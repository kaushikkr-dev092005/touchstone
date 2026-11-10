"""Execute the explicitly approved final proofs once; retain uncertain exposure."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.qualify_hosted_direct import fingerprint, file_hash
from touchstone.invoice_profile import save
from touchstone.leases import exclusive
from touchstone.study_costs import RESERVATIONS

APPROVED = '878793f09e5acaeb4f301e2bbc3c33f64378f5b2e90108cb61bd8850ae5759cc'
PHRASE = 'APPROVE FINAL LIVE PROOFS ' + APPROVED[:16]


def run_demo(approval):
    from tools.run_project import environment
    from touchstone.banked import BankedStore, BankedWorkflow
    from touchstone.checkout import HostedCheckoutWorkflow
    from touchstone.holds import OperationJournal, SandboxHoldWorkflow
    from touchstone.metal import MetalRail
    from touchstone.treasury import AirwallexSandbox
    from touchstone.workload import Task
    if approval != PHRASE:
        raise ValueError('The exact final proof approval is required')
    plan = json.loads((ROOT/'bench/results/m3-v2/final-live-plan.json').read_text())
    t = plan['terms']
    if plan['plan_sha256'] != APPROVED or fingerprint(t) != APPROVED:
        raise ValueError('Approved final plan changed')
    if any(file_hash(ROOT/name) != digest for name, digest in t['financial_code_sha256'].items()):
        raise ValueError('Approved financial implementation changed')
    environment()
    directory = ROOT/'data'/t['scope']
    with exclusive(directory/'owner.sqlite'):
        path = directory/'journal.json'
        state = json.loads(path.read_text())
        if state['plan_sha256'] != APPROVED or state['total_credit_cap_micro_usd'] != 3000000:
            raise ValueError('Scope or lowered credit ceiling changed')
        if state.get('integrated_dispatch_started'):
            raise ValueError('Original dispatch already started; inspect it without retrying')
        scope = t['integrated_scope']
        if state['funding'][scope]['state'] != 'FUNDED':
            raise ValueError('Only the approved prefunded wallet may be used')
        store = BankedStore(ROOT/'data/banked/ledger.sqlite', ROOT/'data/metal/funding-owner.sqlite')
        if any(job['scope'] == scope for job in store.jobs()):
            raise ValueError('Existing banked job cannot be dispatched again')
        bank = AirwallexSandbox()
        journal = OperationJournal(ROOT/'data/banked/airwallex.sqlite')
        auth = HostedCheckoutWorkflow(bank, journal).status(scope, t['customer_sandbox_hold_micro_usd'])
        if not auth.get('authorization_ready'):
            raise ValueError('Authoritative uncaptured sandbox authorization is required')
        reserve = RESERVATIONS[t['model']]
        if t['prior_credit_exposure_micro_usd'] + reserve > state['total_credit_cap_micro_usd']:
            raise ValueError('Global credit ceiling cannot cover this one call')
        task = Task(**json.loads((ROOT/t['integrated_task']).read_text()))
        if fingerprint(task.public()) != t['integrated_task_sha256']:
            raise ValueError('Approved task changed')
        state.update(phase='INTEGRATED_DISPATCHING', integrated_dispatch_started=True,
                     integrated_credit_exposure_micro_usd=reserve, integrated_credit_status='RESERVED')
        save(path, state)
        workflow = BankedWorkflow(store, SandboxHoldWorkflow(bank, journal),
            lambda wallet, url, cap, budget: MetalRail(wallet, url, cap, budget, execute=True))
        try:
            result = workflow.run(scope, task, 'http://127.0.0.1:8093',
                t['customer_sandbox_hold_micro_usd'], t['integrated_wallet_deposit_micro_usdz'],
                t['per_call_micro_usdz'], integration_probe=True, allow_funding=False,
                return_float=False, qualification_profile=t['qualification_profile'],
                qualification_corpus=t['qualification_corpus'])
            receipt = store.receipt(scope)
            cost = receipt.get('hosted_api_credit_estimate')
            if cost and cost['estimated_credit_micro_usd'] <= reserve:
                state.update(integrated_credit_exposure_micro_usd=cost['estimated_credit_micro_usd'],
                             integrated_credit_status='PROVIDER_USAGE_ESTIMATE')
            state.update(phase=result['phase'], integrated_customer_closed=result['customer_closed'])
            save(ROOT/'bench/results/m3-v2/integrated-receipt.json', receipt)
            save(path, state)
            return {'phase': result['phase'], 'customer_closed': result['customer_closed'],
                'provider_spend_micro_usdz': receipt['token']['provider_spend_micro_usdz'],
                'sandbox_capture_micro_usd': receipt['fiat']['captured_micro_usd'],
                'credit_exposure_micro_usd': state['integrated_credit_exposure_micro_usd'],
                'verification': receipt.get('verification'), 'reconciliation': receipt.get('reconciliation')}
        except Exception as error:
            state.update(phase='INTEGRATED_STOPPED', failure_type=type(error).__name__)
            save(path, state)
            raise


def reconcile_unpaid(runner, client, state_path):
    """Count a proven unpaid trial as a failure, never send its request again."""
    import sqlite3
    from touchstone.comparison import task_id
    from touchstone.ledger import Ledger
    from touchstone.verifier import check
    from touchstone.workload import Task
    state = json.loads(state_path.read_text())
    ledger = Ledger(runner.directory/'ledger.sqlite')
    pending = [a for a in ledger.attempts() if a['state'] in {'RESERVED','DISPATCHING','PAID'}]
    if not pending:
        raise ValueError('No original unresolved request to inspect')
    if len(pending) != 1 or pending[0]['receipt']:
        raise ValueError('Only one receipt-free original attempt may be reconciled')
    attempt = pending[0]
    evidence = client.invoke('inspect-purchase', id=attempt['key'])
    if (evidence.get('confirmed_nonpayment') is not True or evidence.get('pending_invoice')
            or evidence.get('new_receipt_ids') or evidence.get('transactions_sent') != 0
            or evidence.get('inference_requests_sent') != 0):
        raise ValueError('Original outcome remains unresolved; no continuation allowed')
    call = state['calls'][attempt['key']]
    row = next(r for r in runner.plan['tasks'] if task_id(r, call['policy']) == call['task_id'])
    if any(r['task']['id'] == call['task_id'] for r in state['rows']):
        raise ValueError('Failed trial already counted')
    task = Task(call['task_id'], 'invoice_extraction', row['task']['source'])
    failed = {key: row[key] for key in ('seed','index','source_id','template_id','partition')}
    failed.update(task=task.public(), policy=call['policy'], output=None, accepted=False,
        decision='review', calls=[attempt['key']], fault=runner.plan['schedule']['faults'].get(task.id, {}),
        verifier=check(task, None), latency_ms=call.get('latency_ms'),
        protocol_failure='CONFIRMED_UNPAID_NO_RETRY', nonpayment_evidence=evidence)
    # Local-only reconciliation after the pinned SDK proves no possible charge.
    wallet_path = ROOT/'data/metal'/runner.plan['scope']/'wallet.sqlite'
    with closing(sqlite3.connect(wallet_path)) as db, db:
        prior = db.execute('SELECT state FROM purchases WHERE id=?', (attempt['key'],)).fetchone()
        if not prior or prior[0] not in {'RESERVED','UNKNOWN'}:
            raise ValueError('Original SDK record changed')
        result = {'mode':'TESTNET','state':'UNPAID_CONFIRMED','receipt':None,'output':None,
                  'next_action':'NO_RETRY_AUTHORIZED; trial counted as failed', 'evidence':evidence}
        db.execute("UPDATE purchases SET state='UNPAID_CONFIRMED',result=? WHERE id=?",
                   (json.dumps(result), attempt['key']))
    ledger.void(attempt['key'], 'PINNED_SDK_CONFIRMED_UNPAID_NO_RETRY', authoritative=True)
    state['calls'][attempt['key']].update(status='VOID', nonpayment_evidence=evidence)
    state['rows'].append(failed)
    save(state_path, state)
    save(runner.directory/('nonpayment-'+attempt['key']+'.json'), failed)
    return {'failed_task_id':task.id,'request_repeated':False,'financial_transactions':0}


def run_comparison(approval, continuation=False):
    from tools.run_project import environment
    from tools.run_invoice_qualification import fund_once
    from touchstone.banked import BankedStore
    from touchstone.comparison import Comparison, validate
    from touchstone.metal import MetalRail
    from touchstone.telemetry import sample
    if approval != PHRASE:
        raise ValueError('The exact final proof approval is required')
    parent = json.loads((ROOT/'bench/results/m3-v2/final-live-plan.json').read_text())
    t = parent['terms']
    if parent['plan_sha256'] != APPROVED or fingerprint(t) != APPROVED:
        raise ValueError('Approved final plan changed')
    if any(file_hash(ROOT/name) != digest for name, digest in t['financial_code_sha256'].items()):
        raise ValueError('Approved financial implementation changed')
    environment()
    directory = ROOT/'data'/t['scope']
    with exclusive(directory/'owner.sqlite'):
        path = directory/'journal.json'
        state = json.loads(path.read_text())
        if state['plan_sha256'] != APPROVED or state['total_credit_cap_micro_usd'] != 3000000:
            raise ValueError('Scope or lowered credit ceiling changed')
        if state.get('comparison_dispatch_started') and not continuation:
            raise ValueError('Comparison already started; inspect without retrying')
        receipt = BankedStore(ROOT/'data/banked/ledger.sqlite').receipt(t['integrated_scope'])
        if (receipt['phase'] != 'CLOSED_FLOAT_RETAINED' or not receipt['fiat']['customer_closed']
                or state.get('integrated_credit_status') != 'PROVIDER_USAGE_ESTIMATE'):
            raise ValueError('Customer closure and reported demo API usage are required')
        remaining = 3000000 - t['prior_credit_exposure_micro_usd'] - state['integrated_credit_exposure_micro_usd']
        plan = json.loads((ROOT/'bench/results/m4-v2/final-plan.json').read_text())
        validate(plan)
        draft = json.loads((ROOT/'bench/results/m4-v2/qualified-plan.json').read_text())
        changed = {key for key in set(plan)|set(draft) if plan.get(key) != draft.get(key)}
        if (draft['plan_sha256'] != t['comparison_draft_plan_sha256']
                or changed - {'plan_sha256','hosted_credit_cap_micro_usd'}
                or plan['hosted_credit_cap_micro_usd'] != remaining):
            raise ValueError('Comparison differs from approved workload or remaining credit formula')
        gpu = sample()
        if gpu.get('label') != 'MEASURED' or gpu.get('temperature_c', 100) >= 65 or gpu.get('thermal_throttling_active'):
            raise ValueError('GPU telemetry unavailable or temperature too high')
        state['comparison_plan_sha256'] = plan['plan_sha256']
        state['comparison_credit_cap_micro_usd'] = remaining
        save(path, state)
        client = MetalRail(t['comparison_scope'], plan['origins']['local-gpu'],
            t['per_call_micro_usdz'], t['comparison_wallet_deposit_micro_usdz'], execute=True)
        if not continuation:
            fund_once(client, t['comparison_scope'], t['comparison_wallet_deposit_micro_usdz'],
                state, lambda: save(path, state), t['maximum_native_fee_per_wallet_wei'])
        elif state['funding'][t['comparison_scope']]['state'] != 'FUNDED':
            raise ValueError('Continuation cannot fund anything')
        runner = Comparison(plan, ROOT/'data/m4'/plan['scope'])
        if continuation:
            # Serialize the read-only inspection and local reconciliation with
            # the same ownership locks used by the unchanged approved runner.
            with exclusive(runner.directory/'owner.sqlite'), exclusive(runner.wallet_owner):
                proof = reconcile_unpaid(runner, client, runner.directory/'journal.json')
                state.setdefault('confirmed_unpaid_trials_not_retried', []).append(proof)
                save(path, state)
        from touchstone.ledger import Ledger
        ledger = Ledger(runner.directory/'ledger.sqlite')
        readiness = runner.preflight(sum(j['rail_spent'] for j in ledger.jobs()),
                                    sum(bool(a['receipt']) for a in ledger.attempts()))
        save(ROOT/'bench/results/m4-v2/preflight.json', readiness)
        if not readiness['ready']:
            raise ValueError('Comparison readiness failed; no inference dispatched')
        state.update(phase='COMPARISON_DISPATCHING', comparison_dispatch_started=True)
        save(path, state)
        try:
            report = runner.run(True, t['comparison_wallet_deposit_micro_usdz'],
                t['comparison_max_purchases'], True)
        except Exception as error:
            state.update(phase='COMPARISON_STOPPED', failure_type=type(error).__name__)
            save(path, state)
            try:
                save(ROOT/'bench/results/m4-v2/live-report.json', runner.report())
            except Exception:
                pass
            raise
        save(ROOT/'bench/results/m4-v2/live-report.json', report)
        state.update(phase='COMPLETE' if report['complete'] else 'COMPARISON_STOPPED',
            comparison_complete=report['complete'])
        save(path, state)
        return {key: report[key] for key in ('label','complete','live_gate_passed','pending_attempts','control_violations','audit')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['demo','comparison','continue-untouched'])
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--approval')
    args = parser.parse_args()
    if not args.execute:
        parser.error('No execution without --execute and the recorded exact approval')
    result = run_demo(args.approval) if args.action == 'demo' else run_comparison(
        args.approval, continuation=args.action == 'continue-untouched')
    print(json.dumps(result, indent=2))
