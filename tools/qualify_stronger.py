"""A new, explicitly capped Sonnet qualification. Existing criteria and prompts stay frozen."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.qualify_hosted_direct import file_hash,fingerprint
from tools.preflight_invoice_study import token_payload
from touchstone.invoice_corpus import load
from touchstone.invoice_profile import raw_profile,save
from touchstone.invoice_study import code_hashes,evaluate_profile
from touchstone.ledger import PolicyError
from touchstone.leases import exclusive
from touchstone.providers import anthropic_inference
from touchstone.workload import Task

PLAN=ROOT/'bench/results/m3-v2/sonnet-qualification-plan.json'
RESERVE=224000 # $2/M full 100k input + $10/M 2,400 output; independent of typical cost.


def sonnet_cost(usage):
    fields=('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')
    counts=[0 if usage.get(k) is None else usage[k] for k in fields]
    if any(type(v) is not int or v<0 for v in counts):raise ValueError('Invalid Sonnet usage')
    if not counts[0] or not counts[1]:raise ValueError('Unreported Sonnet usage')
    return (sum(v*rate for v,rate in zip(counts,(2000000,10000000,2500000,100000)))+999999)//1000000


def prepare():
    import hashlib
    preflight=ROOT/'bench/results/m3-v2/sonnet-cost-preflight.json';measured=json.loads(preflight.read_text())
    corpus='bench/results/m3-v2/dataset';manifest,records,_=load(ROOT/corpus)
    by_id={r['task_id']:r for r in measured['rows']}
    if not measured['complete'] or measured['model']!='claude-sonnet-5-5' or measured['corpus_sources_sha256']!=manifest['sources_sha256']:
        raise PolicyError('Complete free Sonnet preflight required')
    for record in records:
        payload=json.dumps(token_payload(Task(**record['task']),measured['model'])).encode()
        if by_id[record['task']['id']]['request_sha256']!=hashlib.sha256(payload).hexdigest():raise PolicyError('Prompt changed after count')
    prior=json.loads((ROOT/'bench/results/m3-v2/profiles/direct-hosted-premium.json').read_text())
    exposure=prior['upstream_api_credit_estimate_micro_usd']+prior['unreported_original_credit_exposure_micro_usd']
    terms={'scope':'invoice-sonnet-qualification-v2-20261110','model':measured['model'],
        'corpus':corpus,'corpus_sources_sha256':manifest['sources_sha256'],'code_sha256':code_hashes(),
        'driver_sha256':file_hash(__file__),'utility_sha256':file_hash(ROOT/'tools/qualify_hosted_direct.py'),
        'preflight_sha256':file_hash(preflight),'prepaid_credit_aggregate_cap_micro_usd':8000000,
        'prior_qualification_credit_exposure_micro_usd':exposure,'maximum_new_calls':180,
        'maximum_calibration_calls':120,'maximum_holdout_calls':60,'maximum_output_tokens':2400,
        'per_call_credit_reservation_micro_usd':RESERVE,
        'full_corpus_credit_upper_estimate_micro_usd':measured['estimated_credit_upper_micro_usd'],
        'additional_usdz_purchases':0,'additional_usdz_funding':0,'native_fees_wei':0,
        'new_hosted_cash_micro_usd':0,'retries':0,'automatic_model_switches':0,'gpu_model_start':False,
        'holdout_only_after_calibration_passes':True,'qualification_criteria_changed':False,
        'prompt_changed':False,'thinking':'MODEL_DEFAULT_ADAPTIVE','output':'bench/results/m3-v2/profiles/sonnet-hosted-premium.json',
        'pricing_reference':'https://platform.claude.com/docs/en/about-claude/pricing',
        'pricing_checked_date':'2026-11-10'}
    return {'terms':terms,'plan_sha256':fingerprint(terms),'execution_authorized':False}


def phrase(plan):return 'APPROVE SONNET QUALIFICATION '+plan['plan_sha256'][:16]


def run(plan,execute=False,approval=None,infer=anthropic_inference):
    if fingerprint(plan['terms'])!=plan['plan_sha256']:raise PolicyError('Plan changed')
    if not execute:return {'phase':'FINAL_APPROVAL_REQUIRED','approval_phrase':phrase(plan),'terms':plan['terms'],'inference_calls':0}
    if approval!=phrase(plan):raise PolicyError('Exact new-model spending approval required')
    t=plan['terms']
    if (t['code_sha256']!=code_hashes() or t['driver_sha256']!=file_hash(__file__)
        or t['utility_sha256']!=file_hash(ROOT/'tools/qualify_hosted_direct.py')
        or t['preflight_sha256']!=file_hash(ROOT/'bench/results/m3-v2/sonnet-cost-preflight.json')):
        raise PolicyError('Bound implementation/preflight changed')
    manifest,records,truth=load(ROOT/t['corpus'],include_truth=True)
    if manifest['sources_sha256']!=t['corpus_sources_sha256']:raise PolicyError('Frozen corpus changed')
    from tools.run_project import environment
    environment()
    # Process-local model selection; no persistent account or seller setting changes.
    os.environ['ANTHROPIC_MODEL']=t['model']
    directory=ROOT/'data'/t['scope'];directory.mkdir(parents=True,exist_ok=True)
    with exclusive(directory/'owner.sqlite'):
        journal=directory/'journal.json'
        if journal.exists():
            state=json.loads(journal.read_text())
            if state['plan_sha256']!=plan['plan_sha256']:raise PolicyError('Scope belongs to a different plan')
            return state # Interrupted/complete scopes never dispatch again.
        state={'plan_sha256':plan['plan_sha256'],'phase':'RUNNING','calls':[],'rows':[]}
        def persist():save(journal,state)
        def snapshot(stop=None):
            raw=raw_profile('hosted-premium',t['model'],state['rows'],code_sha256=t['code_sha256'],
                dataset_version=manifest['dataset_version'],corpus_sources_sha256=manifest['sources_sha256'],
                transport='DIRECT_PREPAID_API',qualification_plan_sha256=plan['plan_sha256'],stop_reason=stop,pending_attempts=0,
                confirmed_provider_spend_including_failed_calls_micro_usd=0,new_hosted_cash_micro_usd=0,
                api_credit_estimate_or_reserved_exposure_micro_usd=sum(c.get('estimated_credit_micro_usd',RESERVE) for c in state['calls']),
                previous_studies_credit_exposure_micro_usd=t['prior_qualification_credit_exposure_micro_usd'],
                upstream_billing_reconciled=False,verification_cost_label='SIMULATED',latency_source='API_WALL_CLOCK')
            save(ROOT/t['output'],raw);return raw
        persist()
        try:
            for partition in ('calibration','holdout'):
                for record in records:
                    if record['partition']!=partition:continue
                    exposure=t['prior_qualification_credit_exposure_micro_usd']+sum(c.get('estimated_credit_micro_usd',RESERVE) for c in state['calls'])
                    if exposure+RESERVE>t['prepaid_credit_aggregate_cap_micro_usd']:raise PolicyError('Aggregate credit cap reached')
                    if len(state['calls'])>=t['maximum_new_calls']:raise PolicyError('Call cap reached')
                    task=Task(**record['task']);call={'task_id':task.id,'partition':partition,'state':'DISPATCHING',
                        'reserved_credit_micro_usd':RESERVE,'transaction_id':None,'provider_micro_usdz':0}
                    state['calls'].append(call);persist()
                    output,latency,metadata=infer(task)
                    # Retain a delivered answer before interpreting its cost/identity.
                    state['rows'].append({'task_id':task.id,'output':output,'provider_metadata':metadata,
                        'latency_ms':latency,'receipt':None,'provider_cost_micro_usd':0,'verification_cost_micro_usd':0,
                        'transport':'DIRECT_PREPAID_API'})
                    persist()
                    if metadata.get('provider_model')!=t['model'] or metadata.get('provider_type')!='ANTHROPIC_API':raise PolicyError('Delivered model differs')
                    cost=sonnet_cost(metadata.get('usage') or {})
                    if cost>RESERVE:raise PolicyError('Reported usage exceeds reservation; retain exposure and stop')
                    metadata['hosted_api_cost']={'status':'PROVIDER_USAGE_AT_PUBLISHED_PRICES',
                        'estimated_credit_micro_usd':cost,'billing_reconciled':False,'price_reference':t['pricing_reference'],
                        'price_checked_date':t['pricing_checked_date']}
                    call.update(state='REPORTED',estimated_credit_micro_usd=cost,usage=metadata['usage'],billing_reconciled=False)
                    persist();snapshot()
                    print(json.dumps({'partition':partition,'sources_completed':len(state['rows']),
                        'credit_exposure_micro_usd':exposure+cost}),flush=True)
                result=evaluate_profile(records,truth,snapshot(),dataset_version=manifest['dataset_version'],corpus_sha256=manifest['sources_sha256'])
                state['evaluation']=result;persist()
                if partition=='calibration' and not result['screen']['passes_statistical_screen']:
                    state['phase']='INELIGIBLE';persist();return state
            state['phase']='COMPLETE' if result['eligible'] else 'INELIGIBLE';persist();return state
        except Exception as error:
            state.update(phase='STOPPED',failure_type=type(error).__name__);persist();snapshot(type(error).__name__);return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--execute',action='store_true');parser.add_argument('--approval');args=parser.parse_args()
    if args.action=='prepare':
        plan=prepare();save(PLAN,plan);print(json.dumps({'plan_sha256':plan['plan_sha256'],'approval_phrase':phrase(plan),'terms':plan['terms']},indent=2))
    else:
        result=run(json.loads(PLAN.read_text()),args.execute,args.approval)
        print(json.dumps({k:result.get(k) for k in ('phase','failure_type','evaluation','approval_phrase','terms')},indent=2))
