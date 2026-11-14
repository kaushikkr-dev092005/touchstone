"""Operational zero-charge jobs. No payer, bank mutation, model call or mock rail.

The remote workspace deliberately exposes a smaller capability than the private
financial engine. Quotes are observations; they never create reservations or funds.
"""
import hashlib
import json
import re
import subprocess
import time
import uuid
from pathlib import Path

from .ledger import Ledger, PolicyError, canonical
from .local_tools import TOOL_VERSION, solve
from .procurement_approval import digest, verifier_policy
from .verifier import VERIFIER_VERSION, check
from .workload import Task

ROOT = Path(__file__).resolve().parent.parent
KINDS = {'arithmetic', 'invoice', 'classification', 'invoice_extraction', 'invoice_consistency'}


def validate_task(body):
    required = {'kind', 'source', 'policy', 'budget_micro_usdz', 'max_call_micro_usdz'}
    if type(body) is not dict or set(body) != required:
        raise ValueError('INVALID_JOB_SCHEMA')
    if body['kind'] not in KINDS or type(body['source']) is not dict:
        raise ValueError('UNSUPPORTED_TASK_SCHEMA')
    if body['policy'] not in {'tools-only', 'real-touchstone'}:
        raise ValueError('UNSUPPORTED_POLICY')
    budget, cap = body['budget_micro_usdz'], body['max_call_micro_usdz']
    if any(type(x) is not int or not 0 <= x <= 1_000_000 for x in (budget, cap)) or cap > budget:
        raise ValueError('INVALID_BUDGET')
    if len(canonical(body['source']).encode()) > 16_384:
        raise ValueError('SOURCE_TOO_LARGE')
    return body


class Operations:
    def __init__(self, path):
        self.ledger = Ledger(path)
        with self.ledger.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS operational_jobs(
              id TEXT PRIMARY KEY, owner TEXT NOT NULL, request_key TEXT NOT NULL,
              request_digest TEXT NOT NULL, task TEXT NOT NULL, policy TEXT NOT NULL,
              budget_micro_usdz INTEGER NOT NULL, max_call_micro_usdz INTEGER NOT NULL,
              state TEXT NOT NULL, reason TEXT, output TEXT, verdict TEXT,
              created_at REAL NOT NULL, updated_at REAL NOT NULL,
              UNIQUE(owner,request_key));
            CREATE TABLE IF NOT EXISTS operational_quotes(
              id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES operational_jobs(id),
              origin TEXT NOT NULL, terms TEXT NOT NULL, digest TEXT NOT NULL,
              observed_at REAL NOT NULL, expires_at REAL NOT NULL);
            CREATE TRIGGER IF NOT EXISTS operational_terms_immutable BEFORE UPDATE OF
              owner,request_key,request_digest,task,policy,budget_micro_usdz,max_call_micro_usdz ON operational_jobs
              BEGIN SELECT RAISE(ABORT,'Operational terms are immutable'); END;
            ''')

    @staticmethod
    def public(row):
        result = dict(row)
        for field in ('task', 'output', 'verdict'):
            result[field] = json.loads(result[field]) if result[field] is not None else None
        result.update(mode='OPERATIONAL_ZERO_CHARGE', financial_dispatch_enabled=False,
                      charged_micro_usdz=0, charged_micro_usd=0, api_credit_micro_usd=0,
                      native_fees='NONE', reservation_micro_usdz=0, receipt=None,
                      verifier_version=VERIFIER_VERSION, tool_version=TOOL_VERSION)
        return result

    def create(self, owner, request_key, body):
        validate_task(body)
        if not isinstance(request_key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}', request_key):
            raise ValueError('IDEMPOTENCY_KEY_REQUIRED')
        fingerprint = hashlib.sha256(canonical(body).encode()).hexdigest()
        with self.ledger.tx() as db:
            prior = db.execute('SELECT * FROM operational_jobs WHERE owner=? AND request_key=?', (owner, request_key)).fetchone()
            if prior:
                if prior['request_digest'] != fingerprint:
                    raise PolicyError('IDEMPOTENCY_CONFLICT')
                return self.public(prior)
            identity = 'op_' + uuid.uuid4().hex
            task = Task(identity, body['kind'], body['source']).public()
            now = time.time()
            db.execute('''INSERT INTO operational_jobs
              (id,owner,request_key,request_digest,task,policy,budget_micro_usdz,max_call_micro_usdz,state,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
              (identity, owner, request_key, fingerprint, canonical(task), body['policy'], body['budget_micro_usdz'],
               body['max_call_micro_usdz'], 'QUEUED', now, now))
            self.ledger._event(db, 'JOB_CREATED', {'job_id':identity, 'owner':owner,
                'task_hash':digest(task), 'verifier_policy_hash':verifier_policy(task)[1],
                'mode':'OPERATIONAL_ZERO_CHARGE', 'financial_authority_granted':False})
            return self.public(db.execute('SELECT * FROM operational_jobs WHERE id=?', (identity,)).fetchone())

    def jobs(self, owner):
        with self.ledger.connect() as db:
            return [self.public(r) for r in db.execute('SELECT * FROM operational_jobs WHERE owner=? ORDER BY created_at DESC LIMIT 200', (owner,))]

    def get(self, owner, identity):
        with self.ledger.connect() as db:
            row = db.execute('SELECT * FROM operational_jobs WHERE id=? AND owner=?', (identity, owner)).fetchone()
            if not row:
                raise KeyError('JOB_NOT_FOUND')
            return self.public(row)

    def action(self, owner, identity, action):
        if action not in {'start', 'pause', 'resume'}:
            raise ValueError('UNSUPPORTED_ACTION')
        with self.ledger.tx() as db:
            row = db.execute('SELECT * FROM operational_jobs WHERE id=? AND owner=?', (identity, owner)).fetchone()
            if not row:
                raise KeyError('JOB_NOT_FOUND')
            if row['state'] in {'COMPLETED', 'REVIEW_REQUIRED', 'REJECTED'}:
                return self.public(row)
            task = Task(**json.loads(row['task']))
            def event(kind, **payload):
                self.ledger._event(db, kind, {'job_id':identity, 'owner':owner, 'mode':'OPERATIONAL_ZERO_CHARGE', **payload})
            output = verdict = None
            if action == 'pause':
                state, reason = 'PAUSED', 'OPERATOR_PAUSED'
                event('JOB_PAUSED')
            elif action == 'resume':
                state, reason = 'QUEUED', 'EXPLICIT_START_REQUIRED'
                event('JOB_RESUMED', dispatched=False)
            elif row['state'] == 'PAUSED':
                raise PolicyError('JOB_PAUSED')
            else:
                event('PLANNING_STARTED')
                output = solve(task)
                if output is None:
                    state = 'BLOCKED'
                    reason = 'LOCAL_TOOL_ABSTAINED' if row['policy'] == 'tools-only' else 'PROVIDER_QUALIFICATION_AND_SIGNED_APPROVAL_REQUIRED'
                    event('JOB_BLOCKED', reason=reason, financial_calls=0)
                else:
                    event('LOCAL_TOOL_SELECTED', tool=TOOL_VERSION)
                    verdict = check(task, output)
                    state = ('REVIEW_REQUIRED' if verdict.get('decision') == 'review' else
                             'COMPLETED' if verdict.get('passed') else 'REJECTED')
                    reason = verdict.get('reason', 'VERIFIER_DECISION')
                    event('VERIFICATION_PASSED' if state == 'COMPLETED' else 'MANUAL_REVIEW_REQUIRED' if state == 'REVIEW_REQUIRED' else 'VERIFICATION_REJECTED', verifier=VERIFIER_VERSION)
                    event('JOB_COMPLETED' if state == 'COMPLETED' else 'JOB_BLOCKED', state=state, external_charges=0)
            db.execute('UPDATE operational_jobs SET state=?,reason=?,output=?,verdict=?,updated_at=? WHERE id=?',
                       (state, reason, canonical(output) if output is not None else None,
                        canonical(verdict) if verdict is not None else None, time.time(), identity))
            return self.public(db.execute('SELECT * FROM operational_jobs WHERE id=?', (identity,)).fetchone())

    def quotes(self, owner, identity, providers, *, probe=None):
        """Operator-configured origins only; SDK validates real x402 offers, never opens a wallet."""
        job = self.get(owner, identity)
        task = Task(**job['task'])
        if job['policy'] == 'tools-only':
            raise PolicyError('TOOLS_ONLY_POLICY')
        if not job['max_call_micro_usdz']:
            raise PolicyError('PRICE_CAP_ZERO')
        from .metal import task_resource_url, node_executable
        from .procurement_evidence import summary
        import os
        results = []
        for provider in providers:
            terms = {'url': task_resource_url(provider['origin'], task), 'maximum_micro_usdz':job['max_call_micro_usdz']}
            try:
                if probe:
                    raw = probe(terms)
                else:
                    env = {k:v for k,v in os.environ.items() if not k.startswith(('AIRWALLEX_','ANTHROPIC_','METAL_','TOUCHSTONE_')) and k != 'AGENT_PRIVATE_KEY'}
                    env['TOUCHSTONE_IGNORE_LOCAL_CONFIG'] = '1'
                    p = subprocess.run([node_executable(),str(ROOT/'integrations/metal/quote-probe.mjs')],
                        input=canonical(terms), capture_output=True, text=True, timeout=45, env=env, cwd=ROOT)
                    if p.returncode:
                        raise RuntimeError('PROVIDER_QUOTE_UNAVAILABLE')
                    raw = json.loads(p.stdout)
                if raw['provider_id'] != provider['id'] or raw['url'] != terms['url'] or raw['expires_at'] <= time.time()*1000:
                    raise ValueError('QUOTE_IDENTITY_OR_EXPIRY_MISMATCH')
                identity_quote = digest(raw)
                with self.ledger.tx() as db:
                    db.execute('INSERT OR IGNORE INTO operational_quotes VALUES(?,?,?,?,?,?,?)',
                        (identity_quote, identity, provider['origin'], canonical(raw), identity_quote, time.time(), raw['expires_at']/1000))
                    self.ledger._event(db,'PROVIDER_QUOTE_RECEIVED',{'job_id':identity,'owner':owner,
                        'quote_digest':identity_quote,'provider':provider['id'],'payment_dispatched':False})
                results.append({'provider':provider['id'], 'status':'QUOTE_RECEIVED', 'quote':raw,
                    'digest':identity_quote, 'qualification':'BLOCKED_REQUALIFICATION_REQUIRED',
                    'dispatch':'BLOCKED_REMOTE_FINANCIAL_DISPATCH_DISABLED', 'approval':'APPROVAL_REQUIRED'})
            except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError):
                results.append({'provider':provider['id'], 'status':'BLOCKED', 'reason':'PROVIDER_QUOTE_UNAVAILABLE'})
        return {'providers':results, 'evidence_status':summary()['status'], 'payments_dispatched':0,
                'reason':None if providers else 'NO_OPERATOR_CONFIGURED_PROVIDERS'}
