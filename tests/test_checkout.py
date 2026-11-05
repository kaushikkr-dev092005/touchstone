import copy
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs

from touchstone.checkout import HostedCheckoutWorkflow
from touchstone.holds import OperationJournal, OutcomeUnknown, SandboxHoldWorkflow


class FakeCheckout:
    account_id = "acct_fixture"

    def __init__(self, lose_create=False):
        self.calls = []
        self.session = None
        self.intent = None
        self.lose_create = lose_create

    def request(self, method, path, body=None, api_version=None):
        self.calls.append((method, path, copy.deepcopy(body), api_version))
        if path.endswith("/checkout_sessions/create"):
            self.session = {
                "id": "bco_fixture",
                "mode": "PAYMENT",
                "status": "ACTIVE",
                "account_id": self.account_id,
                "currency": "USD",
                "expires_at": "2026-10-30T12:00:00Z",
                "url": "https://checkout.airwallex.com/pay?s=DO_NOT_STORE",
                "metadata": copy.deepcopy(body["metadata"]),
                "payment_intent_data": copy.deepcopy(body["payment_intent_data"]),
                "payment_options": copy.deepcopy(body["payment_options"]),
            }
            if self.lose_create:
                self.lose_create = False
                raise TimeoutError("response lost")
            return copy.deepcopy(self.session)
        if path.startswith("/api/v1/checkout/checkout_sessions?"):
            parsed = urlsplit(path)
            query = parse_qs(parsed.query)
            cursor = query.get("page_after", [None])[0]
            return {"items": [copy.deepcopy(self.session)] if self.session and not cursor else [], "page_after": None}
        if path == "/api/v1/checkout/checkout_sessions/bco_fixture":
            return copy.deepcopy(self.session)
        if path == "/api/v1/pa/payment_intents/int_fixture":
            if method == "POST" and path.endswith("/capture"):
                self.intent["captured_amount"] = body["amount"]
            return copy.deepcopy(self.intent)
        if path == "/api/v1/pa/payment_intents/int_fixture/capture":
            self.intent["captured_amount"] = body["amount"]
            return copy.deepcopy(self.intent)
        if path == "/api/v1/pa/payment_intents/int_fixture/cancel":
            self.intent["status"] = "CANCELLED"
            return copy.deepcopy(self.intent)
        raise AssertionError(f"Unexpected fixture request: {method} {path}")


class HostedCheckoutTests(unittest.TestCase):
    def test_official_sandbox_host_is_valid_but_lookalikes_are_refused(self):
        session = self.client.request('POST', '/api/v1/checkout/checkout_sessions/create', self.workflow._body('host-check', 1000000))
        session['url'] = 'https://checkout.sandbox.airwallex.com/pay?s=PRIVATE_FIXTURE'
        self.workflow._validate_session(session, 'host-check')
        for url in ('https://checkout.sandbox.airwallex.com.attacker.invalid/pay',
                    'https://checkout.sandbox.airwallex.com:444/pay',
                    'https://attacker.invalid@checkout.sandbox.airwallex.com/pay'):
            session['url'] = url
            with self.assertRaises(ValueError):
                self.workflow._validate_session(session, 'host-check')

    def test_account_separators_are_supported_without_allowing_header_injection(self):
        client = FakeCheckout()
        for account in ('acct_part_one', 'acct_part-one'):
            client.account_id = account
            HostedCheckoutWorkflow(client, None)._validate_scope('fixture', 1000000)
        client.account_id = 'acct_bad\r\nInjected: header'
        with self.assertRaises(ValueError):
            HostedCheckoutWorkflow(client, None)._validate_scope('fixture', 1000000)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "operations.sqlite"
        self.journal = OperationJournal(self.path)
        self.client = FakeCheckout()
        self.workflow = HostedCheckoutWorkflow(self.client, self.journal)

    def tearDown(self):
        self.temp.cleanup()

    def test_start_reuses_hosted_url_without_persisting_it(self):
        result = self.workflow.start("hosted-1")
        self.assertEqual(result["status"], "ACTIVE")
        self.assertEqual(result["checkout_url"], "https://checkout.airwallex.com/pay?s=DO_NOT_STORE")
        self.assertFalse(result["payment_created"])
        self.assertEqual(self.workflow.start("hosted-1")["checkout_session_id"], "bco_fixture")
        self.assertEqual(sum(c[0] == "POST" and c[1].endswith("/checkout_sessions/create") for c in self.client.calls), 1)
        with self.journal.connect() as db:
            stored = " ".join(str(tuple(row)) for row in db.execute("SELECT response FROM operations"))
        self.assertNotIn("DO_NOT_STORE", stored)
        self.assertNotIn("checkout.airwallex.com/pay", stored)
        self.assertTrue(all(c[3] == "2026-05-29" for c in self.client.calls if "/checkout_sessions" in c[1]))

    def test_completed_hosted_hold_reuses_intent_for_integrated_capture(self):
        self.workflow.start("hosted-2")
        self.client.session.update(status="COMPLETED", payment_intent_id="int_fixture")
        self.client.intent = {"id": "int_fixture", "status": "REQUIRES_CAPTURE", "amount": 1.0,
                              "currency": "USD", "captured_amount": 0, "merchant_order_id": "hosted-2"}
        result = self.workflow.status("hosted-2")
        self.assertTrue(result["authorization_ready"])
        self.assertEqual(result["intent"]["id"], "int_fixture")
        holds = SandboxHoldWorkflow(self.client, self.journal)
        self.assertTrue(holds.authorize("hosted-2")["ready"])
        closed = holds.run("hosted-2", capture=500000)
        self.assertTrue(closed["complete"])
        self.assertEqual(closed["captured_micro_usd"], 500000)
        self.assertFalse(any(c[0] == "POST" and c[1].endswith("/pa/payment_intents/create") for c in self.client.calls))
        self.assertEqual(sum(c[0] == "POST" and c[1].endswith("/capture") for c in self.client.calls), 1)
        self.assertEqual(sum(c[0] == "POST" and c[1].endswith("/cancel") for c in self.client.calls), 1)

    def test_unknown_create_recovers_by_scope_without_creating_another_session(self):
        self.client.lose_create = True
        with self.assertRaisesRegex(OutcomeUnknown, "unresolved"):
            self.workflow.start("hosted-3")
        result = self.workflow.start("hosted-3", recover=True)
        self.assertEqual(result["checkout_session_id"], "bco_fixture")
        self.assertEqual(sum(c[0] == "POST" and c[1].endswith("/checkout_sessions/create") for c in self.client.calls), 1)

    def test_capture_on_checkout_is_rejected_before_dispatch(self):
        self.workflow.start("hosted-4")
        self.client.session.update(status="COMPLETED", payment_intent_id="int_fixture")
        self.client.intent = {"id": "int_fixture", "status": "SUCCEEDED", "amount": 1.0,
                              "currency": "USD", "captured_amount": 1.0, "merchant_order_id": "hosted-4"}
        with self.assertRaisesRegex(ValueError, "captured funds"):
            self.workflow.status("hosted-4")
        self.assertFalse(any(c[0] == "POST" and c[1].endswith("/capture") for c in self.client.calls))

    def test_completed_operator_capture_can_be_read_without_another_write(self):
        self.workflow.start('hosted-recorded')
        self.client.session.update(status='COMPLETED', payment_intent_id='int_fixture')
        self.client.intent = {'id': 'int_fixture', 'status': 'REQUIRES_CAPTURE', 'amount': 1.0,
                              'currency': 'USD', 'captured_amount': 0, 'merchant_order_id': 'hosted-recorded'}
        self.workflow.status('hosted-recorded')
        SandboxHoldWorkflow(self.client, self.journal).run('hosted-recorded', 1000000, 10000)
        before = len(self.client.calls)
        result = self.workflow.status('hosted-recorded')
        self.assertTrue(result['complete'])
        self.assertFalse(result['authorization_ready'])
        self.assertEqual(result['captured_micro_usd'], 10000)
        self.assertTrue(all(c[0] == 'GET' for c in self.client.calls[before:]))

    def test_changed_captured_amount_is_not_accepted_as_recorded_capture(self):
        self.workflow.start('hosted-changed')
        self.client.session.update(status='COMPLETED', payment_intent_id='int_fixture')
        self.client.intent = {'id': 'int_fixture', 'status': 'REQUIRES_CAPTURE', 'amount': 1.0,
                              'currency': 'USD', 'captured_amount': 0, 'merchant_order_id': 'hosted-changed'}
        self.workflow.status('hosted-changed')
        SandboxHoldWorkflow(self.client, self.journal).run('hosted-changed', 1000000, 10000)
        self.client.intent['captured_amount'] = 0.02
        with self.assertRaisesRegex(ValueError, 'captured funds'):
            self.workflow.status('hosted-changed')

    def test_account_id_is_required_before_any_remote_call(self):
        client = FakeCheckout()
        client.account_id = None
        workflow = HostedCheckoutWorkflow(client, self.journal)
        with self.assertRaisesRegex(ValueError, "AIRWALLEX_ACCOUNT_ID"):
            workflow.start("hosted-5")
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
