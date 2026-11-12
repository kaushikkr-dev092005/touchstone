"""Amend only the approved credit ceiling; continue untouched real M4 outcomes."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.comparison import Comparison,credit_exposure,fingerprint,validate
from touchstone.invoice_profile import save
from touchstone.leases import exclusive
from touchstone.ledger import Ledger,PolicyError
from touchstone.metal import node_executable

PUBLIC=ROOT/'bench/results/m4-live-20261112'
ORIGINAL=ROOT/'data/m4/m4-qualified-20261110'
DIRECTORY=ROOT/'data/m4-live-20261112'
PLAN=PUBLIC/'continuation-plan.json'


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def amendment(original,prior_total,prior_comparison,total_ceiling):
    """The workload, schedule, models, wallet and USDZ/call limits stay bound."""
    if any(type(n) is not int or n<0 for n in (prior_total,prior_comparison,total_ceiling)):
        raise ValueError('Integer micro-USD ceilings required')
    if prior_comparison>prior_total or total_ceiling<prior_total:
        raise ValueError('Cannot erase existing credit exposure')
    result=deepcopy(original)
    result['hosted_credit_cap_micro_usd']=total_ceiling-(prior_total-prior_comparison)
    result.pop('plan_sha256')
    return {**result,'plan_sha256':fingerprint(result)}


def clearing(scope):
    child={k:v for k,v in os.environ.items() if not k.startswith(('AIRWALLEX_','ANTHROPIC_')) and k!='AGENT_PRIVATE_KEY'}
    process=subprocess.run([node_executable(),'integrations/metal/clearing-readiness.mjs',scope],cwd=ROOT,
        env=child,text=True,capture_output=True,timeout=45)
    if process.returncode:raise RuntimeError('Clearing readiness unavailable; no purchase dispatched')
    return json.loads(process.stdout)


def wait_for_clearing(scope,timeout=90):
    deadline=time.monotonic()+timeout
    while True:
        observation=clearing(scope)
        if observation.get('ready'):return observation
        print(json.dumps({'waiting_for_clearing':True,'read_only_check':True,'financial_transactions_this_check':0}),flush=True)
        if time.monotonic()>=deadline:raise PolicyError('Clearing unavailable; no payment attempted')
        time.sleep(5)


def prepare():
    from tools.run_project import environment
    environment()
    original=json.loads((ROOT/'bench/results/m4-v2/final-plan.json').read_text());validate(original)
    report=json.loads((ROOT/'bench/results/m4-v2/live-report.json').read_text())
    audit=json.loads((PUBLIC/'read-only-audit.json').read_text())
    if not audit['cost_preflight_complete'] or not audit['within_new_ceiling']:
        raise ValueError('Complete free cost preflight within the $4.50 total required')
    if audit['original_plan_sha256']!=original['plan_sha256'] or report['complete'] or len(report['rows'])!=12:
        raise ValueError('Original 12/64 live stop must be unchanged')
    effective=amendment(original,audit['prior_conservative_credit_exposure_micro_usd'],
        report['hosted_credit_exposure_micro_usd'],4500000)
    ledger=Ledger(ORIGINAL/'ledger.sqlite')
    if not ledger.audit()['valid'] or any(a['state'] in {'RESERVED','DISPATCHING','PAID'} for a in ledger.attempts()):
        raise ValueError('Original ledger is unresolved')
    runner=Comparison(effective,DIRECTORY)
    readiness=runner.preflight(report['confirmed_provider_micro_usdz'],sum(bool(a['receipt']) for a in ledger.attempts()))
    readiness['clearing']=wait_for_clearing(original['scope'])
    save(PUBLIC/'preflight.json',readiness)
    if not readiness['ready'] or not readiness['clearing']['ready']:
        raise ValueError('Current real sellers, quotes, wallet and clearing must pass before approval')
    terms={'original_plan_sha256':original['plan_sha256'],'effective_comparison_plan':effective,
        'total_claude_ceiling_micro_usd':4500000,
        'prior_noncomparison_credit_exposure_micro_usd':audit['prior_conservative_credit_exposure_micro_usd']-report['hosted_credit_exposure_micro_usd'],
        'prior_global_credit_exposure_micro_usd':audit['prior_conservative_credit_exposure_micro_usd'],
        'missing_outcomes':52,'maximum_new_purchase_attempts':39,'maximum_new_hosted_calls':27,
        'maximum_new_provider_micro_usdz':390000,'maximum_new_credit_estimate_micro_usd':audit['maximum_new_hosted_credit_estimate_micro_usd'],
        'existing_wallet_only':original['scope'],'new_funding_micro_usdz':0,'new_hosted_cash_micro_usd':0,
        'retries':0,'topups':0,'withdrawals':0,'bank_operations':0,'model_switching':False,
        'clearing_wait_timeout_seconds':90,'preserve_confirmed_unpaid_as_incorrect':True,
        'gpu_start_limit_c':65,'gpu_stop_limit_c':75,'automatic_thermal_restart':False,
        'original_journal_sha256':file_hash(ORIGINAL/'journal.json'),'original_audit_head':ledger.audit()['head'],
        'approval_basis':'User requests real completion and raises the total Claude guard to $4.50; final dispatch approval still required',
        'code_sha256':{name:file_hash(ROOT/name) for name in ['tools/continue_policy_live.py','integrations/metal/clearing-readiness.mjs','tools/run_local.py']}}
    plan={'terms':terms,'plan_sha256':fingerprint(terms)}
    save(PLAN,plan);return plan


def approval_phrase(plan):return 'APPROVE LIVE POLICY CONTINUATION '+plan['plan_sha256'][:16]


def guard_offers(policy,offers,plan,state,terms):
    original_keys=set(state['continuation_original_call_keys'])
    new=[call for key,call in state['calls'].items() if key not in original_keys]
    if policy=='always-cheapest':chosen=min(offers,key=lambda q:(q.price,q.provider)) if offers else None
    else:
        tier='hosted-premium'
        if policy=='touchstone-ladder' and plan['qualifications'].get('local-gpu',{}).get('eligible'):
            tier='local-gpu'
        chosen=next((offer for offer in offers if offer.provider==tier),None)
    if chosen and len(new)>=terms['maximum_new_purchase_attempts']:
        raise PolicyError('New purchase-attempt cap reached before reservation')
    if chosen and chosen.provider=='hosted-premium' and sum(c['provider']=='hosted-premium' for c in new)>=terms['maximum_new_hosted_calls']:
        raise PolicyError('New hosted-call cap reached before reservation')
    return offers


class LiveContinuation(Comparison):
    def __init__(self,plan,directory,terms):
        super().__init__(plan,directory)
        if not self.live:raise ValueError('Only the real Metal rail is allowed')
        self.terms=terms

    def step(self,row,policy,task,ledger,job,owner,rail,state,journal,readiness):
        from touchstone.telemetry import sample
        gpu=sample()
        if gpu.get('label')!='MEASURED' or gpu.get('temperature_c',100)>=75 or gpu.get('thermal_throttling_active'):
            raise PolicyError('GPU telemetry or thermal guard refused further dispatch')
        if policy!='tools-only':
            new_calls=len(state['calls'])-state['continuation_original_calls']
            if new_calls>=self.terms['maximum_new_purchase_attempts']:
                raise PolicyError('New purchase-attempt cap reached')
            wait_for_clearing(self.plan['scope'],self.terms['clearing_wait_timeout_seconds'])
        class BoundedQuotes:
            def quote_for_task(inner,requested):
                return guard_offers(policy,rail.quote_for_task(requested),self.plan,state,self.terms)
            def __getattr__(inner,name):return getattr(rail,name)
        result=super().step(row,policy,task,ledger,job,owner,BoundedQuotes(),state,journal,readiness)
        print(json.dumps({'completed_outcomes':len(state['rows'])+1,'expected':64,'policy':policy,
            'credit_exposure_micro_usd':self.terms['prior_noncomparison_credit_exposure_micro_usd']+credit_exposure(state['calls'])}),flush=True)
        return result


def bootstrap(plan):
    t=plan['terms']
    journal=DIRECTORY/'journal.json'
    if journal.exists():
        if json.loads(journal.read_text())['plan_sha256']!=t['effective_comparison_plan']['plan_sha256']:
            raise ValueError('Continuation directory belongs to another plan')
        return
    if file_hash(ORIGINAL/'journal.json')!=t['original_journal_sha256']:
        raise ValueError('Original outcomes changed after approval')
    old=Ledger(ORIGINAL/'ledger.sqlite')
    if not old.audit()['valid'] or old.audit()['head']!=t['original_audit_head']:
        raise ValueError('Original audit differs')
    target=DIRECTORY/'ledger.sqlite'
    if target.exists():raise ValueError('Partial bootstrap requires inspection; never overwrite its ledger')
    DIRECTORY.mkdir(exist_ok=True)
    with sqlite3.connect((ORIGINAL/'ledger.sqlite').as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(target) as destination:
        source.backup(destination)
    state=json.loads((ORIGINAL/'journal.json').read_text())
    state.update(plan_sha256=t['effective_comparison_plan']['plan_sha256'],stop_reason=None,
        continuation_original_calls=len(state['calls']),continuation_original_call_keys=list(state['calls']),
        continuation_approval_plan_sha256=plan['plan_sha256'])
    ledger=Ledger(target)
    with ledger.tx() as db:
        ledger._event(db,'COMPARISON_CREDIT_CEILING_AMENDED',{'approval_plan_sha256':plan['plan_sha256'],
            'original_plan_sha256':t['original_plan_sha256'],'total_claude_ceiling_micro_usd':4500000,
            'original_outcomes_retained':12,'wallet_unchanged':True,'new_funding':0})
    save(journal,state)


def publish_report(plan,report):
    report['continuation']={'approval_plan_sha256':plan['plan_sha256'],'original_live_outcomes':12,
        'new_live_outcomes':len(report['rows'])-12,'total_claude_ceiling_micro_usd':4500000,
        'global_credit_exposure_micro_usd':plan['terms']['prior_noncomparison_credit_exposure_micro_usd']+report['hosted_credit_exposure_micro_usd'],
        'new_funding_micro_usdz':0,'retries':0,'actual_rail':'METAL_TESTNET',
        'legacy_hypothetical_check_fees_excluded_from_actual_cost':True}
    save(PUBLIC/'live-report.json',report)
    from touchstone.comparison import table
    (PUBLIC/'comparison.md').write_text(table(report),encoding='utf-8')
    return report


def run(plan,execute=False,approval=None):
    # Authorization precedes credentials, sockets, directory creation and SDK access.
    if not execute or approval!=approval_phrase(plan) or fingerprint(plan['terms'])!=plan['plan_sha256']:
        raise ValueError('Explicit final live continuation approval and --execute required')
    t=plan['terms'];validate(t['effective_comparison_plan'])
    if any(file_hash(ROOT/name)!=digest for name,digest in t['code_sha256'].items()):
        raise ValueError('Approved continuation implementation changed')
    from tools.run_project import environment
    from tools.run_final_live_proofs import reconcile_unpaid
    environment()
    with exclusive(ORIGINAL/'owner.sqlite'):
        bootstrap(plan)
        runner=LiveContinuation(t['effective_comparison_plan'],DIRECTORY,t)
        for _ in range(t['maximum_new_purchase_attempts']+1):
            try:
                report=runner.run(True,runner.plan['aggregate_cap_micro_usdz'],runner.plan['max_purchases'],True)
                return publish_report(plan,report)
            except Exception:
                pending=[a for a in Ledger(DIRECTORY/'ledger.sqlite').attempts() if a['state'] in {'RESERVED','DISPATCHING','PAID'}]
                if len(pending)!=1 or pending[0]['receipt']:
                    publish_report(plan,runner.report());raise
                # No retry: inspect the pinned SDK's original request. Only a
                # definitively unpaid trial is voided and counted as incorrect.
                with exclusive(DIRECTORY/'owner.sqlite'),exclusive(runner.wallet_owner):
                    reconcile_unpaid(runner,runner.client(execute=False),DIRECTORY/'journal.json')
                print(json.dumps({'confirmed_unpaid_counted_incorrect':True,'request_retried':False}),flush=True)
        raise PolicyError('Bounded continuation exhausted; inspect original state')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--execute',action='store_true');parser.add_argument('--approval')
    args=parser.parse_args()
    if args.action=='prepare':
        p=prepare();print(json.dumps({'plan_sha256':p['plan_sha256'],'approval_phrase':approval_phrase(p),
            'missing_outcomes':p['terms']['missing_outcomes'],'maximum_new_purchase_attempts':39,
            'maximum_new_hosted_calls':27,'maximum_new_provider_micro_usdz':390000,
            'total_claude_ceiling_micro_usd':4500000,'new_funding_micro_usdz':0},indent=2))
    else:
        p=json.loads(PLAN.read_text());r=run(p,args.execute,args.approval)
        print(json.dumps({k:r[k] for k in ('complete','live_gate_passed','pending_attempts','control_violations','continuation')},indent=2))
