import json
from pathlib import Path
import tempfile
import unittest

from touchstone.server import read_live_policy_runs


class LiveEvidenceTests(unittest.TestCase):
    def test_dashboard_projection_shows_measured_metrics_without_raw_jobs_or_secrets(self):
        report = {"mode": "TESTNET", "scope": "local-run", "seed": 42, "steps": 1,
                  "task_digest": "d" * 64, "observed_at": 1000, "paid_steps": 2,
                  "customer_captured_micro_usd": 0, "customer_hold": "SIMULATED", "simulator_fallbacks": 0,
                  "measured_cost": {"provider_spend_micro_usd": 40000, "verification_spend_micro_usd": 2000,
                    "total_micro_usd": 42000, "verified_correct_steps": 1,
                    "cost_per_verified_correct_micro_usd": 42000, "merchant_absorbed_failure_micro_usd": 11000,
                    "hosted_token_usage": {"input_tokens": 30, "output_tokens": 5},
                    "hosted_api_dollar_cost_included": False},
                  "snapshot": {"jobs": [{"policy": "real-touchstone", "status": "COMPLETED"}],
                               "reconciliation": {"matched": True}, "attempts": [{"output": "private task answer"}]},
                  "provider_url": "http://private-provider", "api_key": "do-not-serve"}
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "report.json").write_text(json.dumps(report), encoding="utf-8")
            result = read_live_policy_runs(temp)
        self.assertEqual(result["mode"], "LIVE_TESTNET_PROVIDER_POLICIES")
        self.assertEqual(len(result["runs"]), 1)
        row = result["runs"][0]
        self.assertEqual(row["policy"], "real-touchstone")
        self.assertEqual(row["total_micro_usd"], 42000)
        self.assertTrue(row["reconciled"])
        self.assertNotIn("snapshot", row)
        self.assertNotIn("provider_url", row)
        self.assertNotIn("api_key", json.dumps(result))

    def test_dashboard_does_not_promote_simulator_result_to_live_evidence(self):
        report = {"mode": "SIMULATED", "snapshot": {"jobs": [{"policy": "real-touchstone"}]}}
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "simulated.json").write_text(json.dumps(report), encoding="utf-8")
            result = read_live_policy_runs(temp)
        self.assertEqual(result["runs"], [])


if __name__ == "__main__":
    unittest.main()
