"""Regression tests for defects found in the 2 November 2026 audit.

Each test failed against the code as audited (see docs/audit/BUG_FIX_REPORT.md).
"""
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from touchstone.ledger import PolicyError
from touchstone.metal import MetalQuote
from touchstone.payments import MetalEngineRail
from touchstone.procurement_evidence import digest
from touchstone.providers import anthropic_inference
from touchstone.workload import Task

TASK = Task("t1", "arithmetic", {"amounts_cents": [1250, 775], "discount_cents": 25})


class FakeClient:
    """Per-origin quote behaviour; any attempt to pay is a test failure."""
    provider_url = "http://127.0.0.1:8092"

    def __init__(self, behaviours):
        self.behaviours = behaviours
        self.calls = []

    def quote(self, url):
        origin = url.split("/inference/")[0]
        self.calls.append(origin)
        behaviour = self.behaviours[origin]
        if isinstance(behaviour, Exception):
            raise behaviour
        return behaviour

    def pay(self, *args, **kwargs):
        raise AssertionError("A quote failure must never dispatch a payment")


def live_quote(provider, price=10000):
    return MetalQuote(f"quote-{provider}", provider, price, time.time() + 30, {"url": "u"})


class QuoteIsolationTests(unittest.TestCase):
    local, hosted = "http://127.0.0.1:8092", "http://127.0.0.1:8093"

    def rail(self, behaviours, expected=("local-gpu", "hosted-premium")):
        return MetalEngineRail("scope-audit", [self.local, self.hosted], client=FakeClient(behaviours),
                               expected_provider_ids=list(expected))

    def test_each_failure_class_skips_only_that_origin(self):
        failures = [ValueError("Metal quote exceeds the mandate or is expired"), KeyError("offer"),
                    TypeError("bad shape"), RuntimeError("Metal quote unavailable"),
                    PolicyError("Provider identity does not match its configured origin")]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                rail = self.rail({self.local: failure, self.hosted: live_quote("hosted-premium")})
                offers = rail.quote_for_task(TASK)
                self.assertEqual([offer.provider for offer in offers], ["hosted-premium"])
                self.assertEqual(rail.last_quote_errors[0]["error"], type(failure).__name__)

    def test_provider_claiming_the_wrong_identity_is_never_offered(self):
        rail = self.rail({self.local: live_quote("hosted-premium"), self.hosted: live_quote("hosted-premium")})
        offers = rail.quote_for_task(TASK)
        self.assertEqual([offer.provider for offer in offers], ["hosted-premium"])
        self.assertEqual(rail.last_quote_errors, [{"origin_index": 0, "error": "PolicyError",
                                                    "detail": "Provider identity does not match its configured origin"}])

    def test_errors_do_not_accumulate_across_quotes(self):
        rail = self.rail({self.local: ValueError("x"), self.hosted: live_quote("hosted-premium")})
        rail.quote_for_task(TASK)
        rail.client.behaviours[self.local] = live_quote("local-gpu")
        rail.quote_for_task(TASK)
        self.assertEqual(rail.last_quote_errors, [])

    def test_all_origins_unusable_returns_empty_list_not_exception(self):
        rail = self.rail({self.local: KeyError("offer"), self.hosted: TypeError("x")})
        self.assertEqual(rail.quote_for_task(TASK), [])
        self.assertEqual(len(rail.last_quote_errors), 2)


class DigestLineEndingTests(unittest.TestCase):
    def test_crlf_checkout_hashes_like_lf_original(self):
        with tempfile.TemporaryDirectory() as directory:
            lf, crlf = Path(directory, "lf.py"), Path(directory, "crlf.py")
            lf.write_bytes(b"a = 1\nb = 2\n")
            crlf.write_bytes(b"a = 1\r\nb = 2\r\n")
            self.assertEqual(digest(lf), digest(crlf))

    def test_content_changes_still_change_the_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            one, two = Path(directory, "one"), Path(directory, "two")
            one.write_bytes(b"a = 1\n")
            two.write_bytes(b"a = 2\n")
            self.assertNotEqual(digest(one), digest(two))

    def test_lone_carriage_returns_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            plain, lone = Path(directory, "plain"), Path(directory, "lone")
            plain.write_bytes(b"a\nb\n")
            lone.write_bytes(b"a\rb\n")
            self.assertNotEqual(digest(plain), digest(lone))


class LiveEvidenceIntegrityTests(unittest.TestCase):
    def report(self, **overrides):
        base = {"mode": "TESTNET", "scope": "s", "seed": 1, "steps": 1, "task_digest": "d" * 64, "observed_at": 1.0,
                "paid_steps": 1, "customer_captured_micro_usd": 0, "customer_hold": "SIMULATED",
                "simulator_fallbacks": 0,
                "measured_cost": {"provider_spend_micro_usd": 1, "verification_spend_micro_usd": 1,
                                  "total_micro_usd": 2, "verified_correct_steps": 1,
                                  "cost_per_verified_correct_micro_usd": 2, "merchant_absorbed_failure_micro_usd": 0,
                                  "hosted_token_usage": {}, "hosted_api_dollar_cost_included": False},
                "snapshot": {"jobs": [{"policy": "real-touchstone", "status": "COMPLETED"}],
                             "reconciliation": {"matched": True}}}
        base.update(overrides)
        return base

    def read(self, report):
        from touchstone.server import read_live_policy_runs
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "r.json").write_text(json.dumps(report), encoding="utf-8")
            return read_live_policy_runs(directory)["runs"]

    def test_clean_run_is_marked_valid_live_evidence(self):
        self.assertTrue(self.read(self.report())[0]["valid_live_evidence"])

    def test_simulator_fallbacks_or_customer_capture_are_flagged_not_trusted(self):
        for override in ({"simulator_fallbacks": 4}, {"customer_captured_micro_usd": 5000}):
            with self.subTest(override=override):
                self.assertFalse(self.read(self.report(**override))[0]["valid_live_evidence"])

    def test_non_integer_counters_are_dropped_rather_than_rendered(self):
        self.assertEqual(self.read(self.report(paid_steps="<img src=x onerror=alert(1)>")), [])
        self.assertEqual(self.read(self.report(simulator_fallbacks=True)), [])
        self.assertEqual(self.read(self.report(steps=-1)), [])


class InputHardeningTests(unittest.TestCase):
    def test_decimal_overflow_is_a_value_error_not_a_crash(self):
        from touchstone.holds import micro_usd
        from touchstone.server import usd_to_micros
        with self.assertRaises(ValueError):
            micro_usd("1e999999")
        with self.assertRaises(ValueError):
            usd_to_micros("1e999999")
        self.assertEqual(usd_to_micros("1.25"), 1250000)

    def test_non_object_readiness_artifact_counts_as_absent(self):
        from touchstone.readiness import _object
        with tempfile.TemporaryDirectory() as directory:
            for name, text in (("list.json", "[]"), ("bad.json", "{oops"), ("scalar.json", "7")):
                path = Path(directory, name)
                path.write_text(text, encoding="utf-8")
                self.assertEqual(_object(path), {}, name)
            good = Path(directory, "good.json")
            good.write_text('{"authenticated": true}', encoding="utf-8")
            self.assertEqual(_object(good), {"authenticated": True})
            self.assertEqual(_object(Path(directory, "missing.json")), {})


class HostedUsageTests(unittest.TestCase):
    def setUp(self):
        # No-network response parser unit tests; authorization has its own suite.
        p=patch('touchstone.procurement_approval.authorize_hosted_call');p.start();self.addCleanup(p.stop)
    def call(self, usage):
        response = {"model": "claude-sonnet-5", "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": '{"total_cents": 2000}'}], "usage": usage}
        opener = lambda request, timeout: io.BytesIO(json.dumps(response).encode())
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "ANTHROPIC_MODEL": "claude-sonnet-5"}):
            return anthropic_inference(TASK, opener)

    def test_null_cache_counters_are_zero_not_invalid(self):
        _, _, metadata = self.call({"input_tokens": 10, "output_tokens": 4,
                                    "cache_creation_input_tokens": None, "cache_read_input_tokens": None})
        self.assertEqual(metadata["usage"], {"input_tokens": 10, "output_tokens": 4,
                                             "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})

    def test_malformed_counters_are_still_rejected(self):
        for bad in ("12", True, -1, 1.5):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "usage metadata is invalid"):
                    self.call({"input_tokens": bad, "output_tokens": 1})

    def test_missing_usage_object_is_all_zero(self):
        _, _, metadata = self.call(None)
        self.assertEqual(sum(metadata["usage"].values()), 0)


if __name__ == "__main__":
    unittest.main()
