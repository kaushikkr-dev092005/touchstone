"""Project already-public observations into the website's read-only evidence view."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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
            'verification':row.get('verification','UNRESOLVED')})
    result = {'date':'10 November 2026','calibrationCorrect':quality['calibration_strict_correct'],
        'calibrationTotal':quality['calibration_trials'],'holdoutCorrect':quality['holdout_strict_correct'],
        'holdoutTotal':quality['holdout_trials'],'holdUsd':integrated['sandbox_hold_micro_usd']/1e6,
        'captureUsd':integrated['sandbox_capture_micro_usd']/1e6,'modelUsdz':integrated['provider_spend_micro_usdz']/1e6,
        'creditUsd':costs['conservative_credit_exposure_micro_usd']/1e6,
        'creditCeilingUsd':costs['total_claude_ceiling_micro_usd']/1e6,
        'products':merchant['catalog']['records_added'],'oauthVerified':oauth['gateway_accepts_signed_guest_token'],
        'records':records}
    path=ROOT/'apps/web/public/data/evidence.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return {'records':len(records),'private_data_loaded':False,'network_calls':0}


if __name__=='__main__':
    print(json.dumps(build()))
