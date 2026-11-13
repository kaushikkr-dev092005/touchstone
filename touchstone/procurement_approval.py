"""Human EOA approvals. No signing key, payer credential, or network call lives here."""
import hashlib
from contextlib import closing
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import sqlite3
import time
from decimal import Decimal
from urllib.parse import urlsplit

from .config import ROOT
from .ledger import PolicyError

SCHEMA = json.loads((ROOT/'integrations/metal/procurement-schema.json').read_text())
PURPOSE = 'PREMIUM_INFERENCE_PURCHASE'
STATES = ('PENDING_APPROVAL', 'SIGNED', 'CONSUMED_AT_DISPATCH', 'EXPIRED', 'REVOKED')


class ApprovalError(PolicyError):
    def __init__(self, code):
        self.code = code
        super().__init__(code + (': mandate version changed' if code=='MANDATE_VERSION_MISMATCH' else ''))


def strict_json(text):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ApprovalError('MALFORMED_APPROVAL')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ApprovalError('MALFORMED_APPROVAL')))


def canonical(value):
    """TSC1: typed JSON tree, code-point sorted keys, ASCII JSON, decimal numbers.

    Type tags make numeric normalization unambiguous. Integers and integral floats
    represent the same JSON number. No NaN, infinity, unsafe numbers or surrogates.
    Node implements the identical encoding; this is not an RFC 8785 claim.
    """
    def tree(v):
        if v is None: return ['null']
        if type(v) is bool: return ['bool', v]
        if type(v) in (int, float):
            if not math.isfinite(v) or abs(v) > 9007199254740991:
                raise ApprovalError('MALFORMED_APPROVAL')
            n = format(Decimal(str(v)), 'f')
            if '.' in n: n = n.rstrip('0').rstrip('.')
            if n == '-0': n = '0'
            if len(n) > 100: raise ApprovalError('MALFORMED_APPROVAL')
            return ['number', n]
        if type(v) is str:
            if any(0xD800 <= ord(c) <= 0xDFFF for c in v): raise ApprovalError('MALFORMED_APPROVAL')
            return ['string', v]
        if type(v) is list: return ['array', [tree(x) for x in v]]
        if type(v) is dict and all(type(k) is str for k in v):
            return ['object', [[tree(k), tree(v[k])] for k in sorted(v)]]
        raise ApprovalError('MALFORMED_APPROVAL')
    return json.dumps(tree(value), ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return '0x'+hashlib.sha256(canonical(value).encode('ascii')).hexdigest()


def config_path():
    return Path(os.environ.get('TOUCHSTONE_APPROVAL_CONFIG', ROOT/'data/private/procurement-approvers.json')).resolve()


def read_config():
    try:
        cfg = strict_json(config_path().read_text(encoding='utf-8'))
        if set(cfg) != {'environment', 'chain_id', 'salt', 'signers', 'agent_addresses', 'ledger_paths', 'api_credit_max'}:
            raise ValueError()
        if (type(cfg['chain_id']) is not int or not 0 < cfg['chain_id'] <= 9007199254740991
                or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}', cfg['environment'])
                or not re.fullmatch(r'0x[0-9a-f]{64}', cfg['salt'])
                or type(cfg['api_credit_max']) is not int or cfg['api_credit_max'] < 0):
            raise ValueError()
        for key in ('signers', 'agent_addresses', 'ledger_paths'):
            if not isinstance(cfg[key], list) or not all(isinstance(x, str) for x in cfg[key]): raise ValueError()
        for address in cfg['signers']+cfg['agent_addresses']:
            if not re.fullmatch(r'0x[0-9a-fA-F]{40}', address): raise ValueError()
        if not cfg['signers'] or not cfg['agent_addresses'] or set(x.lower() for x in cfg['signers']) & set(x.lower() for x in cfg['agent_addresses']):
            raise ValueError()
        return cfg
    except (OSError, ValueError, TypeError, KeyError):
        raise ApprovalError('APPROVER_NOT_CONFIGURED') from None


def domain(cfg):
    return {'name': 'Touchstone', 'version': '1', 'chainId': cfg['chain_id'], 'salt': cfg['salt']}


def typed_data(terms, cfg):
    validate_terms(terms)
    return {'domain': domain(cfg), 'primaryType': 'ProcurementApproval',
            'types': {'ProcurementApproval': [{'name': k, 'type': v} for k, v in SCHEMA.items()]}, 'message': terms}


def validate_terms(terms):
    if not isinstance(terms, dict) or set(terms) != set(SCHEMA): raise ApprovalError('MALFORMED_APPROVAL')
    for key, kind in SCHEMA.items():
        value = terms[key]
        if kind == 'uint256':
            if type(value) is not int or not 0 <= value <= 9007199254740991: raise ApprovalError('MALFORMED_APPROVAL')
        elif not isinstance(value, str) or not value or len(value) > 2048:
            raise ApprovalError('MALFORMED_APPROVAL')
        elif kind == 'bytes32' and not re.fullmatch(r'0x[0-9a-f]{64}', value): raise ApprovalError('MALFORMED_APPROVAL')
    if terms['protocol_version'] != '1' or terms['purpose'] != PURPOSE: raise ApprovalError('TERMS_MISMATCH')


def verifier_policy(task):
    from .verifier import VERIFIER_VERSION
    names = ['verifier.py', 'local_tools.py', 'workload.py']
    version = VERIFIER_VERSION
    if task['kind'] == 'invoice_extraction':
        from .invoice_extraction import VERSION
        version = VERSION
        names += ['invoice_extraction.py', 'invoice_roles.py']
    return version, digest({'task_kind': task['kind'], 'min_quality': task['min_quality'],
        'code_sha256': {n: hashlib.sha256((ROOT/'touchstone'/n).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for n in names}})


def make_terms(job, task, quote, key, attempt, fee, cfg, *, simulated=False):
    raw = quote.public() if hasattr(quote, 'public') else quote
    version, policy = verifier_policy(task)
    url = (raw.get('terms') or {}).get('url')
    if not url and simulated: url = 'https://mock.invalid/inference'
    parsed = urlsplit(url or '')
    if (not parsed.hostname or parsed.username or parsed.password or parsed.fragment
            or parsed.scheme not in ('https', 'http')
            or parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1')):
        raise ApprovalError('TERMS_MISMATCH')
    origin = parsed.scheme+'://'+parsed.netloc
    now = int(time.time())
    expires = min(int(raw['expires_at']), int(job['expires_at']), now+300)
    if expires <= now: raise ApprovalError('QUOTE_EXPIRED')
    return dict(protocol_version='1', environment=cfg['environment'], network='eip155:'+str(cfg['chain_id']),
        job_id=job['id'], step_id=task['id'], task_hash=digest(task), purchase_key=key, attempt=attempt,
        mandate_version=job['mandate_version'], payer_scope=(raw.get('payer_scope') or job['id']),
        provider_id=raw['provider'], provider_origin=origin, quote_id=raw['id'], quote_digest=digest(raw),
        quote_expires_ms=int(round(raw['expires_at']*1000)), currency='MOCK_USD' if simulated else 'USDZ',
        quoted_amount=raw['price'], max_amount=job['price_cap'], budget_currency='LEDGER_MICRO_USD',
        job_ceiling=job['budget'], allocation_currency='MOCK_USD' if simulated else 'USDZ', allocation=job['allocation'],
        spent=job['spent'], rail_spent=job['rail_spent'], api_credit_currency='PREPAID_USD',
        api_credit_max=cfg['api_credit_max'] if raw['provider']=='hosted-premium' else 0,
        fee_currency='LEDGER_MICRO_USD', fee_max=fee, verifier_version=version,
        verifier_policy_digest=policy, nonce='0x'+secrets.token_hex(32), issued_at=now, expires_at=expires, purpose=PURPOSE)


def node_verify(terms, signature, expected_signer):
    from .metal import node_executable
    request = {'terms': terms, 'signature': signature, 'expected_signer': expected_signer}
    try:
        result = subprocess.run([node_executable(), str(ROOT/'integrations/metal/procurement-verify.mjs')],
            input=json.dumps(request), text=True, capture_output=True, timeout=15, cwd=ROOT)
        body = json.loads(result.stdout)
        if result.returncode or not body.get('ok'): raise ApprovalError(body.get('code', 'INVALID_SIGNATURE'))
        return body['result']
    except (OSError, ValueError, subprocess.SubprocessError):
        raise ApprovalError('SIGNATURE_VERIFIER_UNAVAILABLE') from None


class ApprovalStore:
    def __init__(self, ledger):
        self.ledger = ledger
        with ledger.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS procurement_approvals(
              id TEXT PRIMARY KEY, nonce TEXT UNIQUE NOT NULL, purchase_key TEXT NOT NULL,
              terms TEXT NOT NULL, digest TEXT UNIQUE NOT NULL, expected_signer TEXT NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('PENDING_APPROVAL','SIGNED','CONSUMED_AT_DISPATCH','EXPIRED','REVOKED')),
              signature TEXT, verification TEXT, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
              consuming_key TEXT UNIQUE, created_event INTEGER, signed_event INTEGER, consumed_event INTEGER);
            CREATE UNIQUE INDEX IF NOT EXISTS approval_active_purchase ON procurement_approvals(purchase_key)
              WHERE state IN ('PENDING_APPROVAL','SIGNED','CONSUMED_AT_DISPATCH');
            CREATE TRIGGER IF NOT EXISTS approval_immutable BEFORE UPDATE OF id,nonce,purchase_key,terms,digest,expected_signer,created_at,expires_at ON procurement_approvals
              BEGIN SELECT RAISE(ABORT,'immutable approval terms'); END;
            CREATE TRIGGER IF NOT EXISTS approval_no_delete BEFORE DELETE ON procurement_approvals
              BEGIN SELECT RAISE(ABORT,'approval records retained'); END;''')
            if 'dispatch_token_hash' not in {r['name'] for r in db.execute('PRAGMA table_info(procurement_approvals)')}:
                db.execute('ALTER TABLE procurement_approvals ADD COLUMN dispatch_token_hash TEXT')

    def _config(self):
        cfg = read_config()
        if str(Path(self.ledger.path).resolve()) not in cfg['ledger_paths']: raise ApprovalError('APPROVAL_LEDGER_UNTRUSTED')
        return cfg

    def _event(self, db, kind, row):
        self.ledger._event(db, kind, {k: row[k] for k in ('id', 'purchase_key', 'digest', 'expected_signer')})
        return db.execute('SELECT MAX(id) FROM events').fetchone()[0]

    def prepare(self, terms):
        validate_terms(terms)
        cfg = self._config()
        if terms['environment'] != cfg['environment'] or terms['network'] != 'eip155:'+str(cfg['chain_id']):
            raise ApprovalError('TERMS_MISMATCH')
        with self.ledger.tx() as db:
            old = db.execute("SELECT * FROM procurement_approvals WHERE purchase_key=? AND state IN ('PENDING_APPROVAL','SIGNED','CONSUMED_AT_DISPATCH')", (terms['purchase_key'],)).fetchone()
            if old:
                self.compare(json.loads(old['terms']), terms)
                return self.public(dict(old), cfg)
            row = dict(id=secrets.token_hex(16), terms=json.dumps(terms, sort_keys=True, separators=(',', ':')),
                       digest=digest(terms), expected_signer=cfg['signers'][0].lower(), purchase_key=terms['purchase_key'])
            event = self._event(db, 'PROCUREMENT_APPROVAL_PREPARED', row)
            db.execute('INSERT INTO procurement_approvals(id,nonce,purchase_key,terms,digest,expected_signer,state,created_at,expires_at,created_event) VALUES(?,?,?,?,?,?,\'PENDING_APPROVAL\',?,?,?)',
                (row['id'], terms['nonce'], terms['purchase_key'], row['terms'], row['digest'], row['expected_signer'], terms['issued_at'], terms['expires_at'], event))
            return self.public(dict(db.execute('SELECT * FROM procurement_approvals WHERE id=?', (row['id'],)).fetchone()), cfg)

    @staticmethod
    def compare(stored, current):
        current = {**current, **{k: stored[k] for k in ('nonce', 'issued_at', 'expires_at')}}
        if stored != current: raise ApprovalError('TERMS_MISMATCH')

    def public(self, row, cfg=None):
        row={k:v for k,v in row.items() if k!='dispatch_token_hash'}
        terms=json.loads(row['terms'])
        job=self.ledger.get_job(terms['job_id'])
        task=next((t for t in json.loads(job['tasks']) if t['id']==terms['step_id']),None) if job else None
        with self.ledger.connect() as db:
            attempt=db.execute('SELECT quote FROM attempts WHERE key=?',(terms['purchase_key'],)).fetchone()
            quote=json.loads(attempt['quote']) if attempt else None
        if task is None:
            with self.ledger.connect() as db:
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='banked_jobs'").fetchone():
                    banked=db.execute('SELECT mandate,state FROM banked_jobs WHERE scope=?',(terms['job_id'],)).fetchone()
                    if banked:
                        task=json.loads(banked['mandate'])['task'];quote=json.loads(banked['state']).get('quote')
        return {**row, 'terms': terms, 'task':task, 'quote':quote, 'typed_data': typed_data(terms, cfg or self._config())}

    def list(self):
        self.expire()
        with self.ledger.connect() as db:
            rows = [dict(r) for r in db.execute('SELECT * FROM procurement_approvals ORDER BY created_at DESC')]
        return [self.public(r) for r in rows]

    def expire(self):
        with self.ledger.tx() as db:
            for row in db.execute("SELECT * FROM procurement_approvals WHERE state IN ('PENDING_APPROVAL','SIGNED') AND expires_at<=?", (int(time.time()),)).fetchall():
                db.execute("UPDATE procurement_approvals SET state='EXPIRED' WHERE id=?", (row['id'],))
                self._event(db, 'PROCUREMENT_APPROVAL_EXPIRED', row)
                self._release(db,row,'APPROVAL_EXPIRED')

    def _release(self, db, row, reason):
        changed=db.execute("UPDATE attempts SET state='VOID',reason=? WHERE key=? AND state='RESERVED'",(reason,row['purchase_key'])).rowcount
        if changed:
            self.ledger._event(db,'RESERVATION_VOIDED',{'key':row['purchase_key'],'reason':reason})

    def submit(self, identity, signature):
        cfg = self._config()
        self.expire()
        with self.ledger.tx() as db:
            row = db.execute('SELECT * FROM procurement_approvals WHERE id=?', (identity,)).fetchone()
            self.check_state(row)
            terms = json.loads(row['terms'])
            attempt = db.execute('SELECT state FROM attempts WHERE key=?', (row['purchase_key'],)).fetchone()
            if attempt:
                if attempt['state']!='RESERVED': raise ApprovalError('APPROVAL_ALREADY_CONSUMED')
                current = self.ledger._approval_terms(db, row['purchase_key'])
            else:
                current = banked_terms(self.ledger, terms['job_id'], db)
            self.compare(terms, current)
            result = node_verify(terms, signature, row['expected_signer'])
            event = self._event(db, 'PROCUREMENT_APPROVAL_SIGNED', row)
            db.execute("UPDATE procurement_approvals SET state='SIGNED',signature=?,verification=?,signed_event=? WHERE id=?",
                       (signature, json.dumps(result), event, identity))
            return self.public(dict(db.execute('SELECT * FROM procurement_approvals WHERE id=?', (identity,)).fetchone()), cfg)

    @staticmethod
    def check_state(row):
        if not row: raise ApprovalError('APPROVAL_REQUIRED')
        code = {'CONSUMED_AT_DISPATCH':'APPROVAL_ALREADY_CONSUMED', 'REVOKED':'APPROVAL_REVOKED', 'EXPIRED':'APPROVAL_EXPIRED'}.get(row['state'])
        if code: raise ApprovalError(code)
        if row['expires_at'] <= time.time(): raise ApprovalError('APPROVAL_EXPIRED')

    def consume(self, db, key, current):
        self._config()
        row = db.execute('SELECT * FROM procurement_approvals WHERE purchase_key=? ORDER BY created_at DESC,rowid DESC LIMIT 1', (key,)).fetchone()
        self.check_state(row)
        if row['state'] != 'SIGNED': raise ApprovalError('APPROVAL_REQUIRED')
        terms = json.loads(row['terms'])
        self.compare(terms, current)
        if digest(terms) != row['digest']: raise ApprovalError('TERMS_MISMATCH')
        node_verify(terms, row['signature'], row['expected_signer'])
        event = self._event(db, 'PROCUREMENT_APPROVAL_CONSUMED', row)
        token=secrets.token_hex(32)
        db.execute("UPDATE procurement_approvals SET state='CONSUMED_AT_DISPATCH',consuming_key=?,consumed_event=?,dispatch_token_hash=? WHERE id=? AND state='SIGNED'", (key, event, hashlib.sha256(token.encode('ascii')).hexdigest(), row['id']))
        # One-time internal handoff: never persist/log/return this capability via
        # the approval API. A restart cannot rebuild it from a consumed record.
        return {'ledger_path': str(Path(self.ledger.path).resolve()), 'approval_id': row['id'], 'purchase_key': key, 'dispatch_token':token}

    def revoke(self, identity):
        with self.ledger.tx() as db:
            row = db.execute('SELECT * FROM procurement_approvals WHERE id=?', (identity,)).fetchone()
            self.check_state(row)
            db.execute("UPDATE procurement_approvals SET state='REVOKED' WHERE id=?", (identity,))
            self._event(db, 'PROCUREMENT_APPROVAL_REVOKED', row)
            self._release(db,row,'APPROVAL_REVOKED')
        return {'id': identity, 'state': 'REVOKED'}


def bind_dispatch(rail, authorization):
    if authorization:
        if not hasattr(rail, 'authorize_purchase'): raise ApprovalError('UNPROTECTED_PAYMENT_ADAPTER')
        rail.authorize_purchase(authorization)


def banked_terms(ledger, scope, db):
    row = db.execute('SELECT * FROM banked_jobs WHERE scope=?', (scope,)).fetchone()
    if not row: raise ApprovalError('APPROVAL_REQUIRED')
    state, mandate = json.loads(row['state']), json.loads(row['mandate'])
    job = {'id': scope, 'expires_at': state['mandate_expires_at'], 'mandate_version': 1,
           'price_cap': mandate['price_cap'], 'budget': mandate['hold'], 'allocation': mandate['allocation'],
           'spent': state['spent_micro_usd'], 'rail_spent': state['spent_micro_usd']}
    quote = {**state['quote'], 'payer_scope': scope}
    cfg=ledger.approvals._config()
    if cfg['chain_id']!=63825: raise ApprovalError('TERMS_MISMATCH')
    return make_terms(job, mandate['task'], quote, state['reservation'], 0, 0, cfg)


def authorize_hosted_call(task, authorization, payload):
    """Second-stage credit dispatch: same signed purchase, never a second API call.

    A seller receipt does not by itself authorize spending this host's API credits.
    The locally protected record must authorize the task AND a separate credit cap.
    """
    if not isinstance(authorization,dict) or set(authorization)!={'approval_id','purchase_key'}:
        raise ApprovalError('APPROVAL_REQUIRED')
    if not all(isinstance(v,str) and 1<=len(v)<=80 for v in authorization.values()):
        raise ApprovalError('MALFORMED_APPROVAL')
    cfg=read_config()
    from .study_costs import published_cost
    body=json.dumps(payload,ensure_ascii=True,separators=(',',':')).encode('ascii')
    if len(body)>100000:raise ApprovalError('API_CREDIT_LIMIT')
    # Deliberately over-count text input as bytes + framing/schema allowance.
    # Published prices and external billing remain independently unverified.
    costs=published_cost({'provider_model':payload['model'],'usage':{
        'input_tokens':len(body)+4096,'output_tokens':payload['max_tokens']}})
    if not costs:raise ApprovalError('API_PRICE_UNAVAILABLE')
    bound=(costs['estimated_credit_micro_usd']*125+99)//100+1000
    from .ledger import Ledger
    selected=None
    for path in cfg['ledger_paths']:
        if not Path(path).is_file():continue
        with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='procurement_approvals'").fetchone():continue
            if db.execute('SELECT 1 FROM procurement_approvals WHERE id=?',(authorization['approval_id'],)).fetchone():
                if selected:raise ApprovalError('TERMS_MISMATCH')
                selected=path
    if not selected:raise ApprovalError('APPROVAL_REQUIRED')
    ledger=Ledger(selected)
    with ledger.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS procurement_hosted_dispatches(
          purchase_key TEXT PRIMARY KEY,approval_id TEXT UNIQUE NOT NULL,request_digest TEXT NOT NULL,
          model TEXT NOT NULL,credit_bound INTEGER NOT NULL,state TEXT NOT NULL,created_at INTEGER NOT NULL)''')
    with ledger.tx() as db:
        row=db.execute('SELECT * FROM procurement_approvals WHERE id=?',(authorization['approval_id'],)).fetchone()
        if row['state']!='CONSUMED_AT_DISPATCH' or row['consuming_key']!=authorization['purchase_key']:
            raise ApprovalError('APPROVAL_REQUIRED')
        terms=json.loads(row['terms'])
        version,policy=verifier_policy(task.public())
        if (terms['currency']!='USDZ' or terms['network']!='eip155:63825' or terms['provider_id']!='hosted-premium'
                or terms['task_hash']!=digest(task.public()) or terms['step_id']!=task.id
                or terms['verifier_version']!=version or terms['verifier_policy_digest']!=policy):
            raise ApprovalError('TERMS_MISMATCH')
        node_verify(terms,row['signature'],row['expected_signer'])
        if terms['api_credit_currency']!='PREPAID_USD' or not bound<=min(terms['api_credit_max'],cfg['api_credit_max']):
            raise ApprovalError('API_CREDIT_LIMIT')
        if db.execute('SELECT 1 FROM procurement_hosted_dispatches WHERE purchase_key=?',(authorization['purchase_key'],)).fetchone():
            raise ApprovalError('APPROVAL_ALREADY_CONSUMED')
        db.execute('INSERT INTO procurement_hosted_dispatches VALUES(?,?,?,?,?,?,?)',
            (authorization['purchase_key'],row['id'],digest(payload),payload['model'],bound,'DISPATCHING',int(time.time())))
        ledger._event(db,'PROCUREMENT_HOSTED_DISPATCHING',{'purchase_key':authorization['purchase_key'],
            'approval_id':row['id'],'request_digest':digest(payload),'credit_bound_micro_usd':bound,'currency':'PREPAID_USD'})
    return {'credit_bound_micro_usd':bound,'retry_allowed':False}
