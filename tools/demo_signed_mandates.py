"""Real ephemeral human signatures, MOCK rail only. No external calls or secrets."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_procurement_approval import EphemeralSigner
from touchstone.ledger import Ledger
from touchstone.payments import MockRail
from touchstone.procurement_approval import ApprovalError, ApprovalStore, node_verify
from touchstone.providers import Quote
from touchstone.workload import Task
import time


def demonstrate():
    with tempfile.TemporaryDirectory(prefix='touchstone-human-gate-') as directory:
        root=Path(directory);signer=EphemeralSigner()
        try:
            ledger=Ledger(root/'ledger.sqlite');rail=MockRail(root/'rail.sqlite')
            cfg={'environment':'LOCAL_TEST_DEMONSTRATION','chain_id':31337,'salt':'0x'+secrets.token_hex(32),
                 'signers':[signer.addresses[0]],'agent_addresses':[signer.addresses[1]],
                 'ledger_paths':[str(Path(ledger.path).resolve())],'api_credit_max':0}
            registry=root/'approvers.json';registry.write_text(json.dumps(cfg))
            with patch.dict(os.environ,{'TOUCHSTONE_APPROVAL_CONFIG':str(registry),'TOUCHSTONE_IGNORE_LOCAL_CONFIG':'1'}):
                task=Task('signed-demo','arithmetic',{'amounts_cents':[1250,750],'discount_cents':0})
                run=ledger.create_run([{'seed':0,'policy':'always-premium','hold':100000,'allocation':100000,
                    'price_cap':50000,'tasks':[task.public()]}],100000,require_approvals=True)
                job=ledger.jobs(run)[0]
                quote=Quote('mock-premium-quote','premium',10000,0,time.time()+240)
                key=ledger.reserve(job['id'],task,0,quote,1000)
                challenge=ledger.prepare_approval(key)
                try:ledger.assert_can_pay(key);raise AssertionError('Unsigned dispatch accepted')
                except ApprovalError as error:unsigned={'decision':error.code,'adapter_calls':len(rail.receipts())}
                signed=ledger.approvals.submit(challenge['id'],signer.sign(challenge))
                with ledger.worker(job['id']) as owner:
                    auth=ledger.assert_can_pay(key,owner)
                    receipt=rail.pay(key,quote,lambda:{'total_cents':2000})
                    ledger.record_paid(key,receipt)
                changed={**challenge['terms'],'provider_id':'tampered-provider'}
                try:ApprovalStore.compare(challenge['terms'],changed);raise AssertionError('Tamper accepted')
                except ApprovalError as error:tampered={'decision':error.code,'additional_adapter_calls':len(rail.receipts())-1}
                try:node_verify(changed, signed['signature'], challenge['expected_signer']);raise AssertionError('Tampered signature verified')
                except ApprovalError:
                    tampered['original_signature_valid_for_tampered_terms']=False
                ledger.event('PROCUREMENT_TAMPER_BLOCKED',{'purchase_key':key,'code':'TERMS_MISMATCH','additional_payments':0})
                result={'label':'MOCK / LOCAL TEST','real_external_financial_operations':0,'hosted_inference_calls':0,
                    'signature_scheme':'REAL EIP-712 EOA SIGNATURE WITH EPHEMERAL TEST HUMAN',
                    'unsigned':unsigned,'signed':{'decision':'AUTHORIZED','adapter_calls':len(rail.receipts()),
                    'signer':challenge['expected_signer'],'approval_digest':challenge['digest'],'purchase_key':key,
                    'receipt_id':receipt['id'],'verification':json.loads(signed['verification'])},
                    'tampered':tampered,'original_terms_unchanged':ledger.approvals.list()[0]['terms']==challenge['terms'],
                    'authorization':ledger.approvals.list()[0],
                    'audit':ledger.audit(),'audit_export':'SUMMARY_AND_APPROVAL_EVENTS_ONLY',
                    'events':[e for e in ledger.events(limit=100) if e['kind'].startswith('PROCUREMENT_') or e['kind']=='PAID'],
                    'historical_transactions_relabelled':False}
                assert unsigned['adapter_calls']==0 and tampered['additional_adapter_calls']==0 and result['audit']['valid']
                return result
        finally:signer.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=demonstrate()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
