"""Portable deterministic counterexamples; payment signatures do not attest output."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from .config import ROOT
from .local_tools import solve
from .metal import node_executable
from .verifier import check, VERIFIER_VERSION
from .workload import Task

VERSION = 'touchstone-inferential-fault-v1'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def merkle(body):
    leaves = {name: hashlib.sha256(b'\x00' + encoded([name, value])).hexdigest()
              for name, value in sorted(body.items())}
    level = [bytes.fromhex(value) for value in leaves.values()]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(b'\x01' + level[i] + level[i+1]).digest() for i in range(0, len(level), 2)]
    return {'algorithm': 'SHA-256-domain-separated-binary-tree', 'leaves': leaves, 'root': level[0].hex()}


def counterexample(task, output):
    if task.kind not in {'invoice', 'arithmetic'}:
        raise ValueError('Fault proofs support only the bounded integer invoice/arithmetic contracts')
    expected = solve(task)
    if expected is None or not isinstance(output, dict):
        raise ValueError('A supported source and JSON answer are required')
    verdict = check(task, output)
    if verdict.get('passed') is not False:
        raise ValueError('A correct output cannot create a fault receipt')
    claimed = output.get('total_cents')
    if any(type(value) is float for value in output.values()):
        raise ValueError('This portable counterexample format requires integer numeric output')
    verdict['score'] = int(verdict['score'])
    mismatch = type(claimed) is int and claimed != expected['total_cents']
    return {'error_code': 'INVOICE_TOTAL_MISMATCH' if mismatch else 'OUTPUT_SCHEMA_MISMATCH',
            'claimed_total_minor': claimed if type(claimed) is int else None,
            'recomputed_total_minor': expected['total_cents'], 'currency': 'USD', 'minor_unit_scale': 100,
            'expected_output': expected, 'decision': 'VERIFIED_FAIL', 'verdict': verdict}


def code_hashes():
    return {name: hashlib.sha256((ROOT/'touchstone'/name).read_text(encoding='utf-8').encode()).hexdigest()
            for name in ('verifier.py', 'local_tools.py', 'workload.py')}


def create(record):
    task = Task(**record['terms']['task'])
    receipt = record['result']['receipt']
    raw_quote = record['quote']['terms']
    if record.get('mode') != 'REAL_TESTNET_PROTOCOL_PROBE' or record['result']['state'] != 'DELIVERED':
        raise ValueError('A delivered saved testnet purchase is required')
    output = record['result']['output']['body']['output']
    payment = {'invoice': receipt['invoice'], 'receipt': receipt['receipt'],
               'invoiceSignature': receipt['invoice_signature'], 'entries': receipt['entries']}
    if receipt.get('previous'):
        payment['previous'] = receipt['previous']
    public_task = task.public()
    public_task['min_quality'] = int(task.min_quality) if task.min_quality in (0, 1) else task.min_quality
    body = {'version': VERSION, 'created_at': datetime.now(timezone.utc).isoformat(), 'nonce': uuid.uuid4().hex,
            'task': public_task, 'output': output, 'payment': payment,
            'requirements': raw_quote['offer'], 'resource': raw_quote['url'],
            'delivery_attestation': record['result']['output']['body'].get('delivery_attestation'),
            'counterexample': counterexample(task, output),
            'contract': {'verifier_version': VERIFIER_VERSION, 'code_sha256': code_hashes(),
                         'scope': 'Bounded integer USD invoice/arithmetic only; not a semantic correctness oracle',
                         'provenance': 'RECONSTRUCTED_FROM_PUBLIC_TASK_AND_CURRENT_RULES'},
            'original_charge_base_units': receipt['invoice']['amount'],
            'source_evidence_sha256': digest(record)}
    if len(encoded(body)) > 200000:
        raise ValueError('Fault evidence exceeds the size limit')
    return {'label': 'MEASURED', 'body': body, 'commitment': merkle(body), 'fault_signature': None,
            'limits': {'refund_executed': False, 'credit_issued': False,
                       'historical_unsigned_output_is_not_provider_attributed': True,
                       'signature_alone_is_not_proof_of_fault': True}}


def validate(proof):
    body = proof['body']
    if body['version'] != VERSION or proof['commitment'] != merkle(body):
        raise ValueError('Fault commitment changed')
    if body['contract']['code_sha256'] != code_hashes() or body['contract']['verifier_version'] != VERIFIER_VERSION:
        raise ValueError('Verifier contract changed; review against its original implementation')
    if body['counterexample'] != counterexample(Task(**body['task']), body['output']):
        raise ValueError('Counterexample does not reproduce')
    if body['original_charge_base_units'] != body['payment']['invoice']['amount']:
        raise ValueError('Original charge changed')
    datetime.fromisoformat(body['created_at'])
    if not isinstance(body['nonce'], str) or len(body['nonce']) != 32 or any(c not in '0123456789abcdef' for c in body['nonce']):
        raise ValueError('Invalid fault nonce')
    return True


def cryptographic_check(proof, *, check_network=False, operator_key=None, wallet_scope=None):
    validate(proof)
    env = os.environ.copy()
    if check_network:
        from .config import load_local
        load_local()
        env['METAL_RPC_URL'] = os.environ.get('METAL_RPC_URL', '')
    for name in list(env):
        if name == 'AGENT_PRIVATE_KEY' or name.startswith(('AIRWALLEX_', 'ANTHROPIC_')):
            env.pop(name)
    request = {'packet': proof['body'], 'operator_key': operator_key, 'check_network': check_network,
               'root': proof['commitment']['root'], 'fault_signature': proof.get('fault_signature'),
               'sign_existing_wallet': wallet_scope}
    try:
        result = subprocess.run([node_executable(), str(ROOT/'integrations/metal/fault-proof-cli.mjs')],
                                input=json.dumps(request), capture_output=True, text=True, env=env,
                                cwd=ROOT, timeout=65)
        parsed = json.loads(result.stdout)
        if result.returncode or not parsed.get('ok'):
            raise ValueError
        return parsed['result']
    except (OSError, ValueError, subprocess.SubprocessError):
        raise ValueError('Fault proof cryptographic check failed; no transaction was sent') from None


def save(path, proof):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(proof, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)
