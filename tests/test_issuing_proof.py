import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from tests.test_card_rail import Client as CardClient
from touchstone.card_rail import CardRail
from touchstone.holds import OperationJournal, OutcomeUnknown
from touchstone.ledger import PolicyError
from tools.run_issuing_proof import execute, fingerprint, prepare_plan, reconcile_delegate


class Client(CardClient):
    def __init__(self):
        super().__init__()
        self.holder = None
        self.lose_holder = False
        self.holder_type = 'DELEGATE'

    def request(self, method, path, body=None, api_version=None):
        if path.startswith('/api/v1/issuing/cardholders'):
            self.calls.append((method, path))
            if method == 'POST':
                self.holder = {'cardholder_id': 'delegate_fixture', 'status': 'READY', **copy.deepcopy(body)}
                if self.lose_holder:raise OSError('Lost delegate response')
            if '?' in path:return {'has_more': False, 'items': [self.holder] if self.holder else []}
            return copy.deepcopy(self.holder)
        return super().request(method, path, body, api_version)


class IssuingProofTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.client = Client()
        self.journal = OperationJournal(Path(temp.name)/'issuing.sqlite')
        self.plan = prepare_plan(self.client)
        self.approval = 'APPROVE SANDBOX ISSUING '+fingerprint(self.plan)[:16]

    def posts(self):
        return [path for method, path in self.client.calls if method == 'POST']

    def test_no_business_call_before_exact_approval_or_after_changed_terms(self):
        with self.assertRaises(PolicyError):execute(self.client, self.journal, self.plan, None)
        changed = copy.deepcopy(self.plan)
        changed['card']['cap_micro_usd'] = 20000
        with self.assertRaises(PolicyError):
            execute(self.client, self.journal, changed, 'APPROVE SANDBOX ISSUING '+fingerprint(changed)[:16])
        self.assertEqual(self.client.calls, [])

    def test_one_delegate_one_card_and_read_only_replay(self):
        result = execute(self.client, self.journal, self.plan, self.approval)
        self.assertEqual(result['phase'], 'CARD_CONTROLS_VERIFIED')
        self.assertEqual(result['card']['authorization_controls']['transaction_limits']['limits'][0]['amount'], .01)
        self.assertFalse(self.client.card['is_personalized'])
        execute(self.client, self.journal, self.plan, self.approval)
        self.assertEqual(self.posts(), ['/api/v1/issuing/cardholders/create', '/api/v1/issuing/cards/create'])
        self.assertFalse(any('/details' in path for _, path in self.client.calls))
        self.assertEqual(result['merchant_payments'], 0)

    def test_lost_delegate_response_requires_read_reconciliation_without_recreation(self):
        self.client.lose_holder = True
        for _ in range(2):
            with self.assertRaises(OutcomeUnknown):execute(self.client, self.journal, self.plan, self.approval)
        self.assertEqual(len(self.posts()), 1)
        holder = reconcile_delegate(self.client, self.journal, self.plan)
        self.assertEqual(holder['status'], 'READY')
        execute(self.client, self.journal, self.plan, self.approval)
        self.assertEqual(len(self.posts()), 2)

    def test_lost_card_response_never_repeats_either_creation(self):
        self.client.lose = True
        for _ in range(2):
            with self.assertRaises(OutcomeUnknown):execute(self.client, self.journal, self.plan, self.approval)
        self.assertEqual(len(self.posts()), 2)
        runtime = self.journal.get(self.plan['scope'], 'approved_plan')
        import json
        expiry = json.loads(runtime['response'])['expires_at']
        CardRail(self.client, self.journal).reconcile(self.plan['scope'], 'delegate_fixture',
            self.plan['card']['created_by'], 10000, 'USD', expiry, personalized=False)
        self.assertEqual(len(self.posts()), 2)

    def test_expired_original_terms_do_not_gain_a_fresh_expiry(self):
        execute(self.client, self.journal, self.plan, self.approval)
        self.journal.observe_raw(self.plan['scope'], 'approved_plan',
            {'expires_at': (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()})
        with self.assertRaises(PolicyError):execute(self.client, self.journal, self.plan, self.approval)
        self.assertEqual(len(self.posts()), 2)
