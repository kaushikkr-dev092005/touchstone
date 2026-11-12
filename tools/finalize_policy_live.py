"""Read actual comparison receipts; exclude hypothetical check fees from live metrics."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.comparison import POLICIES,credit_exposure
from touchstone.study_costs import published_cost


def actual_metrics(report,prior_noncomparison=2225309,ceiling=4500000,outage_proof=None):
    if report.get('label')!='MEASURED' or report.get('mode')!='TESTNET':
        raise ValueError('A simulated or mock report cannot become live evidence')
    keys=[(r['seed'],r['source_id'],r['policy']) for r in report['rows']]
    if len(keys)!=len(set(keys)) or any(r['policy'] not in POLICIES for r in report['rows']):
        raise ValueError('Duplicate or foreign policy outcomes')
    calls=list(report['calls'].values())
    paid=[c for c in calls if c.get('receipt_id')]
    if len({c['receipt_id'] for c in paid})!=len(paid):raise ValueError('Duplicate paid receipt')
    actual=sum(c['price_micro_usdz'] for c in paid)
    if actual!=report['confirmed_provider_micro_usdz']:raise ValueError('Receipt costs disagree')
    units={(seed,source) for seed,source,_policy in keys}
    complete_pairs=sum(all((seed,source,p) in keys for p in POLICIES) for seed,source in units)
    complete=report['complete'] and len(keys)==64 and len(units)==16 and complete_pairs==16
    outage=any(r.get('observed_outage') is True for r in report['rows'])
    if outage_proof:
        outage=outage or (outage_proof.get('verification_passed') is True and outage_proof.get('http_status')==503
            and isinstance(outage_proof.get('approval_plan_sha256'),str) and len(outage_proof['approval_plan_sha256'])==64
            and outage_proof.get('fault')=='outage' and outage_proof.get('schedule_sha256')==outage_proof.get('response_schedule_sha256')
            and outage_proof.get('approval_plan_sha256')==report.get('continuation',{}).get('approval_plan_sha256'))
    quality_drop=any(c.get('provider_metadata',{}).get('chaos_mode')=='quality-drop' for c in paid)
    controls={'all_64_matched_outcomes':complete,'at_least_30_actual_paid_receipts':len(paid)>=30,
        'no_pending_payment':report['pending_attempts']==0,'audit_valid':report['audit']['valid'],
        'receipt_reconciliation_matched':report['reconciliation']['matched'] is True,
        'no_control_violations':not report['control_violations'],
        'new_attempt_cap_respected':max(0,len(calls)-8)<=39,
        'new_hosted_call_cap_respected':max(0,sum(c['provider']=='hosted-premium' for c in calls)-5)<=27,
        'new_provider_spend_cap_respected':max(0,actual-25000)<=390000,
        'per_call_cap_respected':all(type(c['price_micro_usdz']) is int and 0<c['price_micro_usdz']<=10000 for c in calls),
        'credit_ceiling_respected':prior_noncomparison+credit_exposure(report['calls'])<=ceiling,
        'bound_injected_outage_observed':outage,'paid_injected_quality_drop_observed':quality_drop}
    rows=[]
    for policy in POLICIES:
        outcomes=[r for r in report['rows'] if r['policy']==policy]
        own=[c for c in calls if c['policy']==policy];charged=[c for c in own if c.get('receipt_id')]
        strict=sum(r.get('strict_correct') is True for r in outcomes)
        # Offline scorer uses truth_correct; preserve its published summary when present.
        summary=next((r for r in report['summary'] if r['policy']==policy),{})
        strict=summary.get('strict_correct',strict)
        spend=sum(c['price_micro_usdz'] for c in charged)
        usage=[published_cost(c.get('provider_metadata')) for c in own if c['provider']=='hosted-premium']
        known=sum(c['estimated_credit_micro_usd'] for c in usage if c)
        unknown=sum(c is None for c in usage)
        exposure=credit_exposure({str(i):c for i,c in enumerate(own)})
        rows.append({'policy':policy,'outcomes':len(outcomes),'strict_correct':strict,
            'candidates':summary.get('candidates',0),'review':summary.get('review',0),'rejected':summary.get('rejected',0),
            'false_accepts':summary.get('false_accepts',0),'actual_paid_receipts':len(charged),
            'provider_micro_usdz':spend,'provider_micro_usdz_per_strict_correct':spend/strict if strict else None,
            'reported_api_credit_estimate_micro_usd':known,'api_calls_with_unreported_usage':unknown,
            'conservative_api_credit_exposure_micro_usd':exposure,
            'api_credit_estimate_per_strict_correct_micro_usd':known/strict if strict and not unknown else None})
    return {'label':'MEASURED_REAL_TESTNET_POLICY_COMPARISON','complete':complete,'completed_outcomes':len(keys),
        'expected_outcomes':64,'complete_matched_source_pairs':complete_pairs,'actual_paid_receipts':len(paid),'purchase_attempts':len(calls),
        'provider_micro_usdz':actual,'global_conservative_credit_exposure_micro_usd':prior_noncomparison+credit_exposure(report['calls']),
        'global_reported_api_credit_estimate_micro_usd':1990109+sum(r['reported_api_credit_estimate_micro_usd'] for r in rows),
        'total_claude_ceiling_micro_usd':ceiling,'controls':controls,'live_gate_passed':all(controls.values()),
        'summary':rows,'simulated_costs_included':False,'hypothetical_check_fees_excluded':True,
        'banking':'Separate previously completed sandbox integration; no new bank operation',
        'api_billing_independently_reconciled':False,'clearing_finality_independently_verified':False,
        'outage_attestation_timing':'POSTRUN_READ_ONLY' if outage_proof else 'TRIAL_TELEMETRY_ONLY',
        'original_runner_live_gate_passed':report['live_gate_passed'],
        'sources':'FROZEN_SYNTHETIC_WORKLOAD_REAL_MODEL_OUTPUTS_AND_TESTNET_PAYMENTS',
        'financial_transactions_in_this_check':0,'inference_calls_in_this_check':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',default='bench/results/m4-live-20261112/live-report.json')
    parser.add_argument('--output',default='bench/results/m4-live-20261112/actual-financial-results.json')
    args=parser.parse_args()
    outage=ROOT/'bench/results/m4-live-20261112/outage-attestation.json'
    result=actual_metrics(json.loads((ROOT/args.report).read_text(encoding='utf-8')),
        outage_proof=json.loads(outage.read_text()) if outage.exists() else None)
    target=ROOT/args.output;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
