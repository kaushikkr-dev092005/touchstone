import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from touchstone.local_tools import plan, solve
from touchstone.workload import Task


def citation_after(text, label, value):
    start = text.index(label) + len(label)
    if text[start:start + len(value)] != value:
        raise AssertionError(f"{value!r} does not follow {label!r}")
    return {"value": value, "start": start, "end": start + len(value)}


def invoice_exception_source():
    text = ("Invoice INV-100 for ACME against PO-42. Currency USD. Quantity 2. "
            "Unit price USD 50.00. Line total USD 100.00. Subtotal USD 100.00. "
            "Tax USD 8.00. Total USD 108.00.")
    return {
        "invoice": {
            "text": text,
            "fields": {
                "invoice_id": citation_after(text, "Invoice ", "INV-100"),
                "supplier_name": citation_after(text, "for ", "ACME"),
                "purchase_order_id": citation_after(text, "against ", "PO-42"),
                "currency": citation_after(text, "Currency ", "USD"),
                "subtotal_cents": citation_after(text, "Subtotal ", "USD 100.00"),
                "tax_cents": citation_after(text, "Tax ", "USD 8.00"),
                "total_cents": citation_after(text, "Total ", "USD 108.00"),
            },
            "items": [{
                "quantity": citation_after(text, "Quantity ", "2"),
                "unit_price_cents": citation_after(text, "Unit price ", "USD 50.00"),
                "line_total_cents": citation_after(text, "Line total ", "USD 100.00"),
            }],
        },
        "purchase_order": {
            "purchase_order_id": "PO-42",
            "supplier_name": "ACME",
            "currency": "USD",
            "authorized_cents": 20000,
        },
        "payments": [],
    }


class InvoiceExceptionChecks(unittest.TestCase):
    def task(self, source=None):
        return Task("invoice-exception", "invoice_exception", source or invoice_exception_source())

    def test_matching_invoice_returns_reviewable_candidate_without_payment(self):
        output = solve(self.task())
        self.assertEqual(output["finding"], "MATCHED_REQUIRES_HUMAN_APPROVAL")
        self.assertEqual(output["issues"], [])
        self.assertEqual(output["invoice_total_cents"], 10800)
        self.assertEqual(output["purchase_order_remaining_cents"], 20000)
        start, end = output["evidence_spans"]["fields"]["total_cents"]
        self.assertEqual(invoice_exception_source()["invoice"]["text"][start:end], "USD 108.00")
        self.assertEqual(output["payments_sent"], 0)
        self.assertFalse(output["live_purchase_authorized"])

        decision = plan(self.task())
        self.assertEqual(decision["decision"], "REVIEW_REQUIRED")
        self.assertEqual(decision["payments_sent"], 0)
        self.assertFalse(decision["live_purchase_authorized"])

    def test_mismatched_supplier_and_duplicate_payment_are_exceptions(self):
        source = invoice_exception_source()
        source["purchase_order"]["supplier_name"] = "OTHER"
        source["payments"].append({
            "payment_id": "PAY-1", "invoice_id": "INV-100", "purchase_order_id": "PO-42",
            "supplier_name": "ACME", "currency": "USD", "amount_cents": 10800, "status": "settled",
        })
        output = solve(self.task(source))
        self.assertEqual(output["finding"], "EXCEPTION_REQUIRES_HUMAN_REVIEW")
        self.assertIn("SUPPLIER_MISMATCH", output["issues"])
        self.assertIn("DUPLICATE_OR_IN_PROGRESS_PAYMENT", output["issues"])
        self.assertIn("PURCHASE_ORDER_LIMIT_EXCEEDED", output["issues"])
        self.assertEqual(output["payments_sent"], 0)

    def test_line_total_is_recomputed_from_cited_quantity_and_unit_price(self):
        source = invoice_exception_source()
        source["invoice"]["text"] = source["invoice"]["text"].replace(
            "Line total USD 100.00", "Line total USD 099.00")
        source["invoice"]["items"][0]["line_total_cents"] = citation_after(
            source["invoice"]["text"], "Line total ", "USD 099.00")
        output = solve(self.task(source))
        self.assertEqual(output["finding"], "EXCEPTION_REQUIRES_HUMAN_REVIEW")
        self.assertIn("LINE_TOTAL_MISMATCH", output["issues"])

    def test_invalid_citations_and_unsupported_money_fail_closed(self):
        source = invoice_exception_source()
        source["invoice"]["fields"]["total_cents"]["value"] = "USD 999.00"
        self.assertIsNone(solve(self.task(source)))

        source = invoice_exception_source()
        source["invoice"]["text"] = source["invoice"]["text"].replace(
            "Total USD 108.00", "Total 10800 cents")
        source["invoice"]["fields"]["total_cents"] = citation_after(
            source["invoice"]["text"], "Total ", "10800 cents")
        self.assertIsNone(solve(self.task(source)))

    def test_malformed_payment_status_fails_closed(self):
        source = invoice_exception_source()
        source["payments"].append({
            "payment_id": "PAY-1", "invoice_id": "INV-2", "purchase_order_id": "PO-42",
            "supplier_name": "ACME", "currency": "USD", "amount_cents": 100,
            "status": ["settled"],
        })
        self.assertIsNone(solve(self.task(source)))

    def test_plan_cli_keeps_invoice_exception_on_review_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            input_path = Path(temporary) / "task.json"
            output_path = Path(temporary) / "plan.json"
            input_path.write_text(json.dumps(self.task().public()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "touchstone", "plan", "--input", str(input_path),
                 "--output", str(output_path)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(report["decisions"][0]["decision"], "REVIEW_REQUIRED")
        self.assertEqual(report["decisions"][0]["output"]["finding"], "MATCHED_REQUIRES_HUMAN_APPROVAL")
        self.assertEqual(report["payments_sent"], 0)


if __name__ == "__main__":
    unittest.main()
