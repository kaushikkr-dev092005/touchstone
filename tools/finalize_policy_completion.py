"""Merge current measured comparison into the historical completion view; no execution."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from touchstone.study_costs import published_cost


def main():
    folder=ROOT/'bench/results/m4-live-20261112'
    read=lambda name:json.loads((folder/name).read_text(encoding='utf-8'))
    actual,raw,wallet,plan=map(read,['actual-financial-results.json','live-report.json','clearing-balance.json','continuation-plan.json'])
    if not actual['complete'] or not actual['live_gate_passed'] or not all(actual['controls'].values()):
        raise ValueError('All measured live gates must pass before completion is published')
    expected=(plan['terms']['effective_comparison_plan']['aggregate_cap_micro_usdz']-actual['provider_micro_usdz'])*10**12
    if wallet['pending_invoice'] or wallet['historical_payments']!=actual['actual_paid_receipts'] or int(wallet['spendable_base_units'])!=expected:
        raise ValueError('Current clearing balance and receipts do not reconcile')
    base=json.loads((ROOT/'bench/results/completion-20261110/final-proof-status.json').read_text())
    result=deepcopy(base)
    result.update(observed_at=time.time(),scope='SAVED_SANDBOX_TESTNET_PROOFS_WITH_COMPLETED_LIVE_COMPARISON',
        original_final_proof_approval_plan_sha256=base['approval_plan_sha256'],approval_plan_sha256=plan['plan_sha256'])
    result['comparison']={**actual,'summary':actual['summary'],'pending_attempts':0,'stop_reason':None,
        'confirmed_provider_micro_usdz':actual['provider_micro_usdz']}
    costs=result['costs'];reported=actual['global_reported_api_credit_estimate_micro_usd'];exposure=actual['global_conservative_credit_exposure_micro_usd']
    costs.update(total_claude_ceiling_micro_usd=4500000,reported_api_credit_estimate_micro_usd=reported,
        unreported_credit_allowance_micro_usd=exposure-reported,conservative_credit_exposure_micro_usd=exposure,
        remaining_credit_allowance_micro_usd=4500000-exposure,
        new_provider_spend_micro_usdz=actual['provider_micro_usdz']+result['integrated']['provider_spend_micro_usdz'])
    result['paid_and_failed_call_log']=result['paid_and_failed_call_log'][:1]
    for call in sorted(raw['calls'].values(),key=lambda c:(c['index'],c['policy'])):
        cost=published_cost(call.get('provider_metadata'));charged=bool(call.get('receipt_id'))
        unpaid=call['status']=='VOID' and call.get('nonpayment_evidence',{}).get('confirmed_nonpayment') is True
        result['paid_and_failed_call_log'].append({'scope':plan['terms']['existing_wallet_only'],
            'task_id':call['task_id'],'policy':call['policy'],'provider':call['provider'],
            'receipt_id':call.get('receipt_id'),'provider_micro_usdz':call['price_micro_usdz'] if charged else 0 if unpaid else None,
            'estimated_api_credit_micro_usd':cost['estimated_credit_micro_usd'] if cost else 0 if call['provider']=='local-gpu' else None,
            'onchain_payment_transaction_id':None,'receipt_status':'preconfirmed' if charged else call['status'],
            'verification':next((r['decision'] for r in raw['rows'] if r['task']['id']==call['task_id']),'UNRESOLVED') if charged else 'CONFIRMED_UNPAID_NO_RETRY' if unpaid else 'UNRESOLVED',
            'invoice_payment_authorized':False})
    for entry in result['wallets']:
        if entry['scope']==plan['terms']['existing_wallet_only']:entry['balance']=wallet
    guard=json.loads((ROOT/'tmp/inference/policy-live-model-gpu-guard.json').read_text())
    result['gpu'].update(maximum_observed_temperature_c=guard['peak_temperature_c'],
        model_stopped_after_study=guard['state']=='EXITED')
    result['continuation_measurement']={'original_live_outcomes':12,'new_live_outcomes':52,
        'new_purchase_attempts':actual['purchase_attempts']-8,'new_actual_paid_receipts':actual['actual_paid_receipts']-3,
        'new_confirmed_provider_micro_usdz':actual['provider_micro_usdz']-25000,'new_funding_micro_usdz':0,
        'new_reported_api_credit_estimate_micro_usd':reported-base['costs']['reported_api_credit_estimate_micro_usd'],
        'new_cash_micro_usd':0,'requests_retried':0,'additional_bank_operations':0,
        'raw_gate_outage_telemetry_supplemented_by':'POSTRUN_READ_ONLY_BOUND_SCHEDULE_ATTESTATION',
        'original_receipt_metadata_restored_without_inference':True}
    (folder/'completion-status.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'comparison_complete':True,'outcomes':64,'paid_receipts':actual['actual_paid_receipts'],
        'global_credit_exposure_micro_usd':exposure,'remaining_wallet_base_units':wallet['spendable_base_units'],
        'live_gate_passed':True,'model_stopped':result['gpu']['model_stopped_after_study']}))


if __name__=='__main__':main()
