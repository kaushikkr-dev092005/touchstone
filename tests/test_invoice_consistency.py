from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from touchstone.benchmark import write_noisy_verification_chart
from touchstone.invoice_consistency import check_invoice_consistency, make_invoice_consistency_case, noisy_invoice_check
from touchstone.verifier import check


class InvoiceConsistency(unittest.TestCase):
    def test_cited_line_item_arithmetic_checks_without_answer_map(self):
        task, output = make_invoice_consistency_case(seed=43, line_count=8)
        self.assertTrue(check(task, output)["passed"])
        self.assertTrue(check_invoice_consistency(task, output)["passed"])

    def test_stated_total_discrepancy_is_detected(self):
        task, output = make_invoice_consistency_case(seed=44, line_count=6, inconsistent=True)
        self.assertEqual(output["finding"], "INCONSISTENT")
        self.assertTrue(check(task, output)["passed"])
        wrong = {**output, "finding": "CONSISTENT"}
        self.assertFalse(check(task, wrong)["passed"])

    def test_missing_or_forged_evidence_abstains(self):
        task, output = make_invoice_consistency_case(seed=45, line_count=5)
        forged = deepcopy(output)
        forged["line_items"][0]["unit_price_evidence"]["value"] = "USD 999.99"
        self.assertFalse(check(task, forged)["passed"])
        incomplete = deepcopy(output)
        incomplete["line_items"].pop()
        self.assertFalse(check(task, incomplete)["passed"])

    def test_noisy_spot_checker_reports_empirical_false_acceptance(self):
        task, output = make_invoice_consistency_case(seed=46, line_count=10)
        incorrect = deepcopy(output)
        incorrect["line_items"][0]["line_total_cents"] += 1
        incorrect["line_items"][1]["line_total_cents"] -= 1
        self.assertFalse(check(task, incorrect)["passed"])
        false_accepts = sum(noisy_invoice_check(task, incorrect, seed)["passed"] for seed in range(100))
        self.assertGreater(false_accepts, 65)
        self.assertLess(false_accepts, 95)
        self.assertTrue(all(noisy_invoice_check(task, output, seed)["passed"] for seed in range(20)))

    def test_chart_uses_reported_case_count(self):
        report = {
            "cases": 7,
            "exact_checker_false_accepts": 0,
            "noisy_checker": [
                {"sampled_rows": 1, "false_accept_rate": 0.5},
                {"sampled_rows": 2, "false_accept_rate": 0.25},
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            chart = Path(directory) / "chart.svg"
            write_noisy_verification_chart(report, chart)
            contents = chart.read_text(encoding="utf-8")
        self.assertIn("Exact checker: 0/7 injected cases", contents)
        self.assertNotIn("0/20 injected cases", contents)


if __name__ == "__main__":
    unittest.main()
