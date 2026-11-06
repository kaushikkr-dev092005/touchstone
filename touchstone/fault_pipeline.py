"""Engine verification failure -> signed fault proof -> provider review -> retained acknowledgement.

Every stage is durable and idempotent per payment key. A provider acknowledgement is a
signed statement, never a refund: it is stored beside, and never netted against, the
settled charge. A transport failure leaves the receipt SUBMIT_PENDING for a later retry.
"""
import json
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .config import ROOT
from .fault_proof import create, cryptographic_check, validate
from .ledger import canonical
from .metal import node_executable

STATES = {'NOT_ELIGIBLE', 'PROOF_CREATED', 'SIGN_FAILED', 'SUBMIT_PENDING', 'ACKNOWLEDGED_ACCEPTED',
          'ACKNOWLEDGED_REJECTED', 'ACK_INVALID'}
FINAL = {'NOT_ELIGIBLE', 'ACKNOWLEDGED_ACCEPTED', 'ACKNOWLEDGED_REJECTED', 'ACK_INVALID'}


def provider_origin(url):
    parsed = urlparse(url or '')
    loopback = parsed.hostname in {'127.0.0.1', 'localhost', '::1'}
    if parsed.username or parsed.password or not parsed.hostname or (parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback)):
        raise ValueError('Fault review origin must be HTTPS or loopback HTTP without credentials')
    return f'{parsed.scheme}://{parsed.netloc}'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def http_submit(origin, proof, timeout=15):
    request = urllib.request.Request(origin + '/faults/review', data=json.dumps(proof, allow_nan=False).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            body = response.read(20001)
        if len(body) > 20000:
            raise ValueError('Acknowledgement too large')
        return json.loads(body)
    except urllib.error.HTTPError as error:
        raise ConnectionError('Provider rejected the review request') from error


def node_ack_verifier(ack, seller, root, invoice_id):
    """Offline signature check using the provider's own acknowledgement verifier."""
    request = {'acknowledgement': ack, 'seller': seller, 'root': root, 'invoice_id': invoice_id}
    try:
        process = subprocess.run([node_executable(), str(ROOT / 'integrations/metal/fault-ack-cli.mjs')],
                                 input=json.dumps(request), capture_output=True, text=True, cwd=ROOT, timeout=30)
        parsed = json.loads(process.stdout)
        return process.returncode == 0 and parsed.get('ok') and parsed['result']['signature_valid'] is True
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return False


def metal_record_source(rail):
    """Rebuild the saved-purchase record shape that fault_proof.create consumes, from live rail evidence."""
    client = rail.client

    def source(key, task, quote):
        raw = client.lookup(key)
        result = raw.get('result') if isinstance(raw, dict) else None
        if not isinstance(result, dict) or result.get('state') != 'DELIVERED':
            return None
        return {'mode': 'REAL_TESTNET_PROTOCOL_PROBE', 'terms': {'task': task.public()},
                'quote': {'terms': quote['terms']}, 'result': result}
    return source


class FaultPipeline:
    def __init__(self, ledger, record_source, *, signer=cryptographic_check, submitter=http_submit,
                 ack_verifier=node_ack_verifier, clock=time.time):
        self.ledger, self.record_source = ledger, record_source
        self.signer, self.submitter, self.ack_verifier, self.clock = signer, submitter, ack_verifier, clock
        with ledger.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS fault_receipts(
                key TEXT PRIMARY KEY, job_id TEXT NOT NULL, step_id TEXT NOT NULL, state TEXT NOT NULL,
                root TEXT, proof TEXT, acknowledgement TEXT, detail TEXT, updated_at REAL NOT NULL)''')

    def _save(self, key, job_id, step_id, state, **fields):
        assert state in STATES
        row = self.get(key) or {}
        merged = {name: fields.get(name, row.get(name)) for name in ('root', 'proof', 'acknowledgement', 'detail')}
        with self.ledger.tx() as db:
            db.execute('''INSERT INTO fault_receipts(key,job_id,step_id,state,root,proof,acknowledgement,detail,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET state=excluded.state,root=excluded.root,
                proof=excluded.proof,acknowledgement=excluded.acknowledgement,detail=excluded.detail,updated_at=excluded.updated_at''',
                       (key, job_id, step_id, state, merged['root'], merged['proof'], merged['acknowledgement'],
                        merged['detail'], self.clock()))
            self.ledger._event(db, 'FAULT_RECEIPT_' + state, {'key': key, 'job_id': job_id, 'step_id': step_id,
                'root': merged['root'], 'detail': merged['detail'], 'refund_executed': False})

    def get(self, key):
        with self.ledger.connect() as db:
            row = db.execute('SELECT * FROM fault_receipts WHERE key=?', (key,)).fetchone()
        return dict(row) if row else None

    def receipts(self):
        with self.ledger.connect() as db:
            rows = [dict(r) for r in db.execute('SELECT * FROM fault_receipts ORDER BY rowid')]
        for row in rows:
            row['acknowledgement'] = json.loads(row['acknowledgement']) if row['acknowledgement'] else None
            row.pop('proof', None)
        return rows

    def handle(self, key):
        """Process one failed attempt. Never raises: a fault-evidence problem must not stop procurement."""
        try:
            return self._handle(key)
        except Exception as error:  # noqa: BLE001 - evidence generation is best-effort and durable
            return {'state': 'ERROR', 'detail': type(error).__name__}

    def _handle(self, key):
        prior = self.get(key)
        if prior and prior['state'] in FINAL:
            return prior
        attempt = next((a for a in self.ledger.attempts() if a['key'] == key), None)
        if not attempt or attempt['passed'] != 0 or not attempt.get('verdict'):
            return None
        job_id, step_id = attempt['job_id'], attempt['step_id']
        job = self.ledger.get_job(job_id)
        from .workload import Task
        task = next(Task(**t) for t in json.loads(job['tasks']) if t['id'] == step_id)
        quote = json.loads(attempt['quote'])
        if not prior or not prior['proof']:
            record = self.record_source(key, task, quote)
            try:
                if record is None:
                    raise ValueError('No delivered, signed purchase record is available')
                proof = create(record)
                validate(proof)
            except ValueError as error:
                self._save(key, job_id, step_id, 'NOT_ELIGIBLE', detail=str(error)[:200])
                return self.get(key)
            try:
                crypto = self.signer(proof, wallet_scope=job_id)
                if not crypto.get('fault_signature'):
                    raise ValueError('No fault signature produced')
                proof['fault_signature'] = crypto['fault_signature']
            except (ValueError, OSError):
                self._save(key, job_id, step_id, 'SIGN_FAILED', root=proof['commitment']['root'],
                           proof=canonical(proof), detail='Existing wallet could not sign; retry later')
                return self.get(key)
            self._save(key, job_id, step_id, 'PROOF_CREATED', root=proof['commitment']['root'], proof=canonical(proof))
            prior = self.get(key)
        return self._submit(prior)

    def _submit(self, row):
        key, job_id, step_id = row['key'], row['job_id'], row['step_id']
        proof = json.loads(row['proof'])
        try:
            ack = self.submitter(provider_origin(proof['body']['resource']), proof)
        except (ValueError, OSError, ConnectionError):
            self._save(key, job_id, step_id, 'SUBMIT_PENDING', detail='Provider review unavailable; original charge unchanged')
            return self.get(key)
        invoice_id = proof['body']['payment']['invoice']['id']
        seller = proof['body']['requirements']['payTo']
        if not isinstance(ack, dict) or not self.ack_verifier(ack, seller, row['root'], invoice_id) or ack.get('refund_executed') is not False:
            self._save(key, job_id, step_id, 'ACK_INVALID', acknowledgement=canonical(ack) if isinstance(ack, dict) else None,
                       detail='Acknowledgement signature or binding is invalid; ignored')
            return self.get(key)
        state = 'ACKNOWLEDGED_ACCEPTED' if ack.get('decision') == 'ACCEPTED' else 'ACKNOWLEDGED_REJECTED'
        self._save(key, job_id, step_id, state, acknowledgement=canonical(ack), detail=str(ack.get('reason', ''))[:200])
        return self.get(key)

    def retry_pending(self):
        """Resubmit receipts whose provider review was unavailable; terminal receipts are untouched."""
        results = []
        for row in self.receipts():
            if row['state'] not in {'SUBMIT_PENDING', 'SIGN_FAILED', 'PROOF_CREATED'}:
                continue
            results.append(self.handle(row['key']))
        return results
