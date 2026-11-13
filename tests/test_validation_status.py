import unittest
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from tools.validation_status import provider_status,paid_preflight


class ValidationStatusTests(unittest.TestCase):
    def test_capped_probe_requires_approval_logs_charge_and_replays_without_purchase(self):
        from tools.capped_probe import run,approval_phrase
        from touchstone.metal import MetalQuote,PaymentPending
        from touchstone.ledger import Ledger
        import time
        calls=[]
        class Client:
            mode='MOCK'
            def authorize_purchase(self, authorization): pass
            def __init__(self,*args,**kwargs):self.provider_url=args[1]
            def invoke(self,command):
                self_check=command=='receipts'
                if not self_check:raise AssertionError('Forbidden operation')
                return []
            def quote(self,url):return MetalQuote('quote','local-gpu',10000,time.time()+60,{'url':url},mode='MOCK')
            def pay(self,key,quote):
                calls.append(key)
                return {'state':'DELIVERED','receipt':{'id':'receipt-fixture','invoice':{'amount':str(10000*10**12)}},
                    'output':{'body':{'output':{'total_cents':2000}}}}
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)
            from signed_fixture import signed_fixtures
            signed_fixtures(self,target)
            kwargs=dict(directory=target,reader=lambda *_:{},client_factory=Client,
                        preflight=lambda *a,**k:{'ready_for_final_approval':True})
            refused=run('existing','one',**kwargs)
            self.assertEqual(refused['reason'],'FINAL_APPROVAL_REQUIRED')
            self.assertFalse((target/'ledger.sqlite').exists())
            with self.assertRaises(ValueError):run('existing','one',execute=True,approval='wrong',**kwargs)
            result=run('existing','one',execute=True,approval=approval_phrase('existing','one'),**kwargs)
            self.assertEqual(result['label'],'MOCK')
            self.assertEqual(result['additional_provider_micro_usdz'],10000)
            self.assertTrue(result['paid_calls'][0]['verification_result']['passed'])
            self.assertEqual(result['paid_calls'][0]['transaction_id'],'receipt-fixture')
            replay=run('existing','one',execute=True,approval=approval_phrase('existing','one'),**kwargs)
            self.assertTrue(replay['idempotent_report_replay'])
            self.assertEqual(len(calls),1)
            with patch.object(Client,'pay',side_effect=PaymentPending('Lost response')):
                unknown=run('existing','uncertain',execute=True,approval=approval_phrase('existing','uncertain'),**kwargs)
            self.assertEqual(unknown['possible_unresolved_exposure_micro_usdz'],10000)
            with self.assertRaises(PaymentPending):
                run('existing','uncertain',execute=True,approval=approval_phrase('existing','uncertain'),**kwargs)
            self.assertEqual(len(Ledger(target/'ledger.sqlite').attempts()),2)
            with patch.object(Client,'quote',return_value=MetalQuote('over','local-gpu',10001,time.time()+60,{'url':'http://127.0.0.1:8092'},mode='MOCK')):
                with self.assertRaises(ValueError):
                    run('existing','over',execute=True,approval=approval_phrase('existing','over'),**kwargs)
            self.assertEqual(len(calls),1)

    def test_paid_preflight_only_reads_existing_funds_and_never_authorizes_spending(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);wallet=root/'data/metal/existing/wallet.sqlite'
            wallet.parent.mkdir(parents=True);wallet.touch()
            calls=[]
            class Client:
                def invoke(self,command):
                    calls.append(command)
                    if command=='funding-status':return {'chain_id':63825,'usdz_balance_base_units':'1000000000000000000','native_balance_base_units':'1'}
                    if command=='receipts':return []
                    raise AssertionError('Non-read operation')
                def balance(self):return {'spendable_base_units':'10000000000000000','pending_invoice':False}
                def quote(self,url):return SimpleNamespace(provider='local-gpu',price=10000,expires_at=200,id='fixture')
            def factory(*args,**kwargs):
                self.assertFalse(kwargs['execute'])
                return Client()
            health=lambda *_:{'provider_id':'local-gpu','provider_type':'model','inference_ready':True,'chain':63825}
            with patch('tools.validation_status.ROOT',root),patch('tools.validation_status.time.time',return_value=100):
                report=paid_preflight('existing',reader=health,client_factory=factory)
                self.assertTrue(report['ready_for_final_approval'])
                self.assertFalse(report['paid_operation_authorized'])
                self.assertEqual(report['proposed_test']['estimated_provider_micro_usdz'],10000)
                self.assertEqual(report['financial_transactions'],0)
                self.assertEqual(calls,['funding-status','receipts'])
                self.assertFalse(report['hosted_study']['ready'])
                with patch.object(Client,'balance',return_value={'spendable_base_units':'0','pending_invoice':False}):
                    self.assertFalse(paid_preflight('existing',reader=health,client_factory=factory)['ready_for_final_approval'])
                with patch.object(Client,'balance',return_value={'spendable_base_units':'10000000000000000','pending_invoice':True}):
                    self.assertFalse(paid_preflight('existing',reader=health,client_factory=factory)['ready_for_final_approval'])
                with patch.object(Client,'quote',return_value=SimpleNamespace(provider='local-gpu',price=10001,expires_at=200,id='over-cap')):
                    self.assertFalse(paid_preflight('existing',reader=health,client_factory=factory)['ready_for_final_approval'])
                missing=paid_preflight('missing',reader=health,client_factory=lambda *a,**k:self.fail('Must not create a wallet'))
                self.assertEqual(missing['label'],'BLOCKED')
                self.assertFalse((root/'data/metal/missing').exists())

    def test_paid_preflight_rejects_caps_above_the_user_proposal(self):
        for kwargs in ({'aggregate_cap':1000001},{'per_call_cap':10001},{'aggregate_cap':True}):
            with self.assertRaises(ValueError):
                paid_preflight('existing',reader=lambda *_:{},**kwargs)

    def test_stopped_or_unconfigured_providers_never_pass(self):
        report = provider_status(lambda *_: {})
        self.assertFalse(report['model'])
        self.assertFalse(report['dashboard'])
        self.assertEqual(report['local-gpu']['label'], 'BLOCKED')
        self.assertEqual(report['hosted-premium']['label'], 'BLOCKED')

    def test_health_requires_identity_chain_readiness_and_hosted_funding_declaration(self):
        rows = {8088: {'jobs': []}, 8080: {'status': 'ok'},
                8092: {'provider_id': 'local-gpu', 'provider_type': 'model', 'chain': 63825, 'inference_ready': True},
                8093: {'provider_id': 'hosted-premium', 'provider_type': 'anthropic', 'chain': 63825,
                       'inference_ready': True, 'upstream_funding': 'PARTNER_CREDITS_OPERATOR_DECLARED'}}
        reader = lambda port, _: rows[port]
        self.assertEqual(provider_status(reader)['hosted-premium']['label'], 'MEASURED')
        for key, value in [('provider_id', 'another-seller'), ('chain', 1), ('inference_ready', False),
                           ('upstream_funding', 'UNVERIFIED')]:
            original = rows[8093][key]
            rows[8093][key] = value
            with self.subTest(key=key):
                self.assertEqual(provider_status(reader)['hosted-premium']['label'], 'BLOCKED')
            rows[8093][key] = original


if __name__ == '__main__':
    unittest.main()
