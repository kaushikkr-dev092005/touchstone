import copy
import json
from pathlib import Path
import tempfile
import unittest
from touchstone.holds import OperationJournal, OutcomeUnknown, SandboxHoldWorkflow, api_usd, micro_usd


class FakeAirwallex:
    def __init__(self, lose=None, pending=False):
        self.intent = None
        self.calls = []
        self.lose = lose
        self.pending = pending

    def request(self, method, path, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        if method == "GET":
            if "?" in path:
                return {"items": [self.intent] if self.intent else [], "has_more": False}
            return copy.deepcopy(self.intent)
        action = path.rsplit("/", 1)[-1]
        if action == "create":
            self.intent = {"id": "int_test123", "status": "REQUIRES_PAYMENT_METHOD", "amount": body["amount"], "currency": body["currency"], "merchant_order_id": body["merchant_order_id"], "captured_amount": 0, "client_secret": "DO_NOT_STORE"}
        elif action == "confirm":
            assert body["payment_method_options"]["card"] == {"authorization_type": "pre_auth", "auto_capture": False}
            self.intent["status"] = "PENDING_REVIEW" if self.pending else "REQUIRES_CAPTURE"
        elif action == "capture":
            self.intent["captured_amount"] = body["amount"]
            # Exercise explicit cancellation of remaining authorization.
            self.intent["status"] = "REQUIRES_CAPTURE"
        elif action == "cancel":
            self.intent["status"] = "CANCELLED"
        if action == self.lose:
            self.lose = None
            raise TimeoutError("Lost response after remote side effect")
        return copy.deepcopy(self.intent)


class Holds(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "operations.sqlite"
        self.journal = OperationJournal(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_hold_capture_cancel_and_repeat_without_second_write(self):
        client = FakeAirwallex()
        workflow = SandboxHoldWorkflow(client, self.journal)
        report = workflow.run("job-1")
        self.assertTrue(report["complete"])
        self.assertEqual(report["captured_micro_usd"], 500000)
        writes = [c for c in client.calls if c[0] == "POST"]
        self.assertEqual(len(writes), 4)
        self.assertEqual(len({c[2]["request_id"] for c in writes}), 4)
        workflow.run("job-1")
        self.assertEqual(len([c for c in client.calls if c[0] == "POST"]), 4)
        with self.journal.connect() as db:
            text = json.dumps([dict(r) for r in db.execute("SELECT * FROM operations")])
        for secret in ["DO_NOT_STORE", "4035501000000008", '"cvc"', "client_secret"]:
            self.assertNotIn(secret, text)

    def test_lost_create_is_recovered_by_order_without_second_create(self):
        client = FakeAirwallex(lose="create")
        workflow = SandboxHoldWorkflow(client, self.journal)
        with self.assertRaises(OutcomeUnknown):
            workflow.run("job-2")
        with self.assertRaises(OutcomeUnknown):
            workflow.run("job-2")
        self.assertTrue(workflow.run("job-2", recover=True)["complete"])
        self.assertEqual(sum(c[1].endswith("/create") for c in client.calls), 1)

    def test_create_recovery_reuses_original_request_id_when_list_is_delayed(self):
        class DelayedListing(FakeAirwallex):
            def request(self, method, path, body=None):
                if method == 'GET' and '?' in path:
                    return {'items':[], 'has_more':False}
                return super().request(method, path, body)
        client = DelayedListing(lose='create')
        workflow = SandboxHoldWorkflow(client, self.journal)
        with self.assertRaises(OutcomeUnknown):
            workflow.run('delayed-create')
        self.assertTrue(workflow.run('delayed-create', recover=True)['complete'])
        creates = [c for c in client.calls if c[1].endswith('/create')]
        self.assertEqual(len(creates), 2)
        self.assertEqual(creates[0][2], creates[1][2])

    def test_lost_capture_recovery_does_not_charge_again(self):
        client = FakeAirwallex(lose="capture")
        workflow = SandboxHoldWorkflow(client, self.journal)
        with self.assertRaises(OutcomeUnknown):
            workflow.run("job-3")
        self.assertTrue(workflow.run("job-3", recover=True)["complete"])
        self.assertEqual(sum(c[0] == "POST" and c[1].endswith("/capture") for c in client.calls), 1)

    def test_changed_terms_rejected_before_any_new_request(self):
        client = FakeAirwallex(lose="create")
        workflow = SandboxHoldWorkflow(client, self.journal)
        with self.assertRaises(OutcomeUnknown):
            workflow.run("job-4")
        before = len(client.calls)
        with self.assertRaises(ValueError):
            workflow.run("job-4", capture=600000, recover=True)
        self.assertEqual(len(client.calls), before)

    def test_pending_review_never_dispatches_capture(self):
        client = FakeAirwallex(pending=True)
        result = SandboxHoldWorkflow(client, self.journal).run("job-5")
        self.assertFalse(result["complete"])
        self.assertFalse(any(c[1].endswith("/capture") for c in client.calls))

    def test_rounding_and_limit_errors(self):
        self.assertEqual(micro_usd("0.50"), 500000)
        for value in [1001, -10000, True]:
            with self.assertRaises(ValueError):
                api_usd(value)
        for value in ["nan", "inf", "-1", "0.0000001"]:
            with self.assertRaises(ValueError):
                micro_usd(value)
        client = FakeAirwallex()
        with self.assertRaises(ValueError):
            SandboxHoldWorkflow(client, self.journal).run("job-6", hold=1000000, capture=1000001)
        self.assertEqual(client.calls, [])
