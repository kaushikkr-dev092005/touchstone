"""One approved, scope-bound hosted qualification; no retries, withdrawals or automatic top-ups."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.hosted_cost import estimate_usage
from touchstone.invoice_corpus import load
from touchstone.invoice_profile import paid,save
from touchstone.invoice_study import code_hashes,evaluate_profile
from touchstone.leases import exclusive
from touchstone.metal import MetalRail,dollars
from touchstone.ledger import PolicyError,canonical


def fingerprint(value):return hashlib.sha256(canonical(value).encode()).hexdigest()


def prepare(corpus,preflight):
    from tools.preflight_invoice_study import token_payload
    from touchstone.workload import Task
    manifest,records,_=load(corpus)
    measured=json.loads(Path(preflight).read_text(encoding='utf-8'))
    if not measured.get('complete') or measured.get('model')!='claude-haiku-5-5':raise ValueError('Complete free cost preflight required')
    by_id={row['task_id']:row for row in measured['rows']}
    for record in records:
        task=Task(**record['task']);payload=json.dumps(token_payload(task,measured['model'])).encode()
        if by_id.get(task.id,{}).get('request_sha256')!=hashlib.sha256(payload).hexdigest():
            raise ValueError('A source/prompt changed after token counting')
    terms={'scope':'invoice-qualification-v2-20261110','corpus':str(Path(corpus)),
        'corpus_sources_sha256':manifest['sources_sha256'],'model':measured['model'],
        'provider_origin':'http://127.0.0.1:8093','code_sha256':code_hashes(),
        'driver_sha256':hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'calibration_wallet':'m3v2-20261110-cal','holdout_wallet':'m3v2-20261110-held',
        'calibration_allocation_micro_usdz':1320000,'holdout_allocation_micro_usdz':660000,
        'maximum_funding_micro_usdz':1980000,'maximum_provider_spend_micro_usdz':1800000,
        'per_call_micro_usdz':10000,'maximum_calls':180,'prepaid_credit_cap_micro_usd':1000000,
        'maximum_native_fee_per_wallet_wei':'1000000000000000','maximum_native_fee_total_wei':'2000000000000000',
        'maximum_deposits':2,'new_hosted_cash_spend':0,'reference_calls':0,'automatic_retries':0,
        'withdrawals':0,'holdout_runs_only_after_calibration_passes':True,
        'estimated_prepaid_credit_micro_usd':measured['estimated_credit_upper_micro_usd'],
        'profile_output':'bench/results/m3-v2/profiles/hosted-premium.json'}
    return {'terms':terms,'plan_sha256':fingerprint(terms),'execution_authorized':False}


def approval_phrase(plan):return 'APPROVE QUALIFICATION '+plan['plan_sha256'][:16]


def fund_once(client,scope,allocation,state,persist,fee_cap):
    phase=state.setdefault('funding',{}).get(scope)
    if phase and phase['state']=='FUNDED':return
    if phase:raise PolicyError('Original funding outcome unresolved; no retry or replacement deposit')
    balance=client.balance()
    if balance.get('pending_invoice') is not False or balance.get('historical_payments',0):
        raise PolicyError('A qualification wallet must have no prior purchase or pending invoice')
    if int(balance['spendable_base_units'])>=allocation*10**12:
        state['funding'][scope]={'state':'FUNDED','deposits_sent':0};persist();return
    state['funding'][scope]={'state':'DISPATCHING','allocation_micro_usdz':allocation};persist()
    try:
        result=client.invoke('deposit',dollars=dollars(allocation),native_gas_cap_wei=fee_cap)
        balance=client.balance()
        if int(balance['spendable_base_units'])<allocation*10**12:raise PolicyError('Deposit not confirmed spendable')
        state['funding'][scope]={'state':'FUNDED','allocation_micro_usdz':allocation,'deposits_sent':1,'result':result}
        persist()
    except Exception:
        state['funding'][scope]['state']='UNKNOWN';persist();raise


class CreditJournal:
    # A full short-prompt Haiku input window (100k) + 2,400 output tokens at the frozen rates.
    RESERVE=11200
    def __init__(self,state,persist,cap):self.state,self.persist,self.cap=state,persist,cap
    def before(self,task,quote):
        rows=self.state.setdefault('credits',{})
        if task.id in rows:raise PolicyError('An existing credit reservation cannot be repeated')
        exposure=sum(row.get('estimated_credit_micro_usd',self.RESERVE) for row in rows.values())
        if exposure+self.RESERVE>self.cap:raise PolicyError('Prepaid-credit cap cannot cover another call')
        rows[task.id]={'state':'RESERVED','reserved_credit_micro_usd':self.RESERVE};self.persist()
    def after(self,task,quote,receipt):
        metadata=receipt.get('provider_metadata') or {}
        row=self.state['credits'][task.id]
        row.update(receipt_id=receipt['id'],provider_micro_usdz=receipt['amount'])
        if metadata.get('provider_model')!='claude-haiku-5-5' or metadata.get('provider_type')!='ANTHROPIC_API':
            self.persist();raise PolicyError('Delivered API model changed; credit exposure retained')
        usage=metadata.get('usage')
        if not isinstance(usage,dict) or any(type(usage.get(key)) is not int or usage[key]<=0 for key in ('input_tokens','output_tokens')):
            row['state']='UNKNOWN';self.persist();raise PolicyError('API usage unavailable; credit exposure retained')
        cost=estimate_usage(metadata['provider_model'],metadata.get('usage') or {})
        value=cost['estimated_credit_micro_usd']
        row.update(estimated_credit_micro_usd=value,usage=metadata.get('usage'),billing_reconciled=False)
        if value>self.RESERVE:
            row['state']='UNKNOWN';self.persist();raise PolicyError('API cost exceeded reserved exposure; stop')
        row['state']='REPORTED';self.persist()


def run(plan,execute=False,approval=None):
    terms=plan['terms']
    if fingerprint(terms)!=plan['plan_sha256']:raise ValueError('Qualification plan changed')
    if not execute:return {'label':'BLOCKED','reason':'FINAL_APPROVAL_REQUIRED','approval_phrase':approval_phrase(plan),'terms':terms,'payments_sent':0}
    if approval!=approval_phrase(plan):raise ValueError('Exact approved qualification plan required')
    from tools.run_project import environment,health
    environment()
    if terms['code_sha256']!=code_hashes() or terms['driver_sha256']!=hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n',b'\n')).hexdigest():
        raise ValueError('Implementation changed after approval preparation')
    manifest,records,truth=load(terms['corpus'],include_truth=True)
    if manifest['sources_sha256']!=terms['corpus_sources_sha256']:raise ValueError('Frozen sources changed')
    seller=health(8093,'/health')
    if not (seller.get('provider_id')=='hosted-premium' and seller.get('provider_model')==terms['model'] and seller.get('inference_ready') is True):
        raise PolicyError('Configured premium seller is not ready')
    directory=ROOT/'data'/terms['scope'];directory.mkdir(parents=True,exist_ok=True)
    with exclusive(directory/'owner.sqlite'),exclusive(ROOT/'data/metal/qualification-funding.owner.sqlite'):
        path=directory/'journal.json'
        state=json.loads(path.read_text()) if path.exists() else {'plan_sha256':plan['plan_sha256'],'phase':'APPROVED','funding':{},'credits':{}}
        if state['plan_sha256']!=plan['plan_sha256']:raise ValueError('Scope belongs to a different plan')
        def persist():save(path,state)
        if state['phase'] in {'STOPPED','COMPLETE','INELIGIBLE'}:return state
        if (any(row['state']!='REPORTED' for row in state['credits'].values()) or
                any(row['state']!='FUNDED' for row in state['funding'].values())):
            state.update(phase='STOPPED',failure_type='UNRESOLVED_ORIGINAL_OPERATION');persist();return state
        credit=CreditJournal(state,persist,terms['prepaid_credit_cap_micro_usd'])
        persist()
        try:
            for partition,wallet,allocation,calls in [
                ('calibration',terms['calibration_wallet'],terms['calibration_allocation_micro_usdz'],120),
                ('holdout',terms['holdout_wallet'],terms['holdout_allocation_micro_usdz'],60)]:
                client=MetalRail(wallet,terms['provider_origin'],10000,allocation,execute=True)
                fund_once(client,wallet,allocation,state,persist,terms['maximum_native_fee_per_wallet_wei'])
                raw=paid(wallet,terms['provider_origin'],allocation,10000,calls,ROOT/terms['profile_output'],
                    execute=True,partition=partition,directory=directory/'profiles',corpus=terms['corpus'],
                    before_purchase=credit.before,after_purchase=credit.after)
                if raw.get('stop_reason') or raw.get('pending_attempts'):raise PolicyError('Paid profile stopped; no automatic continuation')
                evaluated=evaluate_profile(records,truth,raw,dataset_version=manifest['dataset_version'],corpus_sha256=manifest['sources_sha256'])
                state['evaluation']=evaluated;state['phase']=partition.upper()+'_DONE';persist()
                if partition=='calibration' and not evaluated['screen']['passes_statistical_screen']:
                    state['phase']='INELIGIBLE';persist();return state
            state['phase']='COMPLETE' if evaluated['eligible'] else 'INELIGIBLE';persist()
        except Exception as error:
            state['phase']='STOPPED';state['failure_type']=type(error).__name__;persist()
        return state


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--corpus',default='bench/results/m3-v2/dataset')
    parser.add_argument('--preflight',default='bench/results/m3-v2/cost-preflight.json')
    parser.add_argument('--plan',default='bench/results/m3-v2/qualification-plan.json')
    parser.add_argument('--execute',action='store_true');parser.add_argument('--approval')
    args=parser.parse_args()
    try:
        if args.action=='prepare':
            plan=prepare(args.corpus,args.preflight);save(args.plan,plan);result=run(plan)
        else:result=run(json.loads(Path(args.plan).read_text()),args.execute,args.approval)
        # Never print private funding responses or account identifiers.
        if args.execute:print(json.dumps({key:result.get(key) for key in ('phase','failure_type','evaluation')},indent=2))
        else:print(json.dumps(result,indent=2))
        return 0 if args.action=='prepare' or result.get('phase')=='COMPLETE' else 2
    except Exception as error:
        print(json.dumps({'label':'BLOCKED','failure_type':type(error).__name__,'notice':'Preserve original journals; nothing retries automatically'}));return 2


if __name__=='__main__':raise SystemExit(main())
