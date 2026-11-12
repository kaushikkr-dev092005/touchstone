"""Spending and authorization guards only; no benchmark, model or payment execution."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.continue_policy_live import amendment,approval_phrase,guard_offers,run
from touchstone.comparison import fingerprint
from touchstone.ledger import PolicyError

ROOT=Path(__file__).resolve().parent.parent


class LivePolicyContinuationGuards(unittest.TestCase):
    def test_ceiling_amendment_preserves_workload_wallet_and_original_plan(self):
        original=json.loads((ROOT/'bench/results/m4-v2/final-plan.json').read_text())
        before=deepcopy(original)
        effective=amendment(original,2919117,693808,4500000)
        self.assertEqual(original,before)
        self.assertEqual(effective['hosted_credit_cap_micro_usd'],2274691)
        changed={k for k in effective if effective[k]!=original[k]}
        self.assertEqual(changed,{'plan_sha256','hosted_credit_cap_micro_usd'})
        self.assertEqual(effective['plan_sha256'],fingerprint({k:v for k,v in effective.items() if k!='plan_sha256'}))

    def test_existing_and_unknown_exposure_cannot_be_erased(self):
        for values in [(100,101,200),(100,50,99),(100,50,True),(100.0,50,200)]:
            with self.assertRaises(ValueError):amendment({'plan_sha256':'old'},*values)

    def test_missing_execute_or_approval_fails_before_account_access(self):
        terms={'total_claude_ceiling_micro_usd':4500000}
        plan={'terms':terms,'plan_sha256':fingerprint(terms)}
        with patch('tools.run_project.environment',side_effect=AssertionError('Account access forbidden')):
            for execute,approval in [(False,None),(True,None),(False,approval_phrase(plan)),(True,'old approval')]:
                with self.assertRaises(ValueError):run(plan,execute,approval)
            changed=deepcopy(plan);changed['terms']['total_claude_ceiling_micro_usd']=9999999
            with self.assertRaises(ValueError):run(changed,True,approval_phrase(plan))

    def test_hosted_limit_refuses_before_reservation_but_keeps_local_offer(self):
        state={'calls':{'new':{'provider':'hosted-premium'},'old':{'provider':'hosted-premium'}},'continuation_original_call_keys':['old']}
        terms={'maximum_new_purchase_attempts':3,'maximum_new_hosted_calls':1}
        plan={'qualifications':{}}
        local=SimpleNamespace(provider='local-gpu',price=5000)
        hosted=SimpleNamespace(provider='hosted-premium',price=10000)
        for policy in ('always-premium','touchstone-ladder'):
            with self.assertRaises(PolicyError):guard_offers(policy,[local,hosted],plan,state,terms)
        self.assertEqual(guard_offers('always-cheapest',[local,hosted],plan,state,terms),[local,hosted])
        with self.assertRaises(PolicyError):guard_offers('always-cheapest',[hosted],plan,state,terms)

    def test_failed_attempts_consume_purchase_limit(self):
        state={'calls':{'old':{'provider':'hosted-premium'},'failed':{'provider':'local-gpu','status':'VOID'}},'continuation_original_call_keys':['old']}
        with self.assertRaises(PolicyError):
            guard_offers('always-cheapest',[SimpleNamespace(provider='local-gpu',price=5000)],
                {'qualifications':{}},state,{'maximum_new_purchase_attempts':1,'maximum_new_hosted_calls':2})
