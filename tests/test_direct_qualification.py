import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import qualify_hosted_direct as driver
from touchstone.hosted_cost import estimate_usage
from touchstone.invoice_corpus import freeze,load
from touchstone.invoice_profile import save
from touchstone.ledger import PolicyError


class DirectQualification(unittest.TestCase):
    def test_missing_or_incorrect_approval_never_loads_credentials_or_calls_api(self):
        terms={'scope':'fixture'};plan={'terms':terms,'plan_sha256':driver.fingerprint(terms)}
        with patch('tools.run_project.environment',side_effect=AssertionError('Credentials loaded')):
            self.assertEqual(driver.run(plan)['phase'],'FINAL_APPROVAL_REQUIRED')
            with self.assertRaises(PolicyError):driver.run(plan,True,'wrong')

    def test_all_sources_once_failed_original_retained_and_restart_sends_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);corpus=root/'bench/results/m3-v2/dataset';freeze(corpus,202611101)
            _,records,truth=load(corpus,include_truth=True)
            first,failed=records[:2]
            original=root/'original.json';status=root/'status.json'
            save(original,{'rows':[{'task_id':first['task']['id'],'output':truth[first['task']['id']]['output'],
                                   'receipt':'MOCK-original','provider_cost_micro_usd':10000}]})
            save(status,{'phase':'STOPPED_NO_RETRY','plan_sha256':'original-mock-plan',
                'confirmed_nonpayment':{'confirmed_nonpayment':True,'task_id':failed['task']['id']},
                'balance':{'pending_invoice':False}})
            calls=[];usage={'input_tokens':1000,'output_tokens':1000}
            def infer(task):
                self.assertNotIn('output',task.source)
                calls.append(task.id)
                return truth[task.id]['output'],3,{'provider_type':'ANTHROPIC_API','provider_model':'claude-haiku-5-5',
                    'usage':usage,'hosted_api_cost':estimate_usage('claude-haiku-5-5',usage)}
            with patch.multiple(driver,ROOT=root,ORIGINAL=original,STATUS=status),patch('tools.run_project.environment'),\
                 patch.dict('os.environ',{'ANTHROPIC_MODEL':'claude-haiku-5-5'}),patch('builtins.print'):
                plan=driver.prepare();state=driver.run(plan,True,driver.phrase(plan),infer=infer)
                self.assertEqual(state['phase'],'COMPLETE')
                self.assertTrue(state['evaluation']['eligible'])
                self.assertEqual(state['evaluation']['calibration']['strict_correct'],119)
                self.assertEqual(state['evaluation']['holdout']['strict_correct'],60)
                self.assertEqual(len(calls),178);self.assertEqual(len(set(calls)),178)
                self.assertNotIn(first['task']['id'],calls);self.assertNotIn(failed['task']['id'],calls)
                self.assertEqual(driver.run(plan,True,driver.phrase(plan),infer=infer),state)
                self.assertEqual(len(calls),178)

    def test_api_error_retains_reserved_exposure_and_prevents_another_request(self):
        # Reuse a small real corpus fixture; the injected API fails before any synthetic output.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);corpus=root/'bench/results/m3-v2/dataset';freeze(corpus,202611101)
            _,records,truth=load(corpus,include_truth=True)
            original=root/'original.json';status=root/'status.json'
            save(original,{'rows':[{'task_id':records[0]['task']['id'],'output':truth[records[0]['task']['id']]['output']}]})
            save(status,{'phase':'STOPPED_NO_RETRY','plan_sha256':'mock',
                'confirmed_nonpayment':{'confirmed_nonpayment':True,'task_id':records[1]['task']['id']},'balance':{'pending_invoice':False}})
            calls=[]
            def fail(task):calls.append(task.id);raise TimeoutError('MOCK uncertain API outcome')
            with patch.multiple(driver,ROOT=root,ORIGINAL=original,STATUS=status),patch('tools.run_project.environment'),\
                 patch.dict('os.environ',{'ANTHROPIC_MODEL':'claude-haiku-5-5'}),patch('builtins.print'):
                plan=driver.prepare();state=driver.run(plan,True,driver.phrase(plan),infer=fail)
                self.assertEqual(state['phase'],'STOPPED')
                self.assertEqual(state['calls'][0]['state'],'DISPATCHING')
                self.assertEqual(state['calls'][0]['reserved_credit_micro_usd'],11200)
                driver.run(plan,True,driver.phrase(plan),infer=fail)
                self.assertEqual(len(calls),1)
