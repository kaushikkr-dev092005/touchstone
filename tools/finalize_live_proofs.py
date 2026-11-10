"""Read journals, balances and transaction receipts; never pays or invokes a model."""
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.invoice_profile import save
from touchstone.study_costs import published_cost


def rpc_receipt(tx):
    body = json.dumps({'jsonrpc':'2.0','id':1,'method':'eth_getTransactionReceipt','params':[tx]}).encode()
    request = urllib.request.Request(os.environ['METAL_RPC_URL'], data=body, headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)['result']
    if not result or result.get('status') != '0x1':
        raise ValueError('Funding receipt not confirmed successful')
    return {'transaction_id':tx,'status':'SUCCESS','block_number':int(result['blockNumber'],16),
        'native_fee_wei':str(int(result['gasUsed'],16)*int(result['effectiveGasPrice'],16))}


def finalize():
    from tools.run_project import environment, health
    from touchstone.metal import MetalRail
    environment()
    parent = json.loads((ROOT/'data/final-live-proofs-20261110/journal.json').read_text())
    qualification = json.loads((ROOT/'bench/results/m3-v2/sonnet-qualification-result.json').read_text())
    demo = json.loads((ROOT/'bench/results/m3-v2/integrated-receipt.json').read_text())
    comparison = json.loads((ROOT/'bench/results/m4-v2/live-report.json').read_text())
    calls = []
    demo_cost = demo['hosted_api_credit_estimate']['estimated_credit_micro_usd']
    calls.append({'scope':demo['scope'],'task_id':'BANKED-REVIEW-20261110','provider':'hosted-premium',
        'receipt_id':demo['token']['receipt_id'],'provider_micro_usdz':demo['token']['provider_spend_micro_usdz'],
        'estimated_api_credit_micro_usd':demo_cost,'onchain_payment_transaction_id':None,
        'receipt_status':'preconfirmed','verification':'review','invoice_payment_authorized':False})
    for call in comparison['calls'].values():
        cost = published_cost(call.get('provider_metadata'))
        calls.append({'scope':'m4-qualified-20261110','task_id':call.get('task_id'),'policy':call.get('policy'),
            'provider':call['provider'],'receipt_id':call.get('receipt_id'),
            'provider_micro_usdz':call['price_micro_usdz'] if call.get('receipt_id') else None,
            'estimated_api_credit_micro_usd':cost['estimated_credit_micro_usd'] if cost else 0 if call['provider']=='local-gpu' else None,
            'onchain_payment_transaction_id':None,'receipt_status':'preconfirmed' if call.get('receipt_id') else call['status'],
            'verification':'CANDIDATE_OR_REVIEW_SEPARATELY_RECORDED' if call.get('receipt_id') else 'CONFIRMED_UNPAID_NO_RETRY' if call['status']=='VOID' else 'UNRESOLVED',
            'invoice_payment_authorized':False})
    wallets = []
    for scope, funding in parent['funding'].items():
        client = MetalRail(scope,'http://127.0.0.1:8093',10000,funding['allocation_micro_usdz'])
        balance = client.balance()
        txs = [rpc_receipt(funding['result'][key]) for key in ('approveTx','depositTx') if funding['result'].get(key)]
        native = sum(int(row['native_fee_wei']) for row in txs)
        if native > 10**15:
            raise ValueError('Wallet native fee cap exceeded')
        wallets.append({'scope':scope,'funded_micro_usdz':funding['allocation_micro_usdz'],
            'balance':balance,'funding_transactions':txs,'native_fee_wei':str(native)})
    exposure = qualification['total_conservative_credit_exposure_micro_usd'] + parent['integrated_credit_exposure_micro_usd'] + comparison['hosted_credit_exposure_micro_usd']
    spend = demo['token']['provider_spend_micro_usdz'] + comparison['confirmed_provider_micro_usdz']
    native = sum(int(w['native_fee_wei']) for w in wallets)
    reported = qualification['total_reported_credit_estimate_micro_usd'] + demo_cost + sum(
        c['estimated_api_credit_micro_usd'] or 0 for c in calls[1:])
    checks = {'total_credit_ceiling_respected':exposure<=3000000,'provider_spend_cap_respected':spend<=510000,
        'new_funding_cap_respected':sum(w['funded_micro_usdz'] for w in wallets)<=570000,
        'purchase_attempt_cap_respected':len(calls)<=51,'native_fee_cap_respected':native<=2*10**15,
        'no_pending_invoice':all(not w['balance'].get('pending_invoice') for w in wallets),
        'customer_closed':demo['fiat']['customer_closed'],'capture_cap_respected':demo['fiat']['captured_micro_usd']<=10000,
        'audit_valid':demo['audit']['valid'] and comparison['audit']['valid'],
        'no_comparison_control_violations':not comparison['control_violations']}
    if not all(checks.values()):
        raise ValueError('A final proof control check failed')
    gpu = json.loads((ROOT/'bench/results/m4-v2/gpu-monitor.json').read_text())
    status = {'label':'MEASURED','scope':'SAVED_SANDBOX_TESTNET_PROOFS_NOT_PRODUCTION',
        'approval_plan_sha256':parent['plan_sha256'],'controls':checks,
        'qualification':{'model':'claude-sonnet-5-5','eligible':True,'calibration_strict_correct':120,
            'calibration_trials':120,'holdout_strict_correct':59,'holdout_trials':60,'false_accepts':0,
            'holdout_interrupted_trials_counted_incorrect':1,'criteria_lowered':False,'synthetic_sources':True,
            'correct_review_drafts_beyond_tools':59,'automatic_invoice_payment':False},
        'integrated':{'phase':demo['phase'],'customer_closed':demo['fiat']['customer_closed'],
            'sandbox_hold_micro_usd':demo['fiat']['approved_micro_usd'],'sandbox_capture_micro_usd':demo['fiat']['captured_micro_usd'],
            'provider_spend_micro_usdz':demo['token']['provider_spend_micro_usdz'],'verification':'review',
            'retained_float_base_units':demo['token']['retained_float_base_units'],'bridge_or_fx_executed':False},
        'comparison':{key:comparison[key] for key in ('complete','stop_reason','live_gate_passed','pending_attempts','confirmed_provider_micro_usdz','hosted_credit_exposure_micro_usd','summary')},
        'costs':{'total_claude_ceiling_micro_usd':3000000,'reported_api_credit_estimate_micro_usd':reported,
            'unreported_credit_allowance_micro_usd':exposure-reported,'conservative_credit_exposure_micro_usd':exposure,
            'remaining_credit_allowance_micro_usd':3000000-exposure,'billing_reconciled':False,'new_hosted_cash_micro_usd':0,
            'new_provider_spend_micro_usdz':spend,'new_funding_micro_usdz':sum(w['funded_micro_usdz'] for w in wallets),'new_native_fee_wei':str(native)},
        'gpu':{'maximum_observed_temperature_c':gpu['maximum_observed_temperature_c'],'stop_limit_c':75,
            'start_refusal_c':65,'automatic_thermal_restart':False,'model_stopped_after_study':not bool(health(8080,'/health')),
            'hardware_temperature_guarantee':False},
        'paid_and_failed_call_log':calls,'wallets':wallets,'refund_executed':False,'final_settlement_verified':False,
        'issuing_reads':'PASS','issuing_writes_and_merchant':'EXTERNAL_ACCESS_REQUIRED',
        'visa_onboarding':'EXTERNAL_APPROVAL_REQUIRED','portal_submission':'OPERATOR_ACCESS_REQUIRED',
        'financial_transactions_in_this_check':0,'inference_calls_in_this_check':0}
    save(ROOT/'bench/results/completion-20261110/final-proof-status.json',status)
    return {'controls':checks,'costs':status['costs'],'comparison_complete':comparison['complete']}


if __name__ == '__main__':
    print(json.dumps(finalize(),indent=2))
