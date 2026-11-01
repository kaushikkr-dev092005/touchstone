from copy import deepcopy
import unittest

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


if __name__ == "__main__":
    unittest.main()
