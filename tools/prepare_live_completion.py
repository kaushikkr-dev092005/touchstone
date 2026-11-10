"""Prepare the final financial proofs for approval. Quotes/counts/reads only; never pays or funds."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.preflight_invoice_study import count
from tools.qualify_hosted_direct import file_hash,fingerprint
from touchstone.comparison import validate,task_id
from touchstone.invoice_corpus import load
from touchstone.invoice_profile import save
from touchstone.invoice_study import evaluate_profile,code_hashes
from touchstone.metal import MetalRail,task_resource_url
from touchstone.workload import Task


def prepare():
    from tools.run_project import environment,health
    from touchstone.rpc import inspect_rpc
    from touchstone.telemetry import sample
    environment()
    profile='bench/results/m3-v2/profiles/sonnet-hosted-premium.json';corpus='bench/results/m3-v2/dataset'
    manifest,records,truth=load(ROOT/corpus,True);raw=json.loads((ROOT/profile).read_text())
    qualified=evaluate_profile(records,truth,raw,dataset_version=manifest['dataset_version'],corpus_sha256=manifest['sources_sha256'])
    if not qualified['eligible']:raise ValueError('Current full model qualification required')
    comparison=json.loads((ROOT/'bench/results/m4-v2/qualified-plan.json').read_text());validate(comparison)
    previous=json.loads((ROOT/'bench/results/m3-v2/sonnet-qualification-result.json').read_text())
    prior=previous['total_conservative_credit_exposure_micro_usd'];remaining=3000000-prior
    task=Task('BANKED-REVIEW-20261110','invoice_extraction',{'text':
        'Independent demonstration receiving copy\nInvoice ID = DEMO-20261110-A\nSupplier = Example Supply\n'
        'Purchase order = PO-DEMO-001\nCurrency = USD\nSubtotal = USD 20.00\nTax = USD 1.00\n'
        'Total due = USD 21.00\nITEM-01 | quantity=2 | unit=USD 10.00 | amount=USD 20.00\n'
        'Receiving copy only. Do not initiate a payment.',
        'purchase_order':{'purchase_order_id':'PO-DEMO-001','supplier_name':'Example Supply','currency':'USD','authorized_cents':10000},'payments':[]})
    save(ROOT/'bench/results/m3-v2/integrated-demo-task.json',task.public())
    provider=health(8093,'/health');local=health(8092,'/health');rpc=inspect_rpc();gpu=sample()
    client=MetalRail('m3v2-20261110-cal','http://127.0.0.1:8093',10000,1320000,execute=False)
    funding=client.invoke('funding-status');balance=client.balance()
    quote=client.quote(task_resource_url('http://127.0.0.1:8093',task))
    local_quote=client.quote(task_resource_url('http://127.0.0.1:8092',task))
    sources=[('integrated-demo',task)]
    for row in comparison['tasks']:
        for policy in ('always-premium','touchstone-ladder','always-cheapest'):
            if policy=='touchstone-ladder' and row['index']==0:continue
            if policy=='always-cheapest' and row['index']!=comparison['outage_index']:continue
            sources.append((policy,Task(task_id(row,policy),'invoice_extraction',row['task']['source'])))
    headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2026-10-21','Content-Type':'application/json'}
    if os.environ.get('ANTHROPIC_WORKSPACE_ID'):headers['anthropic-workspace-id']=os.environ['ANTHROPIC_WORKSPACE_ID']
    observed=sorted(r['provider_metadata']['usage']['output_tokens'] for r in raw['rows'] if r.get('provider_metadata'))
    output95=observed[(len(observed)*95+99)//100-1]
    def free_count(item):
        policy,t=item;result=count(t,raw['model_id'],headers)
        bounded=(result['input_tokens_estimate']*120+99)//100+2048
        result.update(policy=policy,maximum_credit_estimate_micro_usd=bounded*2+2400*10,
            forecast_with_qualification_p95_output_micro_usd=bounded*2+output95*10)
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:costs=list(pool.map(free_count,sources))
    ready=(provider.get('provider_model')==raw['model_id'] and provider.get('inference_ready') is True
        and local.get('inference_ready') is True and quote.price==10000 and local_quote.price<=10000
        and rpc.get('chain_id')==63825 and rpc.get('connected') is True
        and int(funding['usdz_balance_base_units'])>=570000*10**12 and int(funding['native_balance_base_units'])>0
        and not balance.get('pending_invoice') and provider.get('chaos_schedule_sha256')==comparison['schedule_sha256']
        and local.get('chaos_schedule_sha256')==comparison['schedule_sha256'])
    preflight={'label':'MEASURED','observed_at':time.time(),'ready_for_specific_funding_approval':ready,
        'qualified_model':raw['model_id'],'premium_quote_micro_usdz':quote.price,'local_quote_micro_usdz':local_quote.price,
        'funding_balance_base_units':funding['usdz_balance_base_units'],'funding_native_balance_positive':True,
        'existing_calibration_wallet_balance_base_units':balance['spendable_base_units'],'rpc_chain_id':rpc['chain_id'],
        'gpu':gpu,'sources':costs,'hosted_calls_expected':len(costs),'qualification_observed_output_p95_tokens':output95,
        'forecast_credit_micro_usd':sum(r['forecast_with_qualification_p95_output_micro_usd'] for r in costs),
        'maximum_generation_credit_estimate_micro_usd':sum(r['maximum_credit_estimate_micro_usd'] for r in costs),
        'remaining_total_credit_allowance_micro_usd':remaining,'financial_transactions':0,'inference_calls':0,
        'new_wallets_not_created_or_funded':True,'note':'Forecast is not a charge; hard $3 global cap may stop a study before completion. Fresh quotes are rechecked before purchase.'}
    save(ROOT/'bench/results/m3-v2/final-live-preflight.json',preflight)
    terms={'scope':'final-live-proofs-20261110','model':raw['model_id'],'qualification_profile':profile,
        'qualification_profile_sha256':file_hash(ROOT/profile),'qualification_corpus':corpus,'quality_code_sha256':code_hashes(),
        'integrated_scope':'banked-useful-20261110','integrated_task':'bench/results/m3-v2/integrated-demo-task.json',
        'integrated_task_sha256':fingerprint(task.public()),'customer_sandbox_hold_micro_usd':1000000,
        'maximum_customer_sandbox_capture_micro_usd':10000,'sandbox_test_card_only':True,
        'integrated_wallet_deposit_micro_usdz':20000,'integrated_max_purchases':1,
        'comparison_scope':comparison['scope'],'comparison_draft_plan_sha256':comparison['plan_sha256'],
        'comparison_wallet_deposit_micro_usdz':550000,'comparison_max_purchases':50,
        'maximum_new_deposits':2,'maximum_new_deposit_micro_usdz':570000,
        'maximum_new_provider_spend_micro_usdz':510000,'per_call_micro_usdz':10000,
        'maximum_native_fee_per_wallet_wei':'1000000000000000','maximum_native_fee_total_wei':'2000000000000000',
        'total_claude_credit_ceiling_micro_usd':3000000,'prior_credit_exposure_micro_usd':prior,
        'remaining_claude_credit_allowance_micro_usd':remaining,'new_hosted_cash_micro_usd':0,
        'comparison_credit_cap_rule':'3 USD minus qualification exposure and actual-or-reserved integrated-demo credit cost',
        'automatic_retries':0,'automatic_topups':0,'withdrawals':0,'other_transfers':0,
        'unused_float_policy':'RETAIN_IN_ORIGINAL_WALLETS','bridge_or_fx_executed':False,
        'comparison_only_after_integrated_demo_closes':True,
        'financial_code_sha256':{name:file_hash(ROOT/name) for name in ('touchstone/banked.py','touchstone/holds.py',
            'touchstone/checkout.py','touchstone/treasury.py','touchstone/comparison.py','touchstone/study_costs.py',
            'touchstone/ledger.py','integrations/metal/adapter.mjs','integrations/metal/native-budget.mjs')},
        'preflight_sha256':file_hash(ROOT/'bench/results/m3-v2/final-live-preflight.json'),
        'gpu_start_refusal_c':65,'gpu_stop_c':75,'gpu_no_automatic_restart':True}
    plan={'terms':terms,'plan_sha256':fingerprint(terms),'execution_authorized':False,'financial_transactions':0}
    save(ROOT/'bench/results/m3-v2/final-live-plan.json',plan)
    return {'ready_for_specific_funding_approval':ready,'plan_sha256':plan['plan_sha256'],
        'approval_phrase':'APPROVE FINAL LIVE PROOFS '+plan['plan_sha256'][:16],
        'forecast_credit_micro_usd':preflight['forecast_credit_micro_usd'],
        'maximum_generation_credit_estimate_micro_usd':preflight['maximum_generation_credit_estimate_micro_usd'],
        'remaining_total_credit_allowance_micro_usd':remaining,'financial_transactions':0,'inference_calls':0}


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
