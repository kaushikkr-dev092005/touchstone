import copy
from pathlib import Path
import tempfile
import unittest

from touchstone.holds import OperationJournal, OutcomeUnknown, SandboxHoldWorkflow
from touchstone.ledger import Ledger, PolicyError
from touchstone.workload import generate


class MultiIntentAirwallex:
    def __init__(self):
        self.intents, self.calls, self.fail_confirm = {}, [], False

    def request(self, method, path, body=None):
        self.calls.append((method, path))
        if method == 'GET':
            if '?' in path:
                return {'items': list(self.intents.values()), 'has_more': False}
            return copy.deepcopy(self.intents[path.rsplit('/', 1)[-1]])
        action = path.rsplit('/', 1)[-1]
        if action == 'create':
            intent_id = f'int_{len(self.intents) + 1}'
            self.intents[intent_id] = {'id': intent_id, 'status': 'REQUIRES_PAYMENT_METHOD', 'amount': body['amount'],
                                       'currency': 'USD', 'merchant_order_id': body['merchant_order_id'], 'captured_amount': 0}
            return copy.deepcopy(self.intents[intent_id])
        intent = self.intents[path.split('/')[-2]]
        if action == 'confirm':
            if self.fail_confirm:
                raise TimeoutError('lost')
            intent['status'] = 'REQUIRES_CAPTURE'
        return copy.deepcopy(intent)


class HoldIncreaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.client = MultiIntentAirwallex()
        self.workflow = SandboxHoldWorkflow(self.client, OperationJournal(root / 'ops.sqlite'))
        self.ledger = Ledger(root / 'ledger.sqlite')
        run = self.ledger.create_run([{'seed': 1, 'policy': 'touchstone', 'hold': 1000000, 'price_cap': 60000,
                                       'allocation': 300000, 'tasks': [t.public() for t in generate(1, 3)[0]]}], 1500000)
        self.job = self.ledger.jobs(run)[0]
        self.ledger.status(self.job['id'], 'PAUSED_POLICY', 'cap reached')
        self.workflow.authorize('parent', 1000000)

    def increase(self, **overrides):
        args = dict(parent_scope='parent', parent_hold=1000000, supplement_scope='parent-inc1', delta=500000,
                    ledger=self.ledger, job_id=self.job['id'], expected_version=1, new_budget=1500000,
                    new_price_cap=60000, new_allocation=500000, approver='Operator', reason='Customer approved more budget')
        args.update(overrides)
        return self.workflow.increase(**args)

    def test_adds_a_real_supplemental_authorization_then_raises_the_mandate(self):
        result = self.increase()
        self.assertTrue(result['remote_authorization_changed'])
        self.assertFalse(result['incremental_authorization_api_used'])
        self.assertEqual(result['remote']['supplement_intent_id'], 'int_2')
        job = self.ledger.get_job(self.job['id'])
        self.assertEqual((job['hold'], job['mandate_version']), (1500000, 2))
        events = [e for e in self.ledger.events(limit=1000) if e['kind'] == 'MANDATE_INCREASE_APPROVED']
        self.assertEqual(events[-1]['payload']['mode'], 'SANDBOX_SUPPLEMENTAL_AUTHORIZATION')
        self.assertEqual(events[-1]['payload']['remote_authorization']['parent_intent_id'], 'int_1')

    def test_invalid_ledger_change_is_refused_before_any_remote_write(self):
        writes = len([c for c in self.client.calls if c[0] == 'POST'])
        for bad in ({'expected_version': 9}, {'new_budget': 900000}, {'new_allocation': 9000000}):
            with self.assertRaises(PolicyError):
                self.increase(**bad)
        self.assertEqual(len([c for c in self.client.calls if c[0] == 'POST']), writes)
        self.assertEqual(self.ledger.get_job(self.job['id'])['hold'], 1000000)

    def test_uncertain_supplement_leaves_mandate_unchanged_and_never_recreates(self):
        self.client.fail_confirm = True
        with self.assertRaises(OutcomeUnknown):
            self.increase()
        self.assertEqual(self.ledger.get_job(self.job['id'])['hold'], 1000000)
        creates = len([c for c in self.client.calls if c[1].endswith('/create')])
        self.client.fail_confirm = False
        with self.assertRaises(OutcomeUnknown):
            self.increase()
        self.assertEqual(len([c for c in self.client.calls if c[1].endswith('/create')]), creates)

    def test_parent_must_be_uncaptured_and_scopes_distinct(self):
        self.client.intents['int_1']['captured_amount'] = 100000
        with self.assertRaises(OutcomeUnknown):
            self.increase()
        with self.assertRaises(ValueError):
            self.increase(supplement_scope='parent')
        with self.assertRaises(ValueError):
            self.increase(delta=0)


if __name__ == '__main__':
    unittest.main()
