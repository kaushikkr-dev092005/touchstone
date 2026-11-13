"""One approved local testnet call from existing funds; never funds, transfers or retries."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.validation_status import paid_preflight
from touchstone.ledger import Ledger,canonical
from touchstone.leases import exclusive
from touchstone.metal import MetalRail,PaymentPending
from touchstone.payments import MetalEngineRail
from touchstone.workload import Task
from touchstone.verifier import check

TASK=Task('approval-local-probe-001','arithmetic',{'amounts_cents':[1250,775],'discount_cents':25})
CAP=10000


def approval_phrase(wallet,scope='final-local-probe-20261110'):
    digest=hashlib.sha256(json.dumps(TASK.public(),sort_keys=True).encode()).hexdigest()[:12]
    return f'APPROVE ONE LOCAL TESTNET CALL scope={scope} wallet={wallet} cap=0.010000 USDZ task={digest}'


def run(wallet,scope,*,execute=False,approval=None,directory=None,reader=None,client_factory=MetalRail,preflight=paid_preflight):
    import re
    if not all(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,48}',value) for value in (wallet,scope)):
        raise ValueError('Valid existing wallet and immutable operation scope required')
    if not execute:
        return {'label':'BLOCKED','reason':'FINAL_APPROVAL_REQUIRED','payments_sent':0,
                'approval_phrase':approval_phrase(wallet,scope)}
    if approval!=approval_phrase(wallet,scope):raise ValueError('Exact final approval phrase required')
    directory=Path(directory or ROOT/'data/capped-probe')
    terms={'scope':scope,'wallet':wallet,'task':TASK.public(),'maximum_calls':1,'maximum_micro_usdz':CAP,
           'hosted_spend_micro_usd':0,'hosted_credits_authorized':False,'transfers_authorized':False}
    with exclusive(directory/'aggregate-approval.owner.sqlite'):
        ledger=Ledger(directory/'ledger.sqlite')
        with ledger.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS capped_probes(scope TEXT PRIMARY KEY,terms TEXT NOT NULL,run_id TEXT NOT NULL)')
            previous=db.execute('SELECT terms,run_id FROM capped_probes WHERE scope=?',(scope,)).fetchone()
        if previous and previous['terms']!=canonical(terms):raise ValueError('Scope is bound to different purchase terms')
        run_id=previous['run_id'] if previous else None
        job=ledger.jobs(run_id)[0] if run_id else None
        def report(replayed=False,error=None):
            attempts=ledger.attempts(job['id'])
            rows=[{'key':a['key'],'state':a['state'],'actual_provider_micro_usdz':a['price'] if a['receipt'] else None,
                'transaction_id':a['receipt'],'transaction_id_type':'CLEARING_RECEIPT_NOT_ONCHAIN_TRANSACTION',
                'verification_result':json.loads(a['verdict']) if a.get('verdict') else None,
                'output':json.loads(a['output']) if a.get('output') else None} for a in attempts]
            return {'label':evidence_label,'purpose':'SINGLE_LOCAL_PROTOCOL_PROBE_NOT_MODEL_QUALIFICATION',
                'terms':terms,'paid_calls':rows,'additional_provider_micro_usdz':sum(a['price'] for a in attempts if a['receipt']),
                'possible_unresolved_exposure_micro_usdz':sum(a['price'] for a in attempts if a['state'] in {'RESERVED','DISPATCHING','PAID'}),
                'idempotent_report_replay':replayed,'failure_type':error,'audit':ledger.audit(),
                'hosted_inference_calls':0,'transfers_sent':0,'deposits_sent':0,'automatic_retries':0,
                'receipt_assurance':'PRECONFIRMED_NOT_INDEPENDENT_FINAL_SETTLEMENT'}
        evidence_label='MEASURED' if client_factory is MetalRail else 'MOCK'
        if job:
            existing=ledger.attempts(job['id'])
            if existing:
                if all(a['state'] in {'VERIFIED_OK','VERIFIED_FAIL'} for a in existing):return report(True)
                raise PaymentPending('Original outcome unresolved; no retry, recovery or replacement is automatic')
        exposure=sum(a['price'] for a in ledger.attempts() if a['state']!='VOID')
        if exposure+CAP>1000000:raise ValueError('Aggregate 1.00 USDZ cap exhausted, including unresolved attempts')
        checked=preflight(wallet,reader=reader,client_factory=client_factory)
        if not checked.get('ready_for_final_approval'):raise ValueError('Fresh read-only preflight did not pass')
        client=client_factory(wallet,'http://127.0.0.1:8092',CAP,1000000,execute=True)
        history=client.invoke('receipts')
        prior=0
        for row in history:
            receipt=row.get('receipt')
            if receipt:
                amount=int(receipt['invoice']['amount'])
                if amount<0 or amount%10**12:raise ValueError('Historical charge cannot be accounted for')
                prior+=amount//10**12
        # SDK budget includes historical receipts; the new ledger authorizes only this one call.
        client.budget=prior+CAP
        rail=MetalEngineRail(wallet,'http://127.0.0.1:8092',CAP,prior+CAP,client=client,expected_provider_ids=['local-gpu'])
        offers=rail.quote_for_task(TASK)
        if len(offers)!=1 or not 0<offers[0].price<=CAP:raise ValueError('No fresh local quote within the exact cap')
        quote=offers[0]
        if not run_id:
            run_id=ledger.create_run([{'seed':0,'policy':'metal-probe','hold':CAP,'allocation':CAP,
                'price_cap':CAP,'tasks':[TASK.public()]}],CAP,float_mode='TESTNET')
            with ledger.tx() as db:db.execute('INSERT INTO capped_probes VALUES(?,?,?)',(scope,canonical(terms),run_id))
            job=ledger.jobs(run_id)[0]
        try:
            with ledger.worker(job['id']) as owner:
                key=ledger.reserve(job['id'],TASK,0,quote,0)
                from touchstone.procurement_approval import bind_dispatch
                if ledger.approval_required(key):ledger.prepare_approval(key)
                bind_dispatch(rail,ledger.assert_can_pay(key,owner))
                receipt=rail.pay(key,quote)
                ledger.record_paid(key,receipt)
                verdict=check(TASK,receipt['output'])
                ledger.finish_attempt(key,receipt['output'],verdict)
            return report()
        except Exception as error:
            return report(error=type(error).__name__)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wallet',required=True)
    parser.add_argument('--scope',default='final-local-probe-20261110')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--approval')
    parser.add_argument('--output',default='bench/results/completion-20261110/local-paid-probe.json')
    args=parser.parse_args()
    from tools.run_project import environment,health
    environment()
    try:
        result=run(args.wallet,args.scope,execute=args.execute,approval=args.approval,reader=health)
    except Exception as error:
        result={'label':'BLOCKED','failure_type':type(error).__name__,'payments_sent':0,
                'notice':'Preserve any existing reservation and inspect its journal before recovery; nothing retries automatically'}
    target=ROOT/args.output;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if result.get('paid_calls') and not result.get('failure_type') else 2


if __name__=='__main__':raise SystemExit(main())
