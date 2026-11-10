import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import resume_qualification_cap as driver
from tools import qualify_stronger
from touchstone.invoice_corpus import freeze,load
from touchstone.invoice_profile import save
from touchstone.invoice_study import code_hashes
from touchstone.ledger import PolicyError


class LowerQualificationCap(unittest.TestCase):
    def test_no_execute_or_raised_cap_never_loads_credentials(self):
        with patch('tools.run_project.environment',side_effect=AssertionError('Credentials accessed')):
            self.assertEqual(driver.resume({})['inference_calls'],0)
            with self.assertRaises(PolicyError):driver.resume({},True,3000001)

    def test_completed_outputs_are_reused_uncertain_source_is_incorrect_and_never_repeated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);manifest=freeze(root/'corpus',202611101)
            _,records,truth=load(root/'corpus',True)
            original=root/'tools/qualify_stronger.py';original.parent.mkdir()
            original.write_bytes(Path(qualify_stronger.__file__).read_bytes())
            terms={'scope':'fixture','model':'claude-sonnet-5-5','corpus':'corpus',
                'corpus_sources_sha256':manifest['sources_sha256'],'code_sha256':code_hashes(),
                'driver_sha256':driver.file_hash(original),'prior_qualification_credit_exposure_micro_usd':89351,
                'maximum_new_calls':180,'output':'profile.json','pricing_reference':'https://platform.claude.com/docs/en/about-claude/pricing',
                'pricing_checked_date':'2026-11-10'}
            plan={'terms':terms,'plan_sha256':driver.fingerprint(terms)}
            prior=records[:125];pending=prior[-1]['task']['id']
            state={'plan_sha256':plan['plan_sha256'],'phase':'RUNNING',
                'calls':[{'task_id':r['task']['id'],'state':'REPORTED','estimated_credit_micro_usd':1000} for r in prior[:-1]]+
                        [{'task_id':pending,'state':'DISPATCHING','reserved_credit_micro_usd':224000}],
                'rows':[{'task_id':r['task']['id'],'output':truth[r['task']['id']]['output']} for r in prior[:-1]]}
            save(root/'data/fixture/journal.json',state);calls=[]
            def infer(task):
                calls.append(task.id)
                return truth[task.id]['output'],3,{'provider_model':'claude-sonnet-5-5','provider_type':'ANTHROPIC_API',
                    'usage':{'input_tokens':1000,'output_tokens':500}}
            with patch.object(driver,'ROOT',root),patch('tools.run_project.environment'),patch('builtins.print'):
                result=driver.resume(plan,True,3000000,infer)
                self.assertEqual(result['phase'],'COMPLETE')
                self.assertEqual(result['evaluation']['calibration']['strict_correct'],120)
                self.assertEqual(result['evaluation']['holdout']['strict_correct'],59)
                self.assertEqual(len(calls),55);self.assertNotIn(pending,calls)
                self.assertEqual(len(set(calls)),55)
                profile=json.loads((root/'profile.json').read_text())
                self.assertEqual(profile['effective_total_credit_cap_micro_usd'],3000000)
                self.assertEqual(profile['unreported_api_credit_allowance_micro_usd'],224000)
                self.assertTrue(result['evaluation']['eligible'])
                self.assertEqual(driver.resume(plan,True,3000000,infer),result)
                self.assertEqual(len(calls),55)
