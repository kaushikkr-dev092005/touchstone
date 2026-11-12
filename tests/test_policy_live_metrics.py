"""Counters over saved live evidence; no benchmark or model execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from tools.finalize_policy_live import actual_metrics

ROOT=Path(__file__).resolve().parent.parent


class RealPolicyMetrics(unittest.TestCase):
    def setUp(self):
        self.report=json.loads((ROOT/'bench/results/m4-v2/live-report.json').read_text())

    def test_original_stop_is_incomplete_and_hypothetical_fees_are_excluded(self):
        r=actual_metrics(self.report)
        self.assertFalse(r['complete']);self.assertFalse(r['live_gate_passed'])
        self.assertEqual((r['completed_outcomes'],r['actual_paid_receipts'],r['provider_micro_usdz']),(12,3,25000))
        self.assertFalse(r['simulated_costs_included'])
        self.assertEqual(r['global_conservative_credit_exposure_micro_usd'],2919117)

    def test_complete_flag_cannot_replace_missing_outcomes(self):
        self.report.update(complete=True,live_gate_passed=True)
        r=actual_metrics(self.report)
        self.assertFalse(r['complete']);self.assertFalse(r['controls']['at_least_30_actual_paid_receipts'])
        self.assertFalse(r['live_gate_passed'])

    def test_mock_report_is_never_relabelled_live(self):
        self.report.update(label='MOCK',mode='MOCK')
        with self.assertRaises(ValueError):actual_metrics(self.report)

    def test_duplicate_paid_receipt_and_cost_mismatch_are_rejected(self):
        paid=[r for r in self.report['calls'].values() if r.get('receipt_id')]
        paid[1]['receipt_id']=paid[0]['receipt_id']
        with self.assertRaises(ValueError):actual_metrics(self.report)
        self.setUp();self.report['confirmed_provider_micro_usdz']+=1
        with self.assertRaises(ValueError):actual_metrics(self.report)

    def test_duplicate_outcome_is_rejected(self):
        self.report['rows'].append(deepcopy(self.report['rows'][0]))
        with self.assertRaises(ValueError):actual_metrics(self.report)
