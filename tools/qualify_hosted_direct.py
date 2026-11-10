"""Credit-only continuation after a confirmed unpaid protocol failure. Never touches Metal."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.invoice_corpus import load
from touchstone.invoice_profile import raw_profile,save
from touchstone.invoice_study import code_hashes,evaluate_profile
from touchstone.ledger import canonical,PolicyError
from touchstone.leases import exclusive
from touchstone.providers import anthropic_inference
from touchstone.workload import Task

PLAN=ROOT/'bench/results/m3-v2/direct-continuation-plan.json'
STATUS=ROOT/'bench/results/m3-v2/paid-qualification-status.json'
ORIGINAL=ROOT/'bench/results/m3-v2/profiles/hosted-premium.json'
RESERVE=11200


def fingerprint(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def file_hash(path):return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
def phrase(plan):return 'APPROVE DIRECT QUALIFICATION '+plan['plan_sha256'][:16]


def prepare():
    status=json.loads(STATUS.read_text());original=json.loads(ORIGINAL.read_text())
    if (status['phase']!='STOPPED_NO_RETRY' or not status['confirmed_nonpayment']['confirmed_nonpayment']
        or status['balance']['pending_invoice'] or len(original['rows'])!=1):
        raise PolicyError('Original financial operation must be resolved first')
    corpus='bench/results/m3-v2/dataset';manifest,_,_=load(ROOT/corpus)
    terms={'scope':'invoice-direct-qualification-v2-20261110','model':'claude-haiku-5-5',
        'transport':'DIRECT_ANTHROPIC_PREPAID_API','corpus':corpus,'corpus_sources_sha256':manifest['sources_sha256'],
        'original_plan_sha256':status['plan_sha256'],'original_profile_sha256':file_hash(ORIGINAL),
        'original_status_sha256':file_hash(STATUS),'code_sha256':code_hashes(),'driver_sha256':file_hash(__file__),
        'prepaid_credit_aggregate_cap_micro_usd':1000000,'prior_credit_estimate_micro_usd':656,
        'prior_unreported_credit_exposure_micro_usd':11200,'per_call_credit_reservation_micro_usd':RESERVE,
        'maximum_new_calibration_calls':118,'maximum_new_holdout_calls':60,'maximum_new_calls':178,
        'additional_provider_micro_usdz':0,'additional_funding_micro_usdz':0,'new_hosted_cash_micro_usd':0,
        'native_fees_wei':0,'retries':0,'withdrawals':0,'gpu_model_start':False,
        'skip_failed_source_id':status['confirmed_nonpayment']['task_id'],
        'failed_source_counts_as_strict_incorrect':True,'holdout_only_after_calibration_passes':True,
        'output':'bench/results/m3-v2/profiles/direct-hosted-premium.json',
        'published_rate_full_corpus_upper_estimate_micro_usd':335524,
        'api_counting_preflight':'bench/results/m3-v2/cost-preflight.json',
        'qualification_criteria_changed':False}
    return {'terms':terms,'plan_sha256':fingerprint(terms),'execution_authorized':False}


def run(plan,execute=False,approval=None,infer=anthropic_inference):
    if fingerprint(plan['terms'])!=plan['plan_sha256']:raise ValueError('Plan changed')
    if not execute:return {'phase':'FINAL_APPROVAL_REQUIRED','approval_phrase':phrase(plan),'payments_sent':0,'terms':plan['terms']}
    if approval!=phrase(plan):raise PolicyError('Exact direct-continuation approval required')
    t=plan['terms']
    if (t['code_sha256']!=code_hashes() or t['driver_sha256']!=file_hash(__file__)
        or t['original_profile_sha256']!=file_hash(ORIGINAL) or t['original_status_sha256']!=file_hash(STATUS)):
        raise PolicyError('Bound implementation or original evidence changed')
    from tools.run_project import environment
    environment()
    import os
    if os.environ.get('ANTHROPIC_MODEL')!=t['model']:raise PolicyError('Configured hosted model changed')
    manifest,records,truth=load(ROOT/t['corpus'],include_truth=True)
    if manifest['sources_sha256']!=t['corpus_sources_sha256']:raise PolicyError('Frozen sources changed')
    directory=ROOT/'data'/t['scope'];directory.mkdir(parents=True,exist_ok=True)
    with exclusive(directory/'owner.sqlite'):
        journal=directory/'journal.json'
        if journal.exists():
            state=json.loads(journal.read_text())
            # An interrupted API call may already be billed. No automatic restart.
            if state['plan_sha256']!=plan['plan_sha256']:raise PolicyError('Scope belongs to another plan')
            return state
        original=json.loads(ORIGINAL.read_text());first=original['rows'][0]
        state={'plan_sha256':plan['plan_sha256'],'phase':'RUNNING','calls':[],
            'rows':[{**first,'transport':'METAL_X402_ORIGINAL_UNCHANGED_DELIVERY'},
                    {'task_id':t['skip_failed_source_id'],'output':None,'provider_cost_micro_usd':0,
                     'verification_cost_micro_usd':0,'latency_ms':None,'receipt':None,
                     'protocol_failure':'CONFIRMED_UNPAID_NO_RETRY','transport':'METAL_X402_FAILED_NO_MODEL_OUTPUT'}]}
        def persist():save(journal,state)
        def snapshot(stop=None):
            raw=raw_profile('hosted-premium',t['model'],state['rows'],label='MEASURED',code_sha256=t['code_sha256'],
                dataset_version=manifest['dataset_version'],corpus_sources_sha256=manifest['sources_sha256'],
                transport='DIRECT_PREPAID_API_PLUS_ORIGINAL_X402_DELIVERY',
                original_paid_profile_sha256=t['original_profile_sha256'],continuation_plan_sha256=plan['plan_sha256'],
                failed_original_source_counted_incorrect=True,stop_reason=stop,pending_attempts=0,
                confirmed_provider_spend_including_failed_calls_micro_usd=10000,
                upstream_api_credit_estimate_micro_usd=t['prior_credit_estimate_micro_usd']+sum(c.get('estimated_credit_micro_usd',RESERVE) for c in state['calls']),
                unreported_original_credit_exposure_micro_usd=t['prior_unreported_credit_exposure_micro_usd'],
                upstream_billing_reconciled=False,new_hosted_cash_micro_usd=0,
                additional_usdz_payments=0,verification_cost_label='SIMULATED',
                latency_source='API_WALL_CLOCK_AND_ORIGINAL_PROVIDER_REPORTED')
            save(ROOT/t['output'],raw);return raw
        persist()
        try:
            for partition in ('calibration','holdout'):
                existing={r['task_id'] for r in state['rows']}
                for record in records:
                    if record['partition']!=partition or record['task']['id'] in existing:continue
                    if len(state['calls'])>=t['maximum_new_calls']:raise PolicyError('Call cap reached')
                    exposure=t['prior_credit_estimate_micro_usd']+t['prior_unreported_credit_exposure_micro_usd']+sum(c.get('estimated_credit_micro_usd',RESERVE) for c in state['calls'])
                    if exposure+RESERVE>t['prepaid_credit_aggregate_cap_micro_usd']:raise PolicyError('Credit cap reached')
                    task=Task(**record['task'])
                    call={'task_id':task.id,'partition':partition,'state':'DISPATCHING','reserved_credit_micro_usd':RESERVE,
                          'transaction_id':None,'api_request_id':'NOT_EXPOSED_BY_CURRENT_ADAPTER','provider_micro_usdz':0}
                    state['calls'].append(call);persist() # Before the only API request.
                    output,latency,metadata=infer(task)
                    usage=metadata.get('usage') or {};cost=metadata.get('hosted_api_cost') or {}
                    if (metadata.get('provider_model')!=t['model'] or metadata.get('provider_type')!='ANTHROPIC_API'
                        or any(type(usage.get(k)) is not int or usage[k]<=0 for k in ('input_tokens','output_tokens'))
                        or type(cost.get('estimated_credit_micro_usd')) is not int or cost['estimated_credit_micro_usd']>RESERVE):
                        raise PolicyError('Usage/model differs; reserved exposure retained')
                    call.update(state='REPORTED',estimated_credit_micro_usd=cost['estimated_credit_micro_usd'],
                                usage=usage,billing_reconciled=False)
                    state['rows'].append({'task_id':task.id,'output':output,'provider_metadata':metadata,
                        'provider_cost_micro_usd':0,'verification_cost_micro_usd':0,'receipt':None,
                        'transport':'DIRECT_PREPAID_API','latency_ms':latency})
                    persist();snapshot()
                    print(json.dumps({'partition':partition,'completed':len(state['rows']),
                        'new_api_calls':len(state['calls']),'credit_exposure_micro_usd':exposure+cost['estimated_credit_micro_usd']}),flush=True)
                raw=snapshot();result=evaluate_profile(records,truth,raw,dataset_version=manifest['dataset_version'],corpus_sha256=manifest['sources_sha256'])
                state['evaluation']=result;persist()
                if partition=='calibration' and not result['screen']['passes_statistical_screen']:
                    state['phase']='INELIGIBLE';persist();return state
            state['phase']='COMPLETE' if result['eligible'] else 'INELIGIBLE';persist();return state
        except Exception as error:
            state.update(phase='STOPPED',failure_type=type(error).__name__);persist();snapshot(type(error).__name__);return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--execute',action='store_true');parser.add_argument('--approval')
    args=parser.parse_args()
    if args.action=='prepare':
        plan=prepare();save(PLAN,plan);print(json.dumps({'plan_sha256':plan['plan_sha256'],'approval_phrase':phrase(plan),'terms':plan['terms']},indent=2))
    else:
        result=run(json.loads(PLAN.read_text()),args.execute,args.approval)
        print(json.dumps({k:result.get(k) for k in ('phase','failure_type','evaluation','approval_phrase','terms')},indent=2))
