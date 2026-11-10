import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import qualify_stronger as driver
from touchstone.invoice_corpus import freeze,load
from touchstone.invoice_study import code_hashes
from touchstone.ledger import PolicyError


class StrongerQualification(unittest.TestCase):
    def test_approval_guard_precedes_credentials_and_api(self):
        terms={'scope':'fixture'};plan={'terms':terms,'plan_sha256':driver.fingerprint(terms)}
        with patch('tools.run_project.environment',side_effect=AssertionError('Credentials accessed')):
            self.assertEqual(driver.run(plan)['inference_calls'],0)
            with self.assertRaises(PolicyError):driver.run(plan,True,'wrong')

    def test_sonnet_cost_keeps_integer_rounding_and_rejects_unknown_usage(self):
        self.assertEqual(driver.sonnet_cost({'input_tokens':1000,'output_tokens':500}),7000)
        for usage in ({},{'input_tokens':0,'output_tokens':1},{'input_tokens':1,'output_tokens':True}):
            with self.assertRaises(ValueError):driver.sonnet_cost(usage)

    def fixture(self,root,cap=8000000):
        corpus=root/'corpus';manifest=freeze(corpus,202611101)
        utility=root/'tools/qualify_hosted_direct.py';utility.parent.mkdir(parents=True);utility.write_text('# fixture')
        preflight=root/'bench/results/m3-v2/sonnet-cost-preflight.json';preflight.parent.mkdir(parents=True);preflight.write_text('{}')
        terms={'scope':'fixture','model':'claude-sonnet-5-5','corpus':'corpus','corpus_sources_sha256':manifest['sources_sha256'],
            'code_sha256':code_hashes(),'driver_sha256':driver.file_hash(driver.__file__),
            'utility_sha256':driver.file_hash(utility),'preflight_sha256':driver.file_hash(preflight),
            'prior_qualification_credit_exposure_micro_usd':89351,'prepaid_credit_aggregate_cap_micro_usd':cap,
            'maximum_new_calls':180,'output':'profile.json','pricing_reference':'https://platform.claude.com/docs/en/about-claude/pricing',
            'pricing_checked_date':'2026-11-10'}
        return {'terms':terms,'plan_sha256':driver.fingerprint(terms)},load(corpus,True)[2]

    def test_mock_perfect_model_qualifies_once_without_exposing_truth_to_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);plan,truth=self.fixture(root);calls=[]
            def infer(task):
                self.assertNotIn('truth',task.source);calls.append(task.id)
                return truth[task.id]['output'],3,{'provider_model':'claude-sonnet-5-5',
                    'provider_type':'ANTHROPIC_API','usage':{'input_tokens':1000,'output_tokens':500}}
            with patch.object(driver,'ROOT',root),patch('tools.run_project.environment'),patch('builtins.print'):
                state=driver.run(plan,True,driver.phrase(plan),infer)
                self.assertEqual(state['phase'],'COMPLETE');self.assertTrue(state['evaluation']['eligible'])
                self.assertEqual(len(calls),180);self.assertEqual(len(set(calls)),180)
                self.assertEqual(driver.run(plan,True,driver.phrase(plan),infer),state)
                self.assertEqual(len(calls),180)

    def test_cap_and_uncertain_api_outcome_never_dispatch_again(self):
        for capped in (True,False):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);plan,_=self.fixture(root,100000 if capped else 8000000);calls=[]
                def fail(task):calls.append(task.id);raise TimeoutError('MOCK unknown API outcome')
                with patch.object(driver,'ROOT',root),patch('tools.run_project.environment'),patch('builtins.print'):
                    state=driver.run(plan,True,driver.phrase(plan),fail)
                    self.assertEqual(state['phase'],'STOPPED')
                    self.assertEqual(len(calls),0 if capped else 1)
                    driver.run(plan,True,driver.phrase(plan),fail)
                    self.assertEqual(len(calls),0 if capped else 1)
