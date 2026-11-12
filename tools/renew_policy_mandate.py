"""One local-only renewal for the approved continuation; no bank or wallet operation."""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from tools.continue_policy_live import PLAN,DIRECTORY,approval_phrase,file_hash
from touchstone.comparison import fingerprint
from touchstone.leases import exclusive
from touchstone.ledger import Ledger


def renew(plan,execute=False,approval=None):
    if not execute or approval!=approval_phrase(plan) or fingerprint(plan['terms'])!=plan['plan_sha256']:
        raise ValueError('Exact already-approved continuation required before local renewal')
    terms=plan['terms']
    if any(file_hash(ROOT/name)!=digest for name,digest in terms['code_sha256'].items()):
        raise ValueError('Approved financial implementation differs')
    with exclusive(DIRECTORY/'owner.sqlite'),exclusive(ROOT/'data/metal'/terms['existing_wallet_only']/'m4-owner.sqlite'):
        state=json.loads((DIRECTORY/'journal.json').read_text())
        if state['continuation_approval_plan_sha256']!=plan['plan_sha256'] or len(state['rows'])!=12 or len(state['calls'])!=8:
            raise ValueError('Only the untouched initial continuation can be renewed')
        ledger=Ledger(DIRECTORY/'ledger.sqlite')
        if not ledger.audit()['valid'] or any(a['state'] in {'RESERVED','DISPATCHING','PAID'} for a in ledger.attempts()):
            raise ValueError('Unresolved original attempt; no mandate renewal')
        jobs=ledger.jobs(state['run_id'])
        if len(jobs)!=1:raise ValueError('One exact comparison mandate required')
        job=jobs[0];p=terms['effective_comparison_plan']
        if (job['mandate_version']!=1 or job['expires_at']>time.time()
            or job['budget']!=p['aggregate_cap_micro_usdz'] or job['hold']!=p['aggregate_cap_micro_usdz']
            or job['allocation']!=p['aggregate_cap_micro_usdz'] or job['price_cap']!=p['per_call_cap_micro_usdz']):
            raise ValueError('Renewal cannot alter the approved original limits or repeat a prior renewal')
        expires=time.time()+3600
        with ledger.tx() as db:
            db.execute('UPDATE jobs SET expires_at=?,mandate_version=mandate_version+1 WHERE id=?',(expires,job['id']))
            ledger._event(db,'APPROVED_CONTINUATION_LOCAL_MANDATE_RENEWED',{
                'approval_plan_sha256':plan['plan_sha256'],'old_expires_at':job['expires_at'],'expires_at':expires,
                'mandate_version':2,'scope':'LOCAL_COMPARISON_MANDATE_ONLY','bank_authorization_modified':False,
                'limits_changed':False,'financial_transactions':0,'inference_calls':0})
        return {'renewed':True,'mandate_version':2,'expires_at':expires,'limits_changed':False,
            'bank_operations':0,'financial_transactions':0,'inference_calls':0,'audit':ledger.audit()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--approval')
    args=parser.parse_args();print(json.dumps(renew(json.loads(PLAN.read_text()),args.execute,args.approval),indent=2))
