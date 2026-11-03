import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from m2_fixtures import FixtureFactory, FixtureClient
from touchstone.invoice_dataset import build,save
from touchstone.invoice_extraction import deterministic,duplicate_reference,verify
from touchstone.invoice_profile import local,paid,raw_profile
from touchstone.invoice_study import assess,dashboard,evaluate_profile,report,score
from touchstone.metal import PaymentPending,MetalQuote
from touchstone.workload import Task


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.records,self.truth=build()

    def test_unique_fixed_template_split_and_truth_excluded_from_public_sources(self):
        self.assertEqual(len(self.records),180)
        self.assertEqual(len({r['source_sha256'] for r in self.records}),180)
        groups={p:{r['template_id'] for r in self.records if r['partition']==p} for p in ('calibration','holdout')}
        self.assertFalse(groups['calibration']&groups['holdout'])
        self.assertEqual((len(groups['calibration']),len(groups['holdout'])),(8,4))
        self.assertEqual(build(),(self.records,self.truth))
        for record in self.records:
            self.assertEqual(set(record['task']['source']),{'text','purchase_order','payments'})
            self.assertNotIn('fields',record['task']['source'])

    def test_golden_citations_pass_without_reading_offline_labels(self):
        with patch('touchstone.invoice_dataset.build',side_effect=AssertionError('Truth accessed')):
            for record in self.records:
                task=Task(**record['task']);expected=self.truth[task.id]
                result=verify(task,expected['output'])
                self.assertEqual(result['passed'],not bool(expected['missing_fields']),task.id)
                self.assertFalse(result['payment_authorized'])

    def test_tools_have_measured_coverage_and_no_false_accepts(self):
        rows=[]
        for record in self.records:
            task=Task(**record['task'])
            rows.append({'task_id':task.id,'output':deterministic(task),'latency_ms':0})
        scored=score(self.records,self.truth,rows)
        self.assertEqual(sum(r['output'] is not None for r in scored),24)
        self.assertEqual(sum(r['false_accept'] for r in scored),0)

    def test_missing_fields_cannot_be_invented_or_accepted(self):
        record=next(r for r in self.records if r['scenario']=='missing_field')
        task=Task(**record['task']);output=copy.deepcopy(self.truth[task.id]['output'])
        self.assertFalse(verify(task,output)['passed'])
        missing=self.truth[task.id]['missing_fields'][0]
        output['fields'][missing]={'value':'invented','start':0,'end':8}
        self.assertFalse(verify(task,output)['passed'])

    def test_row_coverage_forged_spans_and_bool_offsets_fail(self):
        task=Task(**self.records[0]['task']);gold=self.truth[task.id]['output']
        for mutate in ('omit','bool','wrong_text','outside_row','duplicate_header'):
            output=copy.deepcopy(gold)
            if mutate=='omit':output['items'].pop()
            if mutate=='bool':output['fields']['invoice_id']['start']=True
            if mutate=='wrong_text':output['items'][0]['line_total_cents']['value']='USD 0.00'
            if mutate=='outside_row':output['items'][0]['unit_price_cents']=output['fields']['subtotal_cents']
            if mutate=='duplicate_header':output['fields']['total_cents']=output['fields']['subtotal_cents']
            with self.subTest(mutate=mutate):self.assertFalse(verify(task,output)['passed'])

    def test_duplicate_and_conflicting_po_are_review_outcomes(self):
        for scenario in ('duplicate_reference','conflicting_po'):
            record=next(r for r in self.records if r['scenario']==scenario)
            task=Task(**record['task']);result=verify(task,self.truth[task.id]['output'])
            self.assertEqual(result['decision'],'review')
            self.assertFalse(result['payment_authorized'])
            self.assertEqual(duplicate_reference(task),scenario=='duplicate_reference')

    def test_reference_disagreement_retains_its_charge(self):
        task=Task(**self.records[0]['task']);primary=self.truth[task.id]['output']
        changed=copy.deepcopy(primary);changed['fields']['currency']=None
        verdict=assess(task,primary,changed,10000)
        self.assertFalse(verdict['passed'])
        self.assertEqual(verdict['reference_cost_micro_usd'],10000)
        self.assertEqual(verdict['decision'],'review')
        with self.assertRaises(ValueError):assess(task,primary,changed,0)

    def test_holdout_cannot_inflate_calibration_gate_or_cover_missing_profiles(self):
        calibration=[r for r in self.records if r['partition']=='calibration']
        rows=[{'task_id':r['task']['id'],'output':self.truth[r['task']['id']]['output'],'latency_ms':1} for r in calibration]
        result=evaluate_profile(self.records,self.truth,raw_profile('fixture','fixture',rows))
        self.assertTrue(result['screen']['passes_statistical_screen'])
        self.assertEqual(result['screen']['unique_sources'],120)
        self.assertFalse(result['eligible'])
        rows += [{'task_id':r['task']['id'],'output':None,'latency_ms':1} for r in self.records if r['partition']=='holdout']
        result=evaluate_profile(self.records,self.truth,raw_profile('fixture','fixture',rows))
        self.assertFalse(result['eligible'])
        self.assertEqual(result['screen']['unique_sources'],120)
        with self.assertRaises(ValueError):score(self.records,self.truth,rows+[rows[0]])

    def test_mock_stale_and_changed_artifacts_cannot_qualify(self):
        raw=raw_profile('fixture','fixture',[])
        with self.assertRaises(ValueError):evaluate_profile(self.records,self.truth,{**raw,'label':'MOCK'})
        with tempfile.TemporaryDirectory() as directory:
            report(directory)
            self.assertEqual(dashboard(directory)['label'],'MEASURED')
            source=Path(directory)/'dataset/sources.jsonl'
            source.write_text(source.read_text(encoding='utf-8')+'\n',encoding='utf-8')
            self.assertEqual(dashboard(directory)['label'],'BLOCKED')

    def test_gates_and_showcase_refuse_every_unmeasured_model(self):
        with tempfile.TemporaryDirectory() as directory:
            result=report(directory)
            self.assertEqual(result['qualification_status'],'BLOCKED_NO_ELIGIBLE_MODEL')
            self.assertEqual(result['models_measured'],0)
            self.assertFalse(result['threshold_changed'])
            self.assertEqual([r['decision'] for r in result['showcase']['tasks']],['LOCAL_TOOL','REVIEW_REQUIRED','HUMAN_REVIEW'])


class PremiumClient(FixtureClient):
    def quote(self,url):
        quote=super().quote(url);terms={**quote.terms,'provider_id':'hosted-premium'}
        identity=hashlib.sha256(json.dumps(terms,sort_keys=True).encode()).hexdigest()
        return MetalQuote(identity,'hosted-premium',10000,quote.expires_at,terms,mode='MOCK')


class PremiumFactory(FixtureFactory):
    def __call__(self,wallet,origin,cap,budget):
        client=PremiumClient(self,wallet,origin)
        if int(client.balance()['spendable_base_units'])==0:client.deposit(1000000)
        return client


class PaidProfileTests(unittest.TestCase):
    def test_partitions_merge_without_rebuying_a_source_or_relabelling_mock(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);factory=PremiumFactory(root/'remote')
            health={'inference_ready':True,'chain':63825,'provider_id':'hosted-premium',
                    'upstream_funding':'PARTNER_CREDITS_OPERATOR_DECLARED','provider_model':'fixture-model'}
            kwargs=dict(execute=True,client_factory=factory,health=health,directory=root/'state')
            paid('calib','http://127.0.0.1:8093',50000,10000,1,root/'out.json',**kwargs)
            result=paid('heldout','http://127.0.0.1:8093',50000,10000,1,root/'out.json',partition='holdout',**kwargs)
            self.assertEqual(len(result['rows']),2)
            self.assertEqual(len(result['runs']),2)
            self.assertEqual(result['label'],'MOCK')
            self.assertEqual(result['confirmed_provider_spend_including_failed_calls_micro_usd'],20000)
            self.assertEqual(result['verification_cost_micro_usd'],2000)
            payments=sum(e[0]=='pay' for e in factory.events)
            again=paid('heldout','http://127.0.0.1:8093',50000,10000,1,root/'out.json',partition='holdout',**kwargs)
            self.assertEqual(len(again['rows']),2)
            self.assertEqual(sum(e[0]=='pay' for e in factory.events),payments)
            with self.assertRaises(ValueError):
                paid('another','http://127.0.0.1:8093',50000,10000,1,root/'out.json',**kwargs)
            self.assertEqual(sum(e[0]=='pay' for e in factory.events),payments)

    def test_no_execute_and_wrong_funding_label_send_no_calls(self):
        with self.assertRaises(ValueError):paid('p','http://127.0.0.1:8093',50000,10000,1,'unused')
        with tempfile.TemporaryDirectory() as directory:
            factory=PremiumFactory(Path(directory)/'remote')
            with self.assertRaises(RuntimeError):paid('p','http://127.0.0.1:8093',50000,10000,1,Path(directory)/'out.json',
                execute=True,client_factory=factory,health={},directory=Path(directory)/'state')
            self.assertEqual(factory.events,[])

    def test_reference_calls_are_charged_and_share_call_and_budget_caps(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);factory=PremiumFactory(root/'remote')
            health={'inference_ready':True,'chain':63825,'provider_id':'hosted-premium',
                    'upstream_funding':'PARTNER_CREDITS_OPERATOR_DECLARED'}
            result=paid('primary','http://127.0.0.1:8093',100000,10000,2,root/'out.json',execute=True,
                reference_scope='reference',reference_budget=50000,client_factory=factory,health=health,directory=root/'state')
            self.assertEqual(result['label'],'MOCK')
            self.assertEqual(sum(e[0]=='pay' for e in factory.events),2)
            self.assertEqual(result['confirmed_provider_spend_including_failed_calls_micro_usd'],20000)
            self.assertEqual(result['verification_cost_micro_usd'],2000)
            self.assertEqual(result['rows'][0]['reference_cost_micro_usd'],10000)
            self.assertEqual(result['stop_reason'],'PolicyError')

    def test_unknown_payment_is_retained_and_never_blindly_retried(self):
        class LosingFactory(PremiumFactory):
            def __call__(self,*args):
                client=super().__call__(*args);original=client.pay
                def lose(*params):
                    original(*params)
                    raise PaymentPending('Controlled lost response')
                client.pay=lose
                return client
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);factory=LosingFactory(root/'remote')
            health={'inference_ready':True,'chain':63825,'provider_id':'hosted-premium',
                    'upstream_funding':'PARTNER_CREDITS_OPERATOR_DECLARED'}
            kwargs=dict(execute=True,client_factory=factory,health=health,directory=root/'state')
            result=paid('unknown','http://127.0.0.1:8093',50000,10000,1,root/'out.json',**kwargs)
            self.assertEqual(result['pending_attempts'],1)
            with self.assertRaises(PaymentPending):
                paid('unknown','http://127.0.0.1:8093',50000,10000,1,root/'out.json',**kwargs)
            self.assertEqual(sum(e[0]=='pay' for e in factory.events),1)


class LocalProfileTests(unittest.TestCase):
    def test_hardware_failure_retains_completed_call_before_stopping(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);model=root/'model.gguf';model.write_bytes(b'MOCK MODEL')
            manifests=root/'.tools/models';manifests.mkdir(parents=True)
            manifest={'model_path':str(model),'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
                      'model':'fixture-local'}
            (manifests/'economy-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            health=io.BytesIO(b'{}');health.status=200
            props=io.BytesIO(json.dumps({'model_path':str(model)}).encode())
            with patch('touchstone.invoice_profile.ROOT',root), \
                 patch('touchstone.invoice_profile.urllib.request.build_opener') as opener, \
                 patch('touchstone.invoice_profile.hardware',side_effect=[{'headroom_at_least_20_percent':True},RuntimeError('controlled GPU limit')]), \
                 patch('touchstone.providers.local_inference',return_value=({'fixture':True},12)) as inference:
                opener.return_value.open.side_effect=[health,props]
                with self.assertRaises(RuntimeError):local('economy','calibration',1,root/'out.json')
            saved=json.loads((root/'out.json').read_text(encoding='utf-8'))
            self.assertEqual(len(saved['rows']),1)
            self.assertEqual(saved['rows'][0]['latency_ms'],12)
            self.assertEqual(saved['stop_reason'],'RuntimeError')
            self.assertEqual(inference.call_count,1)
