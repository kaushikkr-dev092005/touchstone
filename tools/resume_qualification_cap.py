"""Apply the operator's lower $3 ceiling; resume only untouched sources, never an uncertain call."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.qualify_stronger import RESERVE,sonnet_cost
from tools.qualify_hosted_direct import file_hash,fingerprint
from touchstone.invoice_corpus import load
from touchstone.invoice_profile import raw_profile,save
from touchstone.invoice_study import code_hashes,evaluate_profile
from touchstone.ledger import PolicyError
from touchstone.leases import exclusive
from touchstone.providers import anthropic_inference
from touchstone.workload import Task


def resume(plan,execute=False,cap=3000000,infer=anthropic_inference):
    if not execute:return {'phase':'EXECUTE_REQUIRED','effective_total_credit_cap_micro_usd':cap,'inference_calls':0}
    if type(cap) is not int or not 0<cap<=3000000:raise PolicyError('Only the user-authorized lower ceiling is permitted')
    t=plan['terms']
    if (fingerprint(t)!=plan['plan_sha256'] or t['code_sha256']!=code_hashes()
        or t['driver_sha256']!=file_hash(ROOT/'tools/qualify_stronger.py')
        or t['model']!='claude-sonnet-5-5'):raise PolicyError('Original qualification provenance changed')
    from tools.run_project import environment
    environment();os.environ['ANTHROPIC_MODEL']=t['model']
    manifest,records,truth=load(ROOT/t['corpus'],include_truth=True)
    if manifest['sources_sha256']!=t['corpus_sources_sha256']:raise PolicyError('Frozen corpus changed')
    directory=ROOT/'data'/t['scope'];journal=directory/'journal.json'
    with exclusive(directory/'owner.sqlite'):
        state=json.loads(journal.read_text())
        if state['plan_sha256']!=plan['plan_sha256']:raise PolicyError('Original study differs')
        if state.get('lower_cap_transition'):
            # An interrupted continuation never restarts automatically either.
            return state
        if state['phase']!='RUNNING':raise PolicyError('Only the interrupted original controller may transition')
        save(directory/'before-lower-cap.json',state)
        calls=state['calls'];ids=[c['task_id'] for c in calls]
        row_ids=[r['task_id'] for r in state['rows']]
        if len(set(ids))!=len(ids) or len(set(row_ids))!=len(row_ids) or not set(row_ids)<=set(ids):
            raise PolicyError('Original source accounting differs')
        unknown=[]
        for call in calls:
            if call['state']!='REPORTED':
                if call['task_id'] in row_ids:raise PolicyError('Delivered but unpriced source requires separate review')
                call['state']='INTERRUPTED_UNKNOWN_NO_RETRY';unknown.append(call['task_id'])
                state['rows'].append({'task_id':call['task_id'],'output':None,'receipt':None,
                    'provider_cost_micro_usd':0,'verification_cost_micro_usd':0,'latency_ms':None,
                    'transport':'DIRECT_PREPAID_API','completion_status':'INTERRUPTED_FOR_LOWER_CAP_NO_RETRY'})
        transition={'observed_at':time.time(),'original_plan_sha256':plan['plan_sha256'],
            'effective_total_credit_cap_micro_usd':cap,'authority':'USER_EXPLICITLY_REDUCED_TOTAL_CEILING_TO_3_USD',
            'completed_original_results_reused':len(row_ids),'unknown_original_sources_never_repeated':unknown,
            'unknown_credit_allowance_micro_usd':len(unknown)*RESERVE,'criteria_changed':False,'prompts_changed':False,
            'resume_driver_sha256':file_hash(__file__),'new_usdz_operations':0}
        state['lower_cap_transition']=transition;state['phase']='RUNNING_LOWER_CAP'
        # This file may only decrease the cap, so later steering can stop new calls cleanly.
        save(directory/'credit-ceiling.json',{'maximum_micro_usd':cap})
        def persist():save(journal,state)
        def exposure():return t['prior_qualification_credit_exposure_micro_usd']+sum(c.get('estimated_credit_micro_usd',RESERVE) for c in calls)
        def snapshot(stop=None):
            raw=raw_profile('hosted-premium',t['model'],state['rows'],code_sha256=t['code_sha256'],
                dataset_version=manifest['dataset_version'],corpus_sources_sha256=manifest['sources_sha256'],
                transport='DIRECT_PREPAID_API',qualification_plan_sha256=plan['plan_sha256'],
                effective_total_credit_cap_micro_usd=cap,lower_cap_transition=transition,
                stop_reason=stop,pending_attempts=0,interrupted_api_calls_counted_incorrect=len(unknown),
                api_credit_estimate_or_reserved_exposure_micro_usd=sum(c.get('estimated_credit_micro_usd',RESERVE) for c in calls),
                api_credit_reported_estimate_micro_usd=sum(c.get('estimated_credit_micro_usd',0) for c in calls),
                unreported_api_credit_allowance_micro_usd=sum(RESERVE for c in calls if c['state']!='REPORTED'),
                previous_studies_credit_exposure_micro_usd=t['prior_qualification_credit_exposure_micro_usd'],
                upstream_billing_reconciled=False,new_hosted_cash_micro_usd=0,
                confirmed_provider_spend_including_failed_calls_micro_usd=0,verification_cost_label='SIMULATED')
            save(ROOT/t['output'],raw);return raw
        persist();save(ROOT/'bench/results/m3-v2/credit-ceiling-reduction.json',transition)
        try:
            current=evaluate_profile(records,truth,snapshot(),dataset_version=manifest['dataset_version'],corpus_sha256=manifest['sources_sha256'])
            if not current['calibration_complete'] or not current['screen']['passes_statistical_screen']:
                raise PolicyError('Original complete calibration must pass before holdout continuation')
            seen=set(ids)
            for record in records:
                if record['task']['id'] in seen:continue
                if record['partition']!='holdout':raise PolicyError('Calibration changed or is incomplete')
                lowered=json.loads((directory/'credit-ceiling.json').read_text())['maximum_micro_usd']
                if type(lowered) is not int or not 0<lowered<=cap:raise PolicyError('Budget override may only decrease')
                cap=lowered
                if exposure()+RESERVE>cap:raise PolicyError('Reduced total ceiling cannot cover another call')
                if len(calls)>=t['maximum_new_calls']:raise PolicyError('Original call cap reached')
                task=Task(**record['task']);call={'task_id':task.id,'partition':'holdout','state':'DISPATCHING',
                    'reserved_credit_micro_usd':RESERVE,'transaction_id':None,'provider_micro_usdz':0}
                calls.append(call);persist()
                output,latency,metadata=infer(task)
                state['rows'].append({'task_id':task.id,'output':output,'provider_metadata':metadata,
                    'latency_ms':latency,'receipt':None,'provider_cost_micro_usd':0,'verification_cost_micro_usd':0,
                    'transport':'DIRECT_PREPAID_API'})
                persist()
                if metadata.get('provider_model')!=t['model'] or metadata.get('provider_type')!='ANTHROPIC_API':raise PolicyError('Delivered model differs')
                cost=sonnet_cost(metadata.get('usage') or {})
                if cost>RESERVE:raise PolicyError('Cost exceeds reserved exposure')
                metadata['hosted_api_cost']={'status':'PROVIDER_USAGE_AT_PUBLISHED_PRICES',
                    'estimated_credit_micro_usd':cost,'billing_reconciled':False,'price_reference':t['pricing_reference'],
                    'price_checked_date':t['pricing_checked_date']}
                call.update(state='REPORTED',estimated_credit_micro_usd=cost,usage=metadata['usage'],billing_reconciled=False)
                seen.add(task.id);persist();snapshot()
                print(json.dumps({'sources_completed':len(state['rows']),'total_credit_exposure_micro_usd':exposure(),
                    'effective_cap_micro_usd':cap}),flush=True)
            result=evaluate_profile(records,truth,snapshot(),dataset_version=manifest['dataset_version'],corpus_sha256=manifest['sources_sha256'])
            state['evaluation']=result;state['phase']='COMPLETE' if result['eligible'] else 'INELIGIBLE';persist();return state
        except Exception as error:
            state.update(phase='STOPPED',failure_type=type(error).__name__);persist();snapshot(type(error).__name__);return state


if __name__=='__main__':
    from touchstone.holds import micro_usd
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--total-credit-cap-usd',default='3');args=parser.parse_args()
    plan=json.loads((ROOT/'bench/results/m3-v2/sonnet-qualification-plan.json').read_text())
    result=resume(plan,args.execute,micro_usd(args.total_credit_cap_usd))
    print(json.dumps({k:result.get(k) for k in ('phase','failure_type','evaluation','effective_total_credit_cap_micro_usd')},indent=2))
