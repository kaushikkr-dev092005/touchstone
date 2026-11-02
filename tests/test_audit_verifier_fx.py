"""Audit regression tests: verifier source contract, purchase gating, invoice-consistency
extraction, and Airwallex FX safety. See docs/audit/BUG_FIX_REPORT.md."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from touchstone.engine import Engine
from touchstone.fx import ConversionRejected, FxJournal, execute_conversion, quote_is_expired, spend_report
from touchstone.invoice_consistency import QTY_RE, make_invoice_consistency_case
from touchstone.ledger import Ledger
from touchstone.payments import MockRail
from touchstone.providers import quotes
from touchstone.treasury import AirwallexSandbox
from touchstone.verifier import check, source_supported
from touchstone.workload import Task, generate


class InvoiceConsistencyExtractionTests(unittest.TestCase):
    def setUp(self):
        self.task, self.good = make_invoice_consistency_case(5, 4)

    def test_correct_extraction_still_passes(self):
        self.assertTrue(check(self.task, self.good)["passed"])

    def test_garbled_quantity_answered_inconsistent_is_rejected(self):
        bad = deepcopy(self.good)
        bad["line_items"][0]["quantity"] += 1
        bad["finding"] = "INCONSISTENT"
        verdict = check(self.task, bad)
        self.assertFalse(verdict["passed"])
        self.assertIn("differ from the cited source", verdict["reason"])

    def test_every_line_total_perturbed_answered_inconsistent_is_rejected(self):
        bad = deepcopy(self.good)
        for row in bad["line_items"]:
            row["line_total_cents"] += 7
        bad["finding"] = "INCONSISTENT"
        self.assertFalse(check(self.task, bad)["passed"])

    def test_genuinely_inconsistent_source_with_exact_extraction_passes(self):
        task, output = make_invoice_consistency_case(44, 6, inconsistent=True)
        self.assertEqual(output["finding"], "INCONSISTENT")
        self.assertTrue(check(task, output)["passed"])

    def test_fractional_quantity_is_not_read_as_a_whole_number(self):
        self.assertIsNone(QTY_RE.search("ITEM-1 Qty: 5.5 unit price: USD 1.00"))
        self.assertEqual(QTY_RE.search("ITEM-1 Qty: 5 unit price: USD 1.00").group(1), "5")
        self.assertEqual(QTY_RE.search("ITEM-1 Qty: 5. Unit price").group(1), "5")


class VerifierSourceContractTests(unittest.TestCase):
    def test_non_usd_invoice_cannot_be_accepted_as_usd(self):
        task = Task("t", "invoice", {"text": "Invoice INV-1. Currency EUR. Quantity 2. Unit price 100 cents. Tax 0 cents."})
        verdict = check(task, {"invoice_id": "INV-1", "currency": "USD", "total_cents": 200})
        self.assertFalse(verdict["passed"])
        self.assertFalse(verdict["retryable"])
        self.assertFalse(source_supported(task)[0])

    def test_source_defects_are_not_retryable_and_never_buyable(self):
        cases = [Task("a", "invoice", {"text": "Invoice INV-1. Currency USD. Quantity 2. Unit price 100 cents."}),
                 Task("b", "arithmetic", {"amounts_cents": [True, True], "discount_cents": 0}),
                 Task("c", "arithmetic", {"amounts_cents": [100], "discount_cents": 500}),
                 Task("d", "mystery", {"text": "x"})]
        for task in cases:
            with self.subTest(task=task.id):
                verdict = check(task, {"total_cents": 1})
                self.assertFalse(verdict["passed"])
                self.assertFalse(verdict["retryable"])
                self.assertFalse(source_supported(task)[0])

    def test_supported_generated_tasks_are_unchanged(self):
        tasks, truth = generate(42, 60)
        for task in tasks:
            self.assertTrue(source_supported(task)[0], task.id)
            self.assertTrue(check(task, truth[task.id])["passed"], task.id)

    def test_contracted_negation_abstains(self):
        task = Task("t", "classification", {"text": "I wasn" + chr(39) + "t charged twice, thanks."})
        self.assertFalse(source_supported(task)[0])
        self.assertFalse(check(task, {"label": "billing"})["passed"])


class EnginePurchaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.ledger, self.rail = Ledger(root / "l.sqlite"), MockRail(root / "r.sqlite")
        self.engine = Engine(self.ledger, self.rail)

    def run_job(self, task, policy="touchstone"):
        return self.ledger.create_run([{"seed": 42, "policy": policy, "hold": 1000000, "allocation": 500000,
                                        "price_cap": 60000, "tasks": [task.public()]}], 1000000)

    def test_unverifiable_source_is_never_purchased(self):
        task = Task("bad", "invoice", {"text": "Invoice INV-1. Currency USD. Quantity 2. Unit price 100 cents."})
        snapshot = self.engine.run(self.run_job(task))
        self.assertEqual(snapshot["attempts"], [])
        self.assertEqual(self.rail.receipts(), [])
        self.assertEqual(snapshot["jobs"][0]["status"], "PAUSED_REVIEW")
        self.assertEqual(snapshot["jobs"][0]["spent"], 0)

    def test_voided_reservation_does_not_consume_the_only_attempt(self):
        task = Task("only", "arithmetic", {"amounts_cents": [100, 200], "discount_cents": 0})
        run = self.run_job(task, policy="always-cheapest")
        job = self.ledger.jobs(run)[0]["id"]
        key = self.ledger.reserve(job, task, 0, quotes(42, 0)[0], 1000)
        self.ledger.void(key, "fixture: rail authoritatively confirmed no payment")
        snapshot = self.engine.run(run)
        bought = [a for a in snapshot["attempts"] if a["state"] != "VOID"]
        self.assertEqual(len(bought), 1)
        self.assertEqual(bought[0]["attempt"], 1)
        self.assertEqual(len(self.rail.receipts()), 1)


class FxFakeClient:
    def __init__(self):
        self.create_count = 0
        self.conversions, self.history = [], []
        self.rejection = None

    def current_balances(self):
        return [{"account_type": "cash", "currency": "USD", "available_amount": 8.0}]

    def create_conversion(self, quote, request_id):
        self.create_count += 1
        if self.rejection:
            raise self.rejection
        conversion = {"conversion_id": "c1", "request_id": request_id, "quote_id": quote["quote_id"],
                      "status": "SETTLED", "sell_currency": "USD", "sell_amount": "1.00",
                      "buy_currency": "EUR", "buy_amount": "0.92"}
        self.conversions = [conversion]
        self.history = [{"source_type": "CONVERSION", "source": "c1", "transaction_type": "CONVERSION_SELL", "currency": "USD", "amount": -1.0},
                        {"source_type": "CONVERSION", "source": "c1", "transaction_type": "CONVERSION_BUY", "currency": "EUR", "amount": 0.92}]
        return conversion

    def conversions_by_request_id(self, request_id):
        return [c for c in self.conversions if c["request_id"] == request_id]

    def conversion_balance_history(self, request_id):
        return self.history


class Rejected(Exception):
    status = 400


FX_QUOTE = {"quote_id": "q1", "sell_currency": "USD", "buy_currency": "EUR", "sell_amount": 1.0,
            "buy_amount": 0.92, "dealt_currency": "USD"}
ENV = {"AIRWALLEX_CLIENT_ID": "c", "AIRWALLEX_API_KEY": "k", "AIRWALLEX_ACCOUNT_ID": "a"}


class FxSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = FxJournal(Path(self.temp.name) / "fx.sqlite")
        self.client = FxFakeClient()

    def test_retry_of_a_rejected_request_raises_instead_of_looking_successful(self):
        self.client.rejection = Rejected("quote_expired")
        with self.assertRaises(Rejected):
            execute_conversion(self.client, self.journal, FX_QUOTE, "req-1")
        self.assertEqual(self.journal.get("req-1")["state"], "REJECTED")
        with self.assertRaises(ConversionRejected):
            execute_conversion(self.client, self.journal, FX_QUOTE, "req-1")
        self.assertEqual(self.client.create_count, 1)

    def test_expired_quote_is_refused_before_any_journal_row_or_request(self):
        stale = {**FX_QUOTE, "valid_to_at": "2020-01-01T00:00:00+0000"}
        with self.assertRaisesRegex(ValueError, "expired"):
            execute_conversion(self.client, self.journal, stale, "req-2")
        self.assertIsNone(self.journal.get("req-2"))
        self.assertEqual(self.client.create_count, 0)

    def test_expiry_parsing_accepts_airwallex_and_iso_forms_and_ignores_unknown(self):
        future = datetime.now(timezone.utc) + timedelta(minutes=10)
        for text in (future.strftime("%Y-%m-%dT%H:%M:%S+0000"), future.isoformat(), future.strftime("%Y-%m-%dT%H:%M:%SZ")):
            self.assertFalse(quote_is_expired({"valid_to_at": text}), text)
        self.assertTrue(quote_is_expired({"valid_to_at": "2020-01-01T00:00:00Z"}))
        self.assertTrue(quote_is_expired({"valid_to_at": "2020-01-01T00:00:00+0000"}))
        self.assertFalse(quote_is_expired({"valid_to_at": "not a date"}))
        self.assertFalse(quote_is_expired({}))

    def test_local_validation_failure_does_not_burn_the_request_id(self):
        class Strict(FxFakeClient):
            def validate_conversion(self, quote, request_id):
                raise ValueError("Invalid FX quote")
        client = Strict()
        with self.assertRaisesRegex(ValueError, "Invalid FX quote"):
            execute_conversion(client, self.journal, FX_QUOTE, "req-3")
        self.assertIsNone(self.journal.get("req-3"))
        self.assertEqual(client.create_count, 0)

    def test_wallet_history_with_flipped_signs_does_not_reconcile(self):
        execute_conversion(self.client, self.journal, FX_QUOTE, "req-4")
        self.assertEqual(spend_report(self.client, self.journal, "req-4")["reconciliation"], "MATCHED_WALLET_HISTORY")
        self.client.history[0]["amount"], self.client.history[1]["amount"] = 1.0, -0.92
        self.assertEqual(spend_report(self.client, self.journal, "req-4")["reconciliation"], "MISMATCH_WALLET_HISTORY")

    def test_quote_amount_must_match_the_requested_sell_amount(self):
        with patch.dict(os.environ, ENV):
            client = AirwallexSandbox()
        client.request = lambda method, path, body=None: {**FX_QUOTE, "sell_amount": 4000000.0}
        with self.assertRaisesRegex(ValueError, "sell amount differs"):
            client.create_fx_quote("USD", "EUR", "1.00")
        client.request = lambda method, path, body=None: {**FX_QUOTE, "sell_amount": 1.0}
        self.assertEqual(client.create_fx_quote("USD", "EUR", "1.00")["quote_id"], "q1")

    def test_conversion_validation_runs_without_network(self):
        with patch.dict(os.environ, ENV):
            client = AirwallexSandbox()
        client.request = lambda *a, **k: self.fail("validation must not call the network")
        client.validate_conversion(FX_QUOTE, "req-5")
        with self.assertRaises(ValueError):
            client.validate_conversion({**FX_QUOTE, "buy_currency": "USD"}, "req-5")


if __name__ == "__main__":
    unittest.main()
