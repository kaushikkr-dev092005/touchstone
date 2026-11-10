"""Prepare or execute one separately approved sandbox delegate/card creation proof."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.card_rail import CardRail
from touchstone.holds import OperationJournal, OutcomeUnknown
from touchstone.ledger import canonical, PolicyError
from touchstone.treasury import AirwallexSandbox
from tools.run_project import environment

PUBLIC = ROOT/'bench/results/completion-20261110'
SCOPE = 'issuing-proof-20261110-v1'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    pending.replace(path)


def prepare_plan(client):
    if not client.account_id:raise ValueError('An explicit sandbox account is required')
    return {'mode': 'AIRWALLEX_SANDBOX_ISSUING_ONLY', 'scope': SCOPE,
        'account_fingerprint': hashlib.sha256(client.account_id.encode()).hexdigest(),
        'api_version': CardRail.api_version,
        'cardholder': {'type': 'DELEGATE', 'email': 'touchstone-issuing-20261110-v1@example.com'},
        'card': {'created_by': 'Alex Example', 'synthetic_requester': True,
                 'personalized': False, 'form_factor': 'VIRTUAL', 'purpose': 'COMMERCIAL',
                 'currency': 'USD', 'cap_micro_usd': 10000, 'lifetime_seconds': 1800,
                 'single_use': True, 'cash_withdrawal_blocked': True},
        'maximum_business_writes': {'delegate_create': 1, 'card_create': 1},
        'merchant_charges_authorized': 0, 'funding_transfers_authorized': 0,
        'sensitive_card_details_authorized': False, 'hosted_inference_calls_authorized': 0,
        'production_requests_authorized': 0, 'new_cash_usd_authorized': '0.00',
        'claude_total_ceiling_usd': '3.00', 'gpu_start_authorized': False,
        'automatic_retries_authorized': False, 'additional_scopes_authorized': False,
        'source_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'touchstone/card_rail.py', 'touchstone/holds.py', 'touchstone/treasury.py',
            'tools/run_issuing_proof.py')}}


def fingerprint(plan):
    return hashlib.sha256(canonical(plan).encode()).hexdigest()


def read_delegate(client, holder_id, expected):
    if not isinstance(holder_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', holder_id):
        raise ValueError('Invalid cardholder identifier')
    raw = client.request('GET', '/api/v1/issuing/cardholders/'+holder_id, api_version=CardRail.api_version)
    if (not isinstance(raw, dict) or raw.get('cardholder_id') != holder_id
            or raw.get('type') != expected['type'] or raw.get('email') != expected['email']
            or raw.get('status') not in {'READY', 'PENDING', 'INCOMPLETE', 'DISABLED', 'DELETED'}):
        raise ValueError('Delegate read-back differs from the approved synthetic record')
    return {'cardholder_id': holder_id, 'status': raw['status'], 'type': raw['type']}


def delegate(client, journal, plan):
    # This endpoint has no documented idempotency key. A durable local marker is
    # mandatory, and a lost response must be reconciled with GET, never POST again.
    body = plan['cardholder']
    digest_body = {**body, 'account_fingerprint': plan['account_fingerprint']}
    _, prior = journal.begin(plan['scope'], 'delegate_create', '/api/v1/issuing/cardholders/create', digest_body)
    if prior:return read_delegate(client, prior['cardholder_id'], body)
    try:
        raw = client.request('POST', '/api/v1/issuing/cardholders/create', body, api_version=CardRail.api_version)
        holder = read_delegate(client, raw.get('cardholder_id') if isinstance(raw, dict) else None, body)
        journal.observe_raw(plan['scope'], 'delegate_create', holder)
        return holder
    except Exception:
        journal.uncertain(plan['scope'], 'delegate_create')
        raise OutcomeUnknown('Delegate outcome unknown; use status to reconcile, never create again') from None


def reconcile_delegate(client, journal, plan):
    row = journal.get(plan['scope'], 'delegate_create')
    if not row:return None
    bound = {**plan['cardholder'], 'account_fingerprint': plan['account_fingerprint']}
    if row['digest'] != hashlib.sha256(canonical(bound).encode()).hexdigest():
        raise ValueError('Original delegate terms differ')
    if row['response']:
        holder_id = json.loads(row['response'])['cardholder_id']
    else:
        query = urlencode({'email': plan['cardholder']['email'], 'page_size': 10, 'page_num': 0})
        raw = client.request('GET', '/api/v1/issuing/cardholders?'+query, api_version=CardRail.api_version)
        if (not isinstance(raw, dict) or raw.get('has_more') is not False
                or not isinstance(raw.get('items'), list) or len(raw['items']) != 1):
            raise OutcomeUnknown('No unique delegate found; retain the original operation')
        holder_id = raw['items'][0].get('cardholder_id')
    holder = read_delegate(client, holder_id, plan['cardholder'])
    journal.observe_raw(plan['scope'], 'delegate_create', holder)
    return holder


def execute(client, journal, plan, approval):
    expected = 'APPROVE SANDBOX ISSUING '+fingerprint(plan)[:16]
    if approval != expected:raise PolicyError('Exact plan approval required before any business write')
    if plan != prepare_plan(client):raise PolicyError('Account, code or issuing terms changed; prepare a new plan')
    _, prior = journal.begin(plan['scope'], 'approved_plan', '/local/approved-issuing-plan', {'plan_sha256': fingerprint(plan)})
    if not prior:
        prior = {'expires_at': (datetime.now(timezone.utc)+timedelta(seconds=plan['card']['lifetime_seconds'])).isoformat()}
        journal.observe_raw(plan['scope'], 'approved_plan', prior)
    if datetime.fromisoformat(prior['expires_at']) <= datetime.now(timezone.utc):
        raise PolicyError('Original card expiry has elapsed; no creation or expiry extension allowed')
    holder = delegate(client, journal, plan)
    if holder['status'] != 'READY':raise PolicyError('Delegate needs approval; no card creation sent')
    card = plan['card']
    result = CardRail(client, journal).issue(plan['scope'], holder['cardholder_id'], card['created_by'],
        card['cap_micro_usd'], card['currency'], prior['expires_at'], execute=True, personalized=False)
    return {'label': client.evidence_label, 'scope': plan['scope'], 'plan_sha256': fingerprint(plan),
            'phase': 'CARD_CONTROLS_VERIFIED', 'card': result, 'delegate': holder,
            'merchant_payments': 0, 'funding_transfers': 0, 'hosted_inference_calls': 0,
            'visa_approved_agent': False, 'sensitive_card_details_requested': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'execute', 'status'])
    parser.add_argument('--approval')
    args = parser.parse_args()
    environment()
    client = AirwallexSandbox()
    journal = OperationJournal(ROOT/'data/issuing.sqlite')
    path = PUBLIC/'issuing-plan.json'
    if args.action == 'prepare':
        plan = prepare_plan(client)
        save(path, {'plan': plan, 'plan_sha256': fingerprint(plan), 'approved': False})
        report = {'label': 'PREPARED_NOT_AUTHORIZED', 'plan_sha256': fingerprint(plan),
                  'approval_phrase': 'APPROVE SANDBOX ISSUING '+fingerprint(plan)[:16],
                  'issuing_reads': CardRail(client, journal).doctor(diagnose=True), 'business_writes': 0}
    else:
        saved = json.loads(path.read_text(encoding='utf-8'))
        plan = saved['plan']
        if fingerprint(plan) != saved['plan_sha256']:raise PolicyError('Saved plan integrity failed')
        if plan != prepare_plan(client):raise PolicyError('Plan account or code binding differs')
        if args.action == 'execute':
            report = execute(client, journal, plan, args.approval)
            save(PUBLIC/'issuing-proof.json', report)
        else:
            holder = reconcile_delegate(client, journal, plan)
            report = {'label': 'MEASURED', 'delegate': holder, 'business_writes': 0,
                      'card_controls_verified': False, 'visa_approved_agent': False}
            row = journal.get(plan['scope'], 'approved_plan')
            issued = journal.get(plan['scope'], 'issue')
            if row and issued and holder:
                runtime = json.loads(row['response'])
                card = plan['card']
                report['card'] = CardRail(client, journal).reconcile(plan['scope'], holder['cardholder_id'],
                    card['created_by'], card['cap_micro_usd'], card['currency'], runtime['expires_at'], personalized=False)
                report['card_controls_verified'] = report['card']['controls_verified']
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:main()
    except (OSError, ValueError, RuntimeError, PolicyError) as error:
        print(json.dumps({'label': 'BLOCKED', 'error_type': type(error).__name__,
                          'reason': 'No automatic retry. Preserve the original plan and reconcile existing operations.'}))
        raise SystemExit(2)
