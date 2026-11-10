import io
import json
import unittest
from unittest.mock import Mock,patch

from tools.preflight_invoice_study import count,estimate_micro_usd,TOKEN_COUNT_URL
from tools.run_invoice_qualification import CreditJournal,approval_phrase,fingerprint,fund_once,run
from touchstone.hosted_cost import estimate_usage
from touchstone.ledger import PolicyError
from touchstone.invoice_dataset import build
from touchstone.workload import Task


class QualificationControls(unittest.TestCase):
    def test_unapproved_plan_does_not_open_wallet_or_request_network(self):
        terms={'scope':'fixture'};plan={'terms':terms,'plan_sha256':fingerprint(terms)}
        with patch('tools.run_invoice_qualification.MetalRail',side_effect=AssertionError('Wallet accessed')):
            result=run(plan)
            self.assertEqual(result['reason'],'FINAL_APPROVAL_REQUIRED')
            self.assertEqual(result['payments_sent'],0)
            self.assertEqual(result['approval_phrase'],approval_phrase(plan))
            with self.assertRaises(ValueError):run(plan,execute=True,approval='wrong plan')

    def test_unknown_deposit_never_retries_or_tops_up(self):
        client=Mock()
        client.balance.return_value={'pending_invoice':False,'historical_payments':0,'spendable_base_units':'0'}
        client.invoke.side_effect=TimeoutError('Uncertain deposit')
        state={};persist=Mock()
        with self.assertRaises(TimeoutError):fund_once(client,'wallet',10000,state,persist,'1000')
        self.assertEqual(state['funding']['wallet']['state'],'UNKNOWN')
        with self.assertRaises(PolicyError):fund_once(client,'wallet',10000,state,persist,'1000')
        self.assertEqual(client.invoke.call_count,1)
        self.assertEqual(client.invoke.call_args.kwargs,{'dollars':'0.010000','native_gas_cap_wei':'1000'})

    def test_confirmed_funding_does_not_repeat_any_funding_request(self):
        client=Mock();state={'funding':{'wallet':{'state':'FUNDED'}}}
        fund_once(client,'wallet',10000,state,Mock(),'1000')
        client.invoke.assert_not_called();client.balance.assert_not_called()

    def test_credit_cap_reserves_before_call_and_rejects_duplicate_task(self):
        state={};journal=CreditJournal(state,Mock(),11200)
        task=Task('one','arithmetic',{'amounts_cents':[1],'discount_cents':0})
        journal.before(task,None)
        with self.assertRaises(PolicyError):journal.before(Task('two',task.kind,task.source),None)
        with self.assertRaises(PolicyError):journal.before(task,None)
        receipt={'id':'receipt-fixture','amount':10000,'provider_metadata':{'provider_model':'claude-haiku-5-5',
            'provider_type':'ANTHROPIC_API','usage':{'input_tokens':1000,'output_tokens':500}}}
        journal.after(task,None,receipt)
        self.assertEqual(state['credits']['one']['estimated_credit_micro_usd'],350)
        self.assertFalse(state['credits']['one']['billing_reconciled'])

    def test_missing_usage_keeps_exposure_instead_of_recording_zero_cost(self):
        state={};journal=CreditJournal(state,Mock(),1000000)
        task=Task('one','arithmetic',{'amounts_cents':[1],'discount_cents':0});journal.before(task,None)
        receipt={'id':'receipt-fixture','amount':10000,'provider_metadata':{
            'provider_model':'claude-haiku-5-5','provider_type':'ANTHROPIC_API'}}
        with self.assertRaises(PolicyError):journal.after(task,None,receipt)
        self.assertEqual(state['credits']['one']['state'],'UNKNOWN')
        self.assertNotIn('estimated_credit_micro_usd',state['credits']['one'])

    def test_unknown_model_and_invalid_usage_have_no_fabricated_price(self):
        self.assertIsNone(estimate_usage('unknown',{})['estimated_credit_micro_usd'])
        with self.assertRaises(ValueError):estimate_usage('claude-haiku-5-5',{'input_tokens':True})
        self.assertEqual(estimate_micro_usd(10000),2605)
        for value in (True,-1,20001):
            with self.assertRaises(ValueError):estimate_micro_usd(value)

    def test_free_preflight_calls_only_count_endpoint_and_never_returns_credentials(self):
        task=Task(**build()[0][0]['task']);requests=[]
        def opener(request,timeout):
            requests.append(request);return io.BytesIO(b'{"input_tokens":1000}')
        result=count(task,'claude-haiku-5-5',{'x-api-key':'fixture-private-key'},opener)
        self.assertEqual(requests[0].full_url,TOKEN_COUNT_URL)
        self.assertNotIn('fixture-private-key',json.dumps(result))
        self.assertEqual(result['financial_transactions'],0);self.assertEqual(result['inference_calls'],0)


if __name__=='__main__':unittest.main()
