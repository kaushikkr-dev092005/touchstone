"""Project already-public observations into the website's read-only evidence view."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.study_costs import published_cost


def build():
    directory = ROOT/'bench/results/completion-20261110'
    final = json.loads((directory/'final-proof-status.json').read_text(encoding='utf-8'))
    merchant = json.loads((directory/'merchant-onboarding.json').read_text(encoding='utf-8'))
    oauth = json.loads((directory/'merchant-oauth.json').read_text(encoding='utf-8'))
    quality, integrated, costs = final['qualification'], final['integrated'], final['costs']
    records = []
    for index, row in enumerate(final['paid_and_failed_call_log']):
        price = row.get('provider_micro_usdz')
        unpaid = row.get('verification') == 'CONFIRMED_UNPAID_NO_RETRY'
        records.append({'id':str(index),'task':str(row.get('task_id') or row['scope']),
            'provider':row['provider'],'state':'Charged' if price else 'Confirmed unpaid' if unpaid else 'Unresolved',
            'costMicro':0 if unpaid else price,'receipt':row.get('receipt_id'),
            'verification':row.get('verification','UNRESOLVED'),
            'apiCreditMicro':row.get('estimated_api_credit_micro_usd')})
    comparison=None
    latest=ROOT/'bench/results/m4-live-20261112'
    if (latest/'actual-financial-results.json').is_file():
        measured=json.loads((latest/'actual-financial-results.json').read_text(encoding='utf-8'))
        raw=json.loads((latest/'live-report.json').read_text(encoding='utf-8'))
        if measured['label']!='MEASURED_REAL_TESTNET_POLICY_COMPARISON' or measured['simulated_costs_included']:
            raise ValueError('Only measured real-rail comparison evidence may be published')
        records=records[:1] # The earlier integrated bank/model receipt; M4 calls follow from the current report.
        for index,call in enumerate(sorted(raw['calls'].values(),key=lambda c:(c['index'],c['policy']))):
            unpaid=call['status']=='VOID' and call.get('nonpayment_evidence',{}).get('confirmed_nonpayment') is True
            charged=bool(call.get('receipt_id'));cost=published_cost(call.get('provider_metadata'))
            records.append({'id':'m4-'+str(index),'task':call['task_id'],'provider':call['provider'],
                'state':'Charged' if charged else 'Confirmed unpaid' if unpaid else 'Unresolved',
                'costMicro':call['price_micro_usdz'] if charged else 0 if unpaid else None,
                'receipt':call.get('receipt_id'),
                'verification':'CONFIRMED_UNPAID_NO_RETRY' if unpaid else next((r['decision'] for r in raw['rows'] if call['reservation_key'] in r.get('calls',[])),'UNRESOLVED'),
                'policy':call['policy'],'purchaseKey':call['reservation_key'],
                'scope':'m4-live-20261112','evidencePath':'bench/results/m4-live-20261112/live-report.json',
                'apiCreditMicro':cost['estimated_credit_micro_usd'] if cost else 0 if call['provider']=='local-gpu' else None})
        comparison={'completed':measured['completed_outcomes'],'expected':measured['expected_outcomes'],
            'complete':measured['complete'],'liveGatePassed':measured['live_gate_passed'],
            'paidReceipts':measured['actual_paid_receipts'],'attempts':measured['purchase_attempts'],
            'providerUsdz':measured['provider_micro_usdz']/1e6,'policies':measured['summary']}
        costs={**costs,'conservative_credit_exposure_micro_usd':measured['global_conservative_credit_exposure_micro_usd'],
            'total_claude_ceiling_micro_usd':measured['total_claude_ceiling_micro_usd']}
    result = {'date':'12 November 2026' if comparison else '10 November 2026','calibrationCorrect':quality['calibration_strict_correct'],
        'calibrationTotal':quality['calibration_trials'],'holdoutCorrect':quality['holdout_strict_correct'],
        'holdoutTotal':quality['holdout_trials'],'holdUsd':integrated['sandbox_hold_micro_usd']/1e6,
        'captureUsd':integrated['sandbox_capture_micro_usd']/1e6,'modelUsdz':integrated['provider_spend_micro_usdz']/1e6,
        'creditUsd':costs['conservative_credit_exposure_micro_usd']/1e6,
        'creditCeilingUsd':costs['total_claude_ceiling_micro_usd']/1e6,
        'products':merchant['catalog']['records_added'],'oauthVerified':oauth['gateway_accepts_signed_guest_token'],
        'records':records,'comparison':comparison}
    path=ROOT/'apps/web/public/data/evidence.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    from tools.build_public_dashboard import build as build_dashboard
    build_dashboard()
    return {'records':len(records),'private_data_loaded':False,'network_calls':0}


if __name__=='__main__':
    print(json.dumps(build()))
