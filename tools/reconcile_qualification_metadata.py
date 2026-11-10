"""Restore discarded cost metadata from original deliveries. No pay/deposit/recover path."""
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.run_project import environment
from tools.run_invoice_qualification import approval_phrase,fingerprint
from touchstone.invoice_profile import save
from touchstone.invoice_study import code_hashes
from touchstone.ledger import Ledger,PolicyError
from touchstone.leases import exclusive
from touchstone.metal import MetalRail,MetalQuote
from touchstone.payments import MetalEngineRail


def reconcile(plan,approval):
    if approval!=approval_phrase(plan) or fingerprint(plan['terms'])!=plan['plan_sha256']:
        raise PolicyError('Exact original approved plan required')
    terms=plan['terms']
    if terms['code_sha256']!=code_hashes():raise PolicyError('Qualification criteria changed')
    directory=ROOT/'data'/terms['scope']
    with exclusive(directory/'owner.sqlite'):
        journal=directory/'journal.json';state=json.loads(journal.read_text())
        if state['plan_sha256']!=plan['plan_sha256'] or state['phase']!='STOPPED' or state['failure_type']!='PolicyError':
            raise PolicyError('Not the stopped metadata incident')
        profile_path=ROOT/terms['profile_output'];profile=json.loads(profile_path.read_text())
        if profile['stop_reason']!='RuntimeError' or profile['pending_attempts']:
            raise PolicyError('Only a fully delivered metadata failure can be reconciled')
        ledger=Ledger(directory/'profiles/ledger.sqlite');attempts=ledger.attempts()
        if (not attempts or not ledger.audit()['valid'] or len(attempts)!=len(profile['rows'])
                or len(attempts)!=len(state['credits']) or any(a['state'] not in {'VERIFIED_OK','VERIFIED_FAIL'} for a in attempts)):
            raise PolicyError('Original calls are not all independently resolved')
        environment()
        client=MetalRail(terms['calibration_wallet'],terms['provider_origin'],10000,
                         terms['calibration_allocation_micro_usdz'],execute=False)
        rail=MetalEngineRail(terms['calibration_wallet'],terms['provider_origin'],client=client,
                             expected_provider_ids=['hosted-premium'])
        restored=[]
        for attempt in attempts:
            credit=state['credits'][attempt['step_id']]
            row=next(r for r in profile['rows'] if r['reservation_key']==attempt['key'])
            original=rail.lookup(attempt['key'],MetalQuote(**json.loads(attempt['quote'])))
            metadata=original.get('provider_metadata') or {}
            if (original.get('state')!='PAID' or original['id']!=attempt['receipt']
                    or credit['state']!='REPORTED' or credit['receipt_id']!=original['id']
                    or original['output']!=json.loads(attempt['output'])
                    or metadata.get('provider_model')!=terms['model']
                    or metadata.get('provider_type')!='ANTHROPIC_API'
                    or metadata.get('funding_source')!='PARTNER_CREDITS_OPERATOR_DECLARED'
                    or metadata.get('usage')!=credit['usage']):
                raise PolicyError('Original delivery or credit evidence differs')
            ledger.record_paid(attempt['key'],original)
            current=next(a for a in ledger.attempts() if a['key']==attempt['key'])
            if current['provider_metadata'] is None:raise PolicyError('Ledger still rejected original metadata')
            row['provider_metadata']=json.loads(current['provider_metadata'])
            row['latency_ms']=metadata.get('latency_ms');row.pop('reference_or_followup_failed',None)
            restored.append(attempt['key'])
        observation={'observed_at':time.time(),'plan_sha256':plan['plan_sha256'],
            'reason':'Ledger whitelist omitted reproducible hosted_api_cost metadata; original delivery restored',
            'restored_original_keys':restored,'new_payments':0,'new_model_calls':0,'new_funding':0,
            'criteria_changed':False,'caps_changed':False,
            'ledger_sha256':hashlib.sha256((ROOT/'touchstone/ledger.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()}
        with ledger.tx() as db:ledger._event(db,'QUALIFICATION_METADATA_RESTORED',observation)
        profile['stop_reason']=None;profile['audit']=ledger.audit()
        for run in profile['runs']:run['stop_reason']=None;run['audit']=ledger.audit()
        save(profile_path,profile)
        state.setdefault('local_reconciliations',[]).append(observation)
        state.pop('failure_type',None);state['phase']='APPROVED';save(journal,state)
        save(ROOT/'bench/results/m3-v2/metadata-reconciliation.json',observation)
        return observation


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval',required=True)
    args=parser.parse_args()
    print(json.dumps(reconcile(json.loads((ROOT/'bench/results/m3-v2/qualification-plan.json').read_text()),args.approval),indent=2))
