"""No network or financial credentials. Real viem signatures; only MOCK payments."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import io
import os
from pathlib import Path
import secrets
import sqlite3
import socket
import re
import subprocess
import tempfile
import time
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

from touchstone.config import ROOT
from touchstone.engine import Engine, InjectedCrash
from touchstone.ledger import Ledger, PolicyError
from touchstone.metal import node_executable, MetalRail, MetalQuote
from touchstone.payments import MockRail
from touchstone.procurement_approval import ApprovalError, canonical, digest, node_verify, strict_json
from touchstone.providers import Quote
from touchstone.workload import Task


class EphemeralSigner:
    def __init__(self):
        self.lock=threading.Lock()
        self.process = subprocess.Popen([node_executable(), str(ROOT/'tests/procurement_signer.mjs')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={k:v for k,v in os.environ.items() if not k.startswith(('ANTHROPIC_','AIRWALLEX_','METAL_')) and k!='AGENT_PRIVATE_KEY'})
        self.addresses = json.loads(self.process.stdout.readline())['addresses']

    def sign(self, challenge, account=0):
        with self.lock:
            self.process.stdin.write(json.dumps({'data': challenge['typed_data'], 'account': account})+'\n')
            self.process.stdin.flush()
            return json.loads(self.process.stdout.readline())['signature']

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=5)
        self.process.stdout.close()
        self.process.stderr.close()


class ProcurementApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.signer = EphemeralSigner()

    @classmethod
    def tearDownClass(cls): cls.signer.close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = Ledger(self.root/'ledger.sqlite')
        self.cfg = {'environment':'LOCAL_TEST', 'chain_id':31337, 'salt':'0x'+secrets.token_hex(32),
                    'signers':[self.signer.addresses[0]], 'agent_addresses':[self.signer.addresses[1]],
                    'ledger_paths':[str(Path(self.ledger.path).resolve())], 'api_credit_max':0}
        self.config = self.root/'approvers.json'
        self.config.write_text(json.dumps(self.cfg))
        self.env = patch.dict(os.environ, {'TOUCHSTONE_APPROVAL_CONFIG':str(self.config), 'TOUCHSTONE_IGNORE_LOCAL_CONFIG':'1'})
        self.env.start(); self.addCleanup(self.env.stop)
        self.task = Task('task-1','arithmetic',{'amounts_cents':[1250,750], 'discount_cents':0})
        run = self.ledger.create_run([{'seed':42,'policy':'always-premium','hold':200000,'price_cap':50000,
            'allocation':200000,'tasks':[self.task.public()]}],200000,require_approvals=True)
        self.job = self.ledger.jobs(run)[0]
        self.quote = Quote('q-1','premium',10000,1,time.time()+240)
        self.key = self.ledger.reserve(self.job['id'],self.task,0,self.quote,1000)
        self.rail = MockRail(self.root/'rail.sqlite')

    def approved(self):
        challenge = self.ledger.prepare_approval(self.key)
        self.ledger.approvals.submit(challenge['id'], self.signer.sign(challenge))
        return challenge

    def error(self, code, function, *args, **kwargs):
        with self.assertRaises(ApprovalError) as result: function(*args, **kwargs)
        self.assertEqual(result.exception.code, code)

    def test_unsigned_blocks_and_audits_without_payment(self):
        self.ledger.prepare_approval(self.key)
        self.error('APPROVAL_REQUIRED',self.ledger.assert_can_pay,self.key)
        self.assertEqual(self.rail.receipts(),[])
        self.assertIn('PROCUREMENT_APPROVAL_BLOCKED',[r['kind'] for r in self.ledger.events()])

    def test_exact_signature_consumed_once_and_mock_paid(self):
        c = self.approved()
        auth = self.ledger.assert_can_pay(self.key)
        self.assertEqual(auth['approval_id'],c['id'])
        receipt = self.rail.pay(self.key,self.quote,lambda:{'total_cents':2000})
        self.ledger.record_paid(self.key,receipt)
        row = self.ledger.approvals.list()[0]
        self.assertEqual(row['state'],'CONSUMED_AT_DISPATCH')
        self.assertEqual(row['consuming_key'],self.key)
        self.assertEqual(json.loads(row['verification'])['signer'],self.signer.addresses[0].lower())
        with self.assertRaises(PolicyError): self.ledger.assert_can_pay(self.key)
        self.assertEqual(len(self.rail.receipts()),1)

    def test_agent_key_rejected(self):
        c=self.ledger.prepare_approval(self.key)
        self.error('AGENT_SIGNER_FORBIDDEN',self.ledger.approvals.submit,c['id'],self.signer.sign(c,1))

    def test_untrusted_wallet_rejected(self):
        c=self.ledger.prepare_approval(self.key)
        self.error('SIGNER_UNTRUSTED',self.ledger.approvals.submit,c['id'],self.signer.sign(c,2))

    def test_invalid_signature_does_not_dispatch(self):
        c=self.ledger.prepare_approval(self.key)
        self.error('INVALID_SIGNATURE',self.ledger.approvals.submit,c['id'],'0x00')
        self.assertEqual(self.ledger.attempts()[0]['state'],'RESERVED')
        self.assertEqual(self.rail.receipts(),[])

    def test_all_material_fields_bound(self):
        c=self.approved()
        fields={'task_hash':'0x'+'ab'*32,'provider_id':'evil','provider_origin':'https://evil.invalid',
                'quote_id':'q-2','quoted_amount':10001,'max_amount':50001,'job_ceiling':200001,
                'allocation':200001,'verifier_version':'weaker','verifier_policy_digest':'0x'+'cd'*32,
                'environment':'LOCAL_TEST_OTHER','network':'eip155:1','payer_scope':'other','purchase_key':'other',
                'api_credit_max':100,'fee_max':0,'mandate_version':2}
        from touchstone.procurement_approval import ApprovalStore
        signature=self.signer.sign(c)
        for field,value in fields.items():
            with self.subTest(field=field):
                changed={**c['terms'],field:value}
                self.error('TERMS_MISMATCH',ApprovalStore.compare,c['terms'],changed)
                # Exercise actual EIP-712 verification for each changed field,
                # independently of the authoritative-term comparison.
                with self.assertRaises(ApprovalError):node_verify(changed,signature,c['expected_signer'])
        self.assertEqual(self.rail.receipts(),[])

    def test_budget_modified_in_database_blocks_dispatch(self):
        self.approved()
        with self.ledger.tx() as db: db.execute('UPDATE jobs SET price_cap=price_cap+1 WHERE id=?',(self.job['id'],))
        self.error('TERMS_MISMATCH',self.ledger.assert_can_pay,self.key)

    def test_task_modified_in_database_blocks_dispatch(self):
        self.approved()
        task={**self.task.public(),'source':{'amounts_cents':[1], 'discount_cents':0}}
        with self.ledger.tx() as db: db.execute('UPDATE jobs SET tasks=? WHERE id=?',(json.dumps([task]),self.job['id']))
        self.error('TERMS_MISMATCH',self.ledger.assert_can_pay,self.key)

    def test_quote_changes_require_reapproval(self):
        self.approved()
        for field,value in [('id','changed'),('price',10001)]:
            with self.subTest(field=field):
                raw={**self.quote.public(),field:value}
                with self.ledger.tx() as db: db.execute('UPDATE attempts SET quote=? WHERE key=?',(json.dumps(raw),self.key))
                self.error('TERMS_MISMATCH',self.ledger.assert_can_pay,self.key)

    def test_verifier_code_change_blocks_dispatch(self):
        self.approved()
        with patch('touchstone.procurement_approval.verifier_policy',return_value=('weaker','0x'+'00'*32)):
            self.error('TERMS_MISMATCH',self.ledger.assert_can_pay,self.key)

    def test_mandate_version_change_blocks(self):
        self.approved()
        with self.ledger.tx() as db: db.execute('UPDATE jobs SET mandate_version=2 WHERE id=?',(self.job['id'],))
        self.error('MANDATE_VERSION_MISMATCH',self.ledger.assert_can_pay,self.key)

    def test_expired_approval_blocks(self):
        self.approved()
        with patch('touchstone.procurement_approval.time.time',return_value=time.time()+250):
            with self.assertRaises(ApprovalError): self.ledger.assert_can_pay(self.key)

    def test_revoked_approval_blocks(self):
        c=self.approved(); self.ledger.approvals.revoke(c['id'])
        self.error('APPROVAL_REVOKED',self.ledger.assert_can_pay,self.key)

    def test_duplicate_nonce_rejected_by_database(self):
        c=self.ledger.prepare_approval(self.key)
        terms={**c['terms'],'purchase_key':'another'}
        with self.assertRaises(sqlite3.IntegrityError): self.ledger.approvals.prepare(terms)

    def test_cross_purchase_replay_rejected(self):
        self.approved();self.ledger.assert_can_pay(self.key)
        with self.ledger.tx() as db:
            terms=self.ledger._approval_terms(db,self.key)
            terms['purchase_key']='different'
            self.error('APPROVAL_REQUIRED',self.ledger.approvals.consume,db,'different',terms)

    def test_concurrent_dispatch_only_one_wins(self):
        self.approved()
        def dispatch(_):
            try: self.ledger.assert_can_pay(self.key);return True
            except PolicyError:return False
        with ThreadPoolExecutor(2) as pool: result=list(pool.map(dispatch,range(2)))
        self.assertEqual(sum(result),1)
        self.assertEqual(self.ledger.approvals.list()[0]['state'],'CONSUMED_AT_DISPATCH')

    def test_restart_preserves_signature_and_audit(self):
        c=self.approved(); ledger=Ledger(self.ledger.path)
        self.assertEqual(ledger.approvals.list()[0]['id'],c['id'])
        ledger.assert_can_pay(self.key)
        self.assertTrue(ledger.audit()['valid'])

    def test_recovery_after_rail_crash_needs_no_new_signature(self):
        self.approved();self.ledger.assert_can_pay(self.key)
        self.rail.pay(self.key,self.quote,lambda:{'total_cents':2000})
        restarted=Ledger(self.ledger.path)
        Engine(restarted,self.rail).recover()
        self.assertEqual(len(self.rail.receipts()),1)
        self.assertEqual(restarted.attempts()[0]['state'],'VERIFIED_OK')
        self.assertTrue(restarted.audit()['valid'])

    def test_crash_before_rail_does_not_dispatch_again(self):
        self.approved(); self.ledger.assert_can_pay(self.key)
        Engine(Ledger(self.ledger.path),self.rail).recover()
        self.assertEqual(self.rail.receipts(),[])
        self.assertEqual(self.ledger.approvals.list()[0]['state'],'CONSUMED_AT_DISPATCH')
        with self.assertRaises(PolicyError): self.ledger.assert_can_pay(self.key)

    def test_domain_salt_change_invalidates_signature(self):
        c=self.approved();self.cfg['salt']='0x'+secrets.token_hex(32);self.config.write_text(json.dumps(self.cfg))
        with self.assertRaises(ApprovalError): self.ledger.assert_can_pay(self.key)

    def test_strict_types_and_unknown_fields_rejected(self):
        c=self.ledger.prepare_approval(self.key)
        from touchstone.procurement_approval import validate_terms
        for changed in ({**c['terms'],'quoted_amount':True},{**c['terms'],'quoted_amount':'10000'},
                        {**c['terms'],'approved':True}):
            self.error('MALFORMED_APPROVAL',validate_terms,changed)
        self.error('MALFORMED_APPROVAL',strict_json,'{"id":"a","id":"b"}')

    def test_direct_python_pay_cannot_bypass(self):
        calls=[]
        with patch.dict(os.environ,{'METAL_RPC_URL':'https://rpc.invalid'}):
            rail=MetalRail('local-test','https://provider.invalid',transport=lambda x:calls.append(x),execute=True)
            self.error('APPROVAL_REQUIRED',rail.invoke,'pay',id='p',quote={},approved=True)
        self.assertEqual(calls,[])

    def test_direct_bridge_unsigned_fails_before_network(self):
        r=subprocess.run([node_executable(),str(ROOT/'integrations/metal/bridge.mjs')],input=json.dumps({'command':'pay','job':'local-test','execute':True}),text=True,capture_output=True)
        self.assertEqual(json.loads(r.stdout)['error'],'APPROVAL_REQUIRED')

    def test_mock_demo_still_runs_without_signatures(self):
        ledger=Ledger(self.root/'legacy.sqlite');rail=MockRail(self.root/'legacy-rail.sqlite')
        engine=Engine(ledger,rail);run=engine.create_demo(count=3);engine.run(run)
        self.assertTrue(rail.receipts())
        self.assertEqual(ledger.approvals.list(),[])

    def test_engine_pauses_then_resumes_exact_signed_quote(self):
        # Existing reservation must survive Engine.recover while a human signs.
        self.ledger.prepare_approval(self.key)
        engine=Engine(self.ledger,self.rail);engine.run(self.job['run_id'])
        self.assertEqual(self.ledger.get_job(self.job['id'])['status'],'PAUSED_APPROVAL')
        self.assertFalse(self.rail.receipts())
        self.approved();self.ledger.resume();engine.run(self.job['run_id'])
        self.assertEqual(len(self.rail.receipts()),1)
        self.assertEqual(self.ledger.get_job(self.job['id'])['status'],'COMPLETED')

    def test_historical_reserved_receipt_recovers_without_retrospective_signature(self):
        self.rail.pay(self.key,self.quote,lambda:{'total_cents':2000})
        Engine(Ledger(self.ledger.path),self.rail).recover()
        self.assertEqual(self.ledger.attempts()[0]['state'],'VERIFIED_OK')
        self.assertEqual(len(self.rail.receipts()),1)
        self.assertEqual(self.ledger.approvals.list(),[])

    def test_canonical_matches_node(self):
        values=[self.task.public(),{'ü':'😀','a':[1.0,1e-7,True,None,-0.0,{'z':3}]},self.quote.public()]
        script="import {digest} from './integrations/metal/procurement-approval.mjs';let s='';for await(const c of process.stdin)s+=c;console.log(JSON.stringify(JSON.parse(s).map(digest)));"
        r=subprocess.run([node_executable(),'--input-type=module','-e',script],input=json.dumps(values),text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(json.loads(r.stdout),list(map(digest,values)))

    def test_protected_node_payer_requires_consumed_exact_terms_and_blocks_replay(self):
        self.cfg['chain_id']=63825;self.config.write_text(json.dumps(self.cfg))
        run=self.ledger.create_run([{'seed':0,'policy':'real-premium','hold':100000,'allocation':100000,
            'price_cap':50000,'tasks':[self.task.public()]}],100000,float_mode='TESTNET')
        job=self.ledger.jobs(run)[0]
        raw={'url':'https://provider.invalid/inference/task','provider_id':'hosted-premium',
             'offer':{'amount':str(10000*10**12)},'expires_at':int((time.time()+240)*1000)}
        quote=MetalQuote('node-quote','hosted-premium',10000,raw['expires_at']/1000,raw,payer_scope='node-gate')
        key=self.ledger.reserve(job['id'],self.task,0,quote,0)
        challenge=self.ledger.prepare_approval(key)
        signature=self.signer.sign(challenge);self.ledger.approvals.submit(challenge['id'],signature)
        auth={'ledger_path':self.ledger.path,'approval_id':challenge['id'],'purchase_key':key}
        script="""import { DatabaseSync } from 'node:sqlite';
import {dispatchApproval} from './integrations/metal/procurement-approval.mjs';
let s='';for await(const c of process.stdin)s+=c;const r=JSON.parse(s);
const db=new DatabaseSync(r.wallet);try{await dispatchApproval({db},r.id,r.q,r.auth,
 {directory:'node-gate',maximum:50000n*10n**12n,budget:100000n*10n**12n});console.log(JSON.stringify({code:'AUTHORIZED'}));}
catch(e){console.log(JSON.stringify({code:e.code||'ERROR'}));}finally{db.close();}"""
        def check(q=raw):
            r=subprocess.run([node_executable(),'--input-type=module','-e',script],
                input=json.dumps({'q':q,'id':key,'auth':auth,'wallet':str(self.root/'dispatch.sqlite')}),
                text=True,capture_output=True,cwd=ROOT)
            return json.loads(r.stdout)['code']
        self.assertEqual(check(),'APPROVAL_REQUIRED')
        auth=self.ledger.assert_can_pay(key)
        self.assertNotIn('dispatch_token',self.ledger.approvals.list()[0])
        self.assertNotIn('dispatch_token_hash',self.ledger.approvals.list()[0])
        original=auth['dispatch_token'];auth['dispatch_token']='00'*32
        self.assertEqual(check(),'APPROVAL_REQUIRED')
        auth['dispatch_token']=original
        self.assertEqual(check({**raw,'offer':{'amount':str(10001*10**12)}}),'TERMS_MISMATCH')
        self.assertEqual(check({**raw,'url':'https://evil.invalid/inference/task'}),'TERMS_MISMATCH')
        self.assertEqual(check({**raw,'provider_id':'local-gpu'}),'TERMS_MISMATCH')
        self.assertEqual(check(),'AUTHORIZED')
        self.assertEqual(check(),'APPROVAL_ALREADY_CONSUMED')
        self.assertEqual(self.rail.receipts(),[])

    def test_banked_workflow_has_independent_signature_gate_and_recovers_paid_receipt(self):
        from test_banked import FixtureRail
        from test_holds import FakeAirwallex
        from touchstone.banked import BankedStore,BankedWorkflow
        from touchstone.holds import SandboxHoldWorkflow,OperationJournal
        store=BankedStore(self.root/'banked.sqlite',self.root/'owner.sqlite')
        self.cfg['chain_id']=63825;self.cfg['ledger_paths'].append(str(Path(store.ledger.path).resolve()))
        self.config.write_text(json.dumps(self.cfg))
        rail=FixtureRail();rail.mode='TESTNET';rail.authorize_purchase=lambda auth:None
        treasury=SandboxHoldWorkflow(FakeAirwallex(),OperationJournal(self.root/'bank.sqlite'))
        workflow=BankedWorkflow(store,treasury,rail.factory)
        def run(recover=False):
            return workflow.run('human-banked',self.task,'http://127.0.0.1:8092',integration_probe=True,
                                allow_funding=False,return_float=False,recover=recover)
        blocked=run()
        self.assertEqual(blocked['phase'],'PAUSED_APPROVAL');self.assertEqual(rail.payments,0)
        challenge=store.ledger.approvals.list()[0]
        store.ledger.approvals.submit(challenge['id'],self.signer.sign(challenge))
        rail.lose_pay=True
        interrupted=run()
        self.assertTrue(interrupted['recovery_required'])
        self.assertEqual(rail.payments,1)
        recovered=run(True)
        self.assertEqual(recovered['phase'],'CLOSED_FLOAT_RETAINED')
        self.assertEqual(rail.payments,1)
        self.assertEqual(store.ledger.approvals.list()[0]['state'],'CONSUMED_AT_DISPATCH')

    def test_secured_api_rejects_fake_approval_and_tampering(self):
        directory=self.root/'api';directory.mkdir()
        self.cfg['ledger_paths'].append(str((directory/'ledger.sqlite').resolve()))
        self.config.write_text(json.dumps(self.cfg))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        process=subprocess.Popen([node_executable(),'--version'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        process.communicate(timeout=10)  # No browser or remote wallet needed for API test.
        import sys
        child=subprocess.Popen([sys.executable,'-c',f'from touchstone.server import serve;serve({port},{str(directory)!r})'],
            cwd=ROOT,env=os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(lambda:(child.terminate(),child.communicate(timeout=10)))
        base=f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                page=urllib.request.urlopen(base,timeout=1).read().decode();break
            except OSError:time.sleep(.05)
        else:self.fail('Local API failed to start')
        token=re.search(r'name="touchstone-token" content="([^"]+)"',page)[1]
        def api(path,body=None,headers=None):
            req=urllib.request.Request(base+'/api/procurement/'+path,data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type':'application/json','X-Touchstone-Token':token,**(headers or {})})
            try:
                with urllib.request.urlopen(req,timeout=20) as r:return r.status,json.load(r)
            except urllib.error.HTTPError as r:return r.code,json.load(r)
        self.assertEqual(api('approvals',headers={'X-Touchstone-Token':'wrong'})[0],403)
        self.assertEqual(api('local-proposal',{},headers={'Origin':'https://evil.invalid'})[0],403)
        code,bad=api('prepare-approval',{'purchase_key':self.key,'approved':True})
        self.assertEqual((code,bad['code']),(400,'MALFORMED_APPROVAL'))
        code,c=api('local-proposal',{});self.assertEqual(code,200)
        self.assertEqual(api('dispatch-mock',{'id':c['id']})[1]['code'],'APPROVAL_REQUIRED')
        self.assertEqual(api('submit-signature',{'id':c['id'],'signature':self.signer.sign(c)})[0],200)
        changed={**c['terms'],'provider_id':'evil'}
        self.assertEqual(api('verify-terms',{'id':c['id'],'terms':changed})[1]['code'],'TERMS_MISMATCH')
        code,paid=api('dispatch-mock',{'id':c['id']})
        self.assertEqual(code,200);self.assertEqual(paid['job_status'],'COMPLETED')
        self.assertEqual(len(paid['receipts']),1);self.assertEqual(paid['external_financial_calls'],0)
        self.assertEqual(api('dispatch-mock',{'id':c['id']})[1]['code'],'APPROVAL_ALREADY_CONSUMED')

    def hosted_authorization(self, credit_cap=1000000):
        self.cfg['chain_id']=63825;self.cfg['api_credit_max']=credit_cap;self.config.write_text(json.dumps(self.cfg))
        run=self.ledger.create_run([{'seed':0,'policy':'real-premium','hold':100000,'allocation':100000,
            'price_cap':50000,'tasks':[self.task.public()]}],100000,float_mode='TESTNET')
        job=self.ledger.jobs(run)[0]
        raw={'url':'https://provider.invalid/inference/task','provider_id':'hosted-premium',
             'offer':{'amount':str(10000*10**12)},'expires_at':int((time.time()+240)*1000)}
        quote=MetalQuote('credit-quote','hosted-premium',10000,raw['expires_at']/1000,raw,payer_scope='credit-gate')
        key=self.ledger.reserve(job['id'],self.task,0,quote,0)
        c=self.ledger.prepare_approval(key);self.ledger.approvals.submit(c['id'],self.signer.sign(c))
        self.ledger.assert_can_pay(key)
        return {'approval_id':c['id'],'purchase_key':key}

    def test_direct_hosted_api_unsigned_causes_zero_requests(self):
        from touchstone.providers import anthropic_inference
        calls=[]
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fixture-only','ANTHROPIC_MODEL':'claude-sonnet-5-5'}):
            self.error('APPROVAL_REQUIRED',anthropic_inference,self.task,lambda *a,**k:calls.append(1))
        self.assertFalse(calls)

    def test_signed_credit_call_is_separate_bounded_and_never_retried(self):
        from touchstone.providers import anthropic_inference
        auth=self.hosted_authorization();calls=[]
        def opener(*args,**kwargs):
            calls.append(1)
            return io.BytesIO(json.dumps({'model':'claude-sonnet-5-5','stop_reason':'end_turn',
                'content':[{'type':'text','text':'{"total_cents":2000}'}],'usage':{'input_tokens':20,'output_tokens':10}}).encode())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fixture-only','ANTHROPIC_MODEL':'claude-sonnet-5-5'}):
            changed=Task(self.task.id,self.task.kind,{'amounts_cents':[1],'discount_cents':0})
            self.error('TERMS_MISMATCH',anthropic_inference,changed,opener,authorization=auth)
            self.assertFalse(calls)
            result=anthropic_inference(self.task,opener,authorization=auth)
            self.assertEqual(result[0],{'total_cents':2000})
            self.error('APPROVAL_ALREADY_CONSUMED',anthropic_inference,self.task,opener,authorization=auth)
        self.assertEqual(len(calls),1)
        with self.ledger.connect() as db:
            row=db.execute('SELECT * FROM procurement_hosted_dispatches').fetchone()
            self.assertGreater(row['credit_bound'],0);self.assertLessEqual(row['credit_bound'],1000000)

    def test_credit_cap_refuses_before_hosted_network(self):
        from touchstone.providers import anthropic_inference
        auth=self.hosted_authorization(1);calls=[]
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fixture-only','ANTHROPIC_MODEL':'claude-sonnet-5-5'}):
            self.error('API_CREDIT_LIMIT',anthropic_inference,self.task,lambda *a,**k:calls.append(1),authorization=auth)
        self.assertFalse(calls)


if __name__=='__main__': unittest.main()
