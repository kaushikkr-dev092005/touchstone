import copy
from pathlib import Path
import tempfile
import time
import unittest

from test_holds import FakeAirwallex
from touchstone.banked import BankedStore, BankedWorkflow, resource_url
from touchstone.holds import SandboxHoldWorkflow, OperationJournal
from touchstone.metal import MetalQuote, PaymentPending
from touchstone.workload import Task


class FixtureRail:
    """Stateful remote fixture, independent from the workflow journal."""
    def __init__(self):
        self.result = None
        self.payments = 0
        self.deposits = 0
        self.withdrawals = 0
        self.price = 10000
        self.output = {'total_cents': 2000}
        self.lose_pay = False
        self.spendable = 100000
        self.withdrawal = {'status': 'sent', 'queued': None, 'claimed': [
            {'tx': 'fixture_claim', 'amount': str(90000*10**12), 'deferred': False}]}

    def factory(self, scope, url, cap, budget):
        self.url = url
        return self

    def balance(self):
        return {'account': 'fixture_clearing_public_key', 'spendable_base_units': str(self.spendable*10**12),
                'assurance': 'fixture', 'historical_payments': 0, 'pending_invoice': False}

    def invoke(self, command):
        assert command == 'funding-status'
        return {'address': 'fixture_funding_address', 'usdz_balance_base_units': str(1000000*10**12), 'native_balance_base_units': '10000'}

    def deposit(self, amount):
        self.deposits += 1
        self.spendable = amount

    def quote(self):
        offer = {'amount': str(self.price*10**12), 'network': 'eip155:63825', 'payTo': 'fixture_seller',
                 'asset': 'fixture_usdz', 'extra': {'settlement': 'fixture_settlement', 'invoicePrefix': 'fixture_prefix'}}
        return MetalQuote('fixture_quote', 'fixture', self.price, time.time()+60,
                          {'url': self.url, 'offer': offer, 'expires_at': (time.time()+60)*1000})

    def lookup(self, key):
        return {'state': 'DELIVERED' if self.result else 'NOT_DISPATCHED', 'result': self.result}

    def pay(self, key, quote):
        self.payments += 1
        self.result = {'state': 'DELIVERED', 'receipt': {'id': 'fixture_prefix:receipt1',
            'invoice': {'id': 'fixture_prefix:receipt1', 'amount': str(quote.price*10**12), 'network': 'eip155:63825',
                'recipient': 'fixture_seller', 'asset': 'fixture_usdz', 'settlement': 'fixture_settlement'}, 'status': 'FIXTURE'},
            'output': {'ok': True, 'status': 200, 'body': {'output': self.output}}}
        self.spendable -= quote.price
        if self.lose_pay:
            self.lose_pay = False
            raise PaymentPending('Fixture lost response after durable payment')
        return copy.deepcopy(self.result)

    def recover(self, key):
        return copy.deepcopy(self.result)

    def withdraw(self):
        self.withdrawals += 1
        return copy.deepcopy(self.withdrawal)


class BankedJobs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = Path(self.temp.name)
        self.store = BankedStore(directory / 'ledger.sqlite')
        self.bank = FakeAirwallex()
        self.treasury = SandboxHoldWorkflow(self.bank, OperationJournal(directory / 'airwallex.sqlite'))
        self.rail = FixtureRail()
        self.workflow = BankedWorkflow(self.store, self.treasury, self.rail.factory)
        self.task = Task('probe', 'arithmetic', {'amounts_cents': [1250,275,499], 'discount_cents': 24})

    def run_job(self, **kwargs):
        return self.workflow.run('banked-fixture', self.task, 'http://127.0.0.1:8092', integration_probe=True, **kwargs)

    def test_whole_job_links_authorization_receipt_verification_capture_and_claim(self):
        report = self.run_job()
        self.assertEqual(report['phase'], 'COMPLETED')
        self.assertTrue(report['verdict']['passed'])
        self.assertEqual(report['spent_micro_usd'], 10000)
        self.assertEqual(report['captured_micro_usd'], 10000)
        self.assertEqual(report['unused_authorization_micro_usd'], 990000)
        self.assertTrue(report['float_returned_confirmed'])
        self.assertTrue(self.store.ledger.audit()['valid'])
        before = len(self.bank.calls)
        self.assertEqual(self.run_job(), report)
        self.assertEqual(self.rail.payments, 1)
        self.assertEqual(len(self.bank.calls), before)

    def test_prefunded_only_never_deposits_when_float_is_short(self):
        self.rail.spendable=0
        result=self.run_job(allow_funding=False,return_float=False)
        self.assertEqual(result['phase'],'AWAITING_EXISTING_FLOAT')
        self.assertEqual((self.rail.deposits,self.rail.payments,self.rail.withdrawals),(0,0,0))

    def test_explicit_retention_closes_customer_without_withdrawing_or_claiming_refund(self):
        result=self.run_job(allow_funding=False,return_float=False)
        self.assertEqual(result['phase'],'CLOSED_FLOAT_RETAINED')
        self.assertTrue(result['customer_closed'])
        self.assertTrue(result['reconciliation']['retained_balance_matches'])
        self.assertFalse(result['float_returned_confirmed'])
        self.assertEqual(result['retained_float_base_units'],str(90000*10**12))
        self.assertEqual((self.rail.deposits,self.rail.payments,self.rail.withdrawals),(0,1,0))
        self.assertEqual(self.run_job(allow_funding=False,return_float=False),result)
        with self.assertRaises(ValueError):self.run_job()

    def test_invoice_demo_cannot_authorize_or_purchase_without_measured_qualification(self):
        from touchstone.invoice_dataset import build
        task=Task(**build()[0][0]['task'])
        with self.assertRaisesRegex(ValueError,'current measured qualification'):
            self.workflow.run('invoice-demo',task,'http://127.0.0.1:8093',integration_probe=True,
                              allow_funding=False,return_float=False)
        self.assertEqual(self.bank.calls,[])
        self.assertEqual(self.rail.payments,0)

    def test_unified_receipt_keeps_fiat_tokens_and_quality_separate(self):
        self.run_job(allow_funding=False,return_float=False)
        receipt=self.store.receipt('banked-fixture')
        self.assertEqual(receipt['fiat']['currency'],'USD')
        self.assertEqual(receipt['token']['currency'],'USDZ')
        self.assertEqual(receipt['fiat']['captured_micro_usd'],10000)
        self.assertEqual(receipt['token']['provider_spend_micro_usdz'],10000)
        self.assertIsNone(receipt['token']['onchain_payment_transaction_id'])
        self.assertFalse(receipt['bridge_or_fx_executed'])
        self.assertFalse(receipt['token']['final_settlement_verified'])
        self.assertTrue(receipt['verification']['passed'])
        self.assertFalse(receipt['invoice_payment_authorized'])
        self.assertTrue(receipt['audit']['valid'])

    def test_retained_balance_uses_original_float_when_larger_than_allocation(self):
        self.rail.spendable=200000
        result=self.run_job(allow_funding=False,return_float=False)
        self.assertEqual(result['phase'],'CLOSED_FLOAT_RETAINED')
        self.assertEqual(result['retained_float_base_units'],str(190000*10**12))

    def test_lost_payment_response_recovers_without_another_purchase(self):
        self.rail.lose_pay = True
        self.assertTrue(self.run_job()['recovery_required'])
        self.assertEqual(self.run_job(recover=True)['phase'], 'COMPLETED')
        self.assertEqual(self.rail.payments, 1)

    def test_lost_capture_response_recovers_without_second_capture_or_payment(self):
        self.bank.lose = 'capture'
        self.assertTrue(self.run_job()['recovery_required'])
        report = self.run_job(recover=True)
        self.assertEqual(report['phase'], 'COMPLETED')
        self.assertEqual(sum(c[0]=='POST' and c[1].endswith('/capture') for c in self.bank.calls), 1)
        self.assertEqual(self.rail.payments, 1)

    def test_changed_mandate_rejected_before_remote_effect(self):
        self.run_job()
        before = len(self.bank.calls)
        with self.assertRaises(ValueError):
            self.run_job(hold=2000000)
        self.assertEqual(len(self.bank.calls), before)
        self.assertEqual(self.rail.payments, 1)

    def test_unfinalized_empty_withdrawal_cannot_release_float(self):
        self.rail.withdrawal = {'status': 'empty'}
        report = self.run_job()
        self.assertEqual(report['phase'], 'CLOSED_FLOAT_PENDING')
        self.assertTrue(report['customer_closed'])
        self.assertFalse(report['float_returned_confirmed'])
        self.assertEqual(report['float_returned_micro_usd'], 0)

    def test_failed_output_is_charged_and_fractional_cents_absorbed(self):
        self.rail.output = {'total_cents': 999999}
        self.rail.price = 15500
        report = self.run_job()
        self.assertFalse(report['verdict']['passed'])
        self.assertEqual(report['spent_micro_usd'], 15500)
        self.assertEqual(report['captured_micro_usd'], 10000)
        self.assertEqual(report['merchant_rounding_micro_usd'], 5500)

    def test_halt_blocks_dispatch_but_resume_keeps_original_terms(self):
        self.store.ledger.halt()
        self.assertEqual(self.run_job()['phase'], 'PAUSED_BEFORE_PAYMENT')
        self.assertEqual(self.rail.payments, 0)
        self.store.ledger.resume()
        self.assertEqual(self.run_job()['phase'], 'COMPLETED')
        self.assertEqual(self.rail.payments, 1)

    def test_explicit_probe_purpose_is_required(self):
        with self.assertRaises(ValueError):
            self.workflow.run('not-approved', self.task, 'http://127.0.0.1:8092')
        self.assertEqual(self.bank.calls, [])

    def test_funding_deposit_and_no_optimistic_float_reuse(self):
        self.rail.spendable = 0
        self.assertEqual(self.run_job()['phase'], 'COMPLETED')
        self.assertEqual(self.rail.deposits, 1)

    def test_receipt_mismatch_prevents_capture(self):
        original = self.rail.pay
        def tampered(key, quote):
            result = original(key, quote)
            result['receipt']['invoice']['recipient'] = 'wrong_seller'
            return result
        self.rail.pay = tampered
        with self.assertRaises(ValueError):
            self.run_job()
        self.assertFalse(any(c[1].endswith('/capture') for c in self.bank.calls))

    def test_resource_url_binds_public_task_and_rejects_url_credentials(self):
        url = resource_url('http://127.0.0.1:8092', self.task)
        self.assertIn('/inference/', url)
        self.assertNotEqual(url, resource_url('http://127.0.0.1:8092', Task('changed', self.task.kind, self.task.source)))
        for origin in ('http://untrusted.example', 'https://user:pass@example.com', 'http://127.0.0.1:8092/?other=1'):
            with self.assertRaises(ValueError):
                resource_url(origin, self.task)


if __name__ == '__main__':
    unittest.main()
