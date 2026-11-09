"""Read-only validation gates. Reports configuration presence, never credential values."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def provider_status(reader):
    services = {'dashboard': bool(reader(8088, '/api/state').get('jobs') is not None),
                'model': reader(8080, '/health').get('status') == 'ok'}
    for name, port, mode in [('local-gpu', 8092, 'model'), ('hosted-premium', 8093, 'anthropic')]:
        raw = reader(port, '/health')
        checks = {'health_available': bool(raw), 'identity_matches': raw.get('provider_id') == name,
                  'provider_type_matches': raw.get('provider_type') == mode,
                  'testnet_63825': raw.get('chain') == 63825,
                  'inference_ready': raw.get('inference_ready') is True}
        if name == 'hosted-premium':
            checks['partner_credits_declared'] = raw.get('upstream_funding') == 'PARTNER_CREDITS_OPERATOR_DECLARED'
        services[name] = {'label': 'MEASURED' if all(checks.values()) else 'BLOCKED', 'checks': checks}
    return services


def profile_status(directory):
    from touchstone.invoice_dataset import build
    from touchstone.invoice_study import code_hashes, evaluate_profile, metrics, score
    records, truth = build()
    current = code_hashes()
    profiles = []
    for path in sorted(Path(directory).glob('*.json')):
        row = {'file': path.name, 'eligible': False}
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            changed = [name for name, value in current.items() if raw.get('code_sha256', {}).get(name) != value]
            row.update(saved_calls=len(raw.get('rows', [])), changed_code=changed,
                       measurement_scope='HISTORICAL_SAVED_OUTPUTS_NO_NEW_MODEL_CALLS')
            rescored = metrics(score(records, truth, raw['rows']))
            row['offline_rescore'] = {k: rescored[k] for k in ('sources_scored', 'strict_correct', 'accepted', 'false_accepts', 'correct_beyond_tools')}
            if changed:
                row.update(label='BLOCKED', reason='STALE_PROFILE_REQUIRES_REMEASUREMENT')
            else:
                evaluated = evaluate_profile(records, truth, raw)
                row.update(label='MEASURED', eligible=evaluated['eligible'],
                           reason='QUALIFIED' if evaluated['eligible'] else 'QUALITY_GATE_NOT_PASSED')
        except (ValueError, KeyError, TypeError, OSError):
            row.update(label='BLOCKED', reason='PROFILE_INVALID_OR_INCOMPATIBLE')
        profiles.append(row)
    return profiles


def paid_preflight(wallet, *, reader, client_factory=None, aggregate_cap=1000000, per_call_cap=10000):
    """Read existing wallets and one quote. No execute path or new wallet is permitted."""
    import re
    from touchstone.metal import MetalRail, task_resource_url
    from touchstone.workload import Task
    if (not isinstance(wallet,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',wallet)
            or type(aggregate_cap) is not int or not 0<aggregate_cap<=1000000
            or type(per_call_cap) is not int or not 0<per_call_cap<=10000 or per_call_cap>aggregate_cap):
        raise ValueError('Use an existing wallet and the proposed maximum 1.00 aggregate / 0.01 per-call caps')
    report={'label':'BLOCKED','scope':'READ_ONLY_PAID_TEST_PREFLIGHT','wallet_scope':wallet,
        'proposed_limits':{'aggregate_micro_usdz':aggregate_cap,'per_call_micro_usdz':per_call_cap,
            'hosted_paid_budget_micro_usd':0,'hosted_credits_authorized':False,'automatic_topups':False,
            'transfers_authorized':False},
        'checks':{},'payments_sent':0,'financial_transactions':0,'model_inference_calls':0,
        'final_approval_received':False,'paid_operation_authorized':False,
        'hosted_study':{'ready':False,'reason':'CREDITS_AND_PERMITTED_USAGE_NOT_VERIFIED_NO_HOSTED_CALLS_AUTHORIZED'},
        'purpose':'One local arithmetic integration probe; not invoice qualification or an M4 live comparison'}
    checks=report['checks']
    checks['existing_wallet']=(ROOT/'data/metal'/wallet/'wallet.sqlite').is_file()
    health=reader(8092,'/health')
    checks['local_seller_ready']=(health.get('provider_id')=='local-gpu' and health.get('provider_type')=='model'
        and health.get('inference_ready') is True and health.get('chain')==63825)
    if not all(checks.values()):
        report['reason']='EXISTING_WALLET_AND_READY_LOCAL_SELLER_REQUIRED'
        return report
    try:
        client=(client_factory or MetalRail)(wallet,'http://127.0.0.1:8092',per_call_cap,aggregate_cap,execute=False)
        funding=client.invoke('funding-status')
        checks['chain_63825']=funding.get('chain_id')==63825
        balance=client.balance()
        receipts=client.invoke('receipts')
        pending=balance.get('pending_invoice') is not False or any(
            row.get('state') in {'RESERVED','UNKNOWN','PAID_OUTPUT_MISSING'} for row in receipts)
        checks['no_pending_purchase']=not pending
        spendable=int(balance['spendable_base_units'])
        if spendable<0:raise ValueError('Invalid spendability')
        report['balances']={'clearing_spendable_base_units':str(spendable),
            'clearing_spendable_micro_usdz':spendable//10**12,'assurance':'OPERATOR_ESTIMATE_NOT_FINALITY',
            'funding_account_usdz_base_units':funding.get('usdz_balance_base_units'),
            'funding_account_native_base_units':funding.get('native_balance_base_units'),
            'funding_account_will_not_be_used':True,'existing_receipts':len(receipts)}
        task=Task('approval-local-probe-001','arithmetic',{'amounts_cents':[1250,775],'discount_cents':25})
        quote=client.quote(task_resource_url('http://127.0.0.1:8092',task))
        checks['quote_provider_matches']=quote.provider=='local-gpu'
        checks['quote_within_caps']=0<quote.price<=per_call_cap and quote.price<=aggregate_cap
        checks['quote_current']=quote.expires_at>time.time()
        checks['existing_clearing_funds_cover_one_call']=spendable>=quote.price*10**12
        report['proposed_test']={'task':task.public(),'task_sha256':hashlib.sha256(json.dumps(task.public(),sort_keys=True).encode()).hexdigest(),
            'calls':1,'estimated_provider_micro_usdz':quote.price,'maximum_provider_micro_usdz':per_call_cap,
            'hosted_api_cost_micro_usd':0,'quote_expires_at':quote.expires_at,'quote_sha256':quote.id,
            'verification':'Independent integer arithmetic; a failed answer is still charged',
            'required_new_deposits':0,'required_transfers':0,'funding_account_transactions':0,
            'unapproved_additional_fees_allowed':False,'requote_before_execution':True}
        report['ready_for_final_approval']=all(checks.values())
        report['label']='MEASURED' if all(checks.values()) else 'BLOCKED'
        report['reason']='AWAITING_FINAL_APPROVAL' if all(checks.values()) else 'READ_ONLY_PRECONDITION_FAILED'
    except Exception as error:
        report.update(reason='READ_ONLY_PREFLIGHT_UNAVAILABLE',failure_type=type(error).__name__)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rpc', action='store_true', help='Also perform a redacted read-only testnet RPC check')
    parser.add_argument('--paid-preflight-wallet',help='Read an existing wallet balance and one local quote under the proposed 1.00/0.01 USDZ limits; never pays')
    parser.add_argument('--output', default='bench/results/validation/readiness.json')
    args = parser.parse_args()
    from tools.run_project import environment, health
    env = environment()
    services = provider_status(health)
    profiles = profile_status(ROOT / 'bench/results/m3/profiles')
    rpc = {'label': 'BLOCKED', 'reason': 'NOT_PROBED', 'transactions_sent': 0}
    if args.rpc:
        from touchstone.rpc import inspect_rpc
        try:
            observed = inspect_rpc()
            rpc = {'label': 'MEASURED', 'connected': observed['connected'], 'chain_id': observed['chain_id'],
                   'transactions_sent': 0}
        except (ValueError, RuntimeError):
            rpc = {'label': 'BLOCKED', 'reason': 'RPC_UNAVAILABLE_OR_WRONG_CHAIN', 'transactions_sent': 0}
    report = {'label': 'MEASURED', 'observed_at': time.time(), 'scope': 'READ_ONLY_VALIDATION_GATE_CHECK',
        'services': services, 'profiles': profiles, 'eligible_models': sum(p['eligible'] for p in profiles),
        'configuration_presence': {'hosted_key': bool(env.get('ANTHROPIC_API_KEY')),
            'hosted_model': bool(env.get('ANTHROPIC_MODEL')), 'metal_rpc': bool(env.get('METAL_RPC_URL'))},
        'rpc': rpc, 'fresh_written_spend_approval': False, 'paid_validation_authorized': False,
        'financial_transactions': 0, 'model_inference_calls': 0,
        'notice': 'Health and configuration presence do not prove working hosted credentials, credits, model quality or settlement.'}
    if args.paid_preflight_wallet:
        report['paid_preflight']=paid_preflight(args.paid_preflight_wallet,reader=health)
    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
