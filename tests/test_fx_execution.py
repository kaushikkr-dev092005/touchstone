from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from touchstone.card_rail import CardRail
from touchstone.fx_execution import execute_preferred
from touchstone.holds import OperationJournal, OutcomeUnknown
from touchstone.ledger import PolicyError
from touchstone.merchant import MerchantAdapter, MerchantError, SignedIntentMerchant
from tests.test_card_rail import Client as CardClient

NOW = 1_000_000.0


class Merchant(MerchantAdapter):
    name = 'fixture-merchant'

    def __init__(self, fail=False, settle=None):
        self.calls, self.fail, self.settle = [], fail, settle

    def charge(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise MerchantError('merchant offline')
        return {'adapter': self.name, 'merchant_acknowledged': True, **kwargs}

    def confirm(self, receipt):
        return self.settle


class Balances:
    def __init__(self, rows):
        self.rows = rows

    def current_balances(self):
        return self.rows


def offer(provider='hosted-premium', currency='USD', price=10000, label='MEASURED'):
    return {'provider': provider, 'rail': 'AIRWALLEX_CARD', 'price_micro': price, 'currency': currency, 'label': label,
            'fx_fee_budget_micro': 0, 'rail_fee_budget_micro': 0, 'quality_lower_bound': '0.99', 'latency_ms': 100,
            'qualification_current': True, 'fees_bounded': True, 'funded_fiat_account': True}


class FxExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.client = CardClient()
        self.journal = OperationJournal(root / 'journal.sqlite')
        self.rail = CardRail(self.client, self.journal)
        expiry = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        self.rail.issue('card1', 'holder', 'Operator', 10000, 'USD', expiry, execute=True)
        self.merchant = Merchant(settle={'transaction': 'txn_fixture'})
        self.funds = Balances([{'currency': 'USD', 'available_amount': 5.0}])
        self.approval = {'scope': 'buy1', 'provider': 'hosted-premium', 'approver': 'Operator',
                         'max_effective_cost_micro': 10000, 'expires_at': NOW + 600}

    def run_it(self, **overrides):
        args = dict(offers=[offer()], rates=[], scope='buy1', approval=self.approval, card_rail=self.rail,
                    card_scope='card1', adapters={'hosted-premium': self.merchant}, funding_client=self.funds,
                    journal=self.journal, execute=True, now=NOW, budget_micro=1000000)
        args.update(overrides)
        return execute_preferred(**args)

    def test_dispatches_once_after_every_gate_and_is_idempotent(self):
        result = self.run_it()
        self.assertEqual((result['payment']['merchant_payment_completed'], result['conversions_created']), (True, 0))
        self.assertEqual(len(self.merchant.calls), 1)
        again = self.run_it()
        self.assertTrue(again['idempotent_replay'])
        self.assertEqual(len(self.merchant.calls), 1)

    def test_every_gate_blocks_before_the_merchant_is_called(self):
        cases = [dict(execute=False),
                 dict(approval={**self.approval, 'max_effective_cost_micro': 9999}),
                 dict(approval={**self.approval, 'expires_at': NOW - 1}),
                 dict(approval={**self.approval, 'provider': 'local-gpu'}),
                 dict(approval={}),
                 dict(offers=[offer(label='SIMULATED')]),
                 dict(funding_client=Balances([{'currency': 'USD', 'available_amount': 0.005}])),
                 dict(funding_client=Balances([{'currency': 'EUR', 'available_amount': 50}])),
                 dict(adapters={})]
        for case in cases:
            with self.assertRaises((PolicyError, ValueError)):
                self.run_it(**case)
        self.assertEqual(self.merchant.calls, [])

    def test_currency_mismatch_never_converts(self):
        eur = offer(currency='EUR', price=10000)
        rate = {'provider_currency': 'EUR', 'budget_currency': 'USD', 'rate_numerator': 11, 'rate_denominator': 10,
                'expires_at': NOW + 60, 'quote_id': 'q1', 'label': 'MEASURED', 'application_fees_disclosed': True}
        with self.assertRaisesRegex(PolicyError, 'currency'):
            self.run_it(offers=[eur], rates=[rate], funding_client=Balances([{'currency': 'EUR', 'available_amount': 50}]),
                        approval={**self.approval, 'max_effective_cost_micro': 20000})
        self.assertEqual(self.merchant.calls, [])

    def test_merchant_failure_is_unknown_and_never_retried(self):
        self.merchant.fail = True
        for _ in range(2):
            with self.assertRaises(OutcomeUnknown):
                self.run_it()
        self.assertEqual(len(self.merchant.calls), 1)

    def test_acknowledgement_without_settlement_is_not_a_completed_payment(self):
        self.merchant.settle = None
        result = self.run_it()
        self.assertTrue(result['payment']['merchant_acknowledged'])
        self.assertFalse(result['payment']['settlement_verified'])
        self.assertFalse(result['payment']['merchant_payment_completed'])

    def test_card_must_be_large_enough_for_the_exact_amount(self):
        with self.assertRaises(PolicyError):
            self.run_it(offers=[offer(price=20000)], approval={**self.approval, 'max_effective_cost_micro': 20000})


class SignedIntentMerchantTests(unittest.TestCase):
    def merchant(self, response):
        class Response:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, n):
                return json.dumps(self.body).encode()

        def opener(request, timeout):
            return Response(response)
        return SignedIntentMerchant('http://127.0.0.1:9000', 'agent', 'unused.pem', signer=lambda *a: {'signature': 'x'}, opener=opener)

    def test_requires_a_matching_verified_acknowledgement(self):
        intent = {'job_id': 'j', 'intent': 'purchase', 'currency': 'USD', 'amount_minor': 1}
        ok = {'signature_verified': True, 'intent_verified': True, 'replay_protected': True, 'intent': intent,
              'identity_trust': 'KEY_DIRECTORY'}
        receipt = self.merchant(ok).charge(job_id='j', card_id='c', amount_micro=10000, currency='USD')
        self.assertTrue(receipt['merchant_acknowledged'])
        for bad in ({**ok, 'replay_protected': False}, {**ok, 'intent': {**intent, 'amount_minor': 2}}, {}):
            with self.assertRaises(MerchantError):
                self.merchant(bad).charge(job_id='j', card_id='c', amount_micro=10000, currency='USD')

    def test_origin_must_be_https_or_loopback_without_credentials(self):
        for bad in ('http://merchant.example', 'https://u:p@merchant.example', 'https://merchant.example/x', 'ftp://127.0.0.1'):
            with self.assertRaises(ValueError):
                SignedIntentMerchant(bad, 'k', 'f')
        self.assertEqual(SignedIntentMerchant('https://merchant.example', 'k', 'f').authority, 'merchant.example')


if __name__ == '__main__':
    unittest.main()
