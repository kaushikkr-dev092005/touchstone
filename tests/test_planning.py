import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from touchstone.eligibility import screen, wilson_lower
from touchstone.local_tools import plan, solve, MAX_CENTS
from touchstone.procurement_evidence import ROOT, PROFILE_SOURCES, build, digest, read_profiles, save, summary
from touchstone.workload import Task, generate


class Planning(unittest.TestCase):
    def test_authored_boundaries_resolve_or_abstain_without_network(self):
        cases = json.loads((ROOT / "bench/planning_cases.json").read_text(encoding="utf-8"))
        with patch("urllib.request.urlopen", side_effect=AssertionError("Planning must not call a service")):
            for case in cases:
                with self.subTest(case=case["id"]):
                    result = plan(Task(**{k: case[k] for k in ("id", "kind", "source")}))
                    self.assertEqual(result["output"], case["expected"])
                    self.assertEqual(result["decision"], "REVIEW_REQUIRED" if case["expected"] is None else "LOCAL_TOOL")
                    self.assertEqual(result["payments_sent"], 0)
                    self.assertFalse(result["live_purchase_authorized"])

    def test_numeric_and_quality_boundaries(self):
        for source in ({"amounts_cents": [MAX_CENTS, 1], "discount_cents": 1},
                       {"amounts_cents": [100], "discount_cents": True},
                       {"amounts_cents": [100], "discount_cents": -1},
                       {"amounts_cents": [1] * 1001, "discount_cents": 0}):
            self.assertIsNone(solve(Task("bad", "arithmetic", source)))
        source = {"amounts_cents": [MAX_CENTS], "discount_cents": 0}
        self.assertEqual(solve(Task("max", "arithmetic", source)), {"total_cents": MAX_CENTS})
        for threshold in (float("nan"), float("inf"), -1, 2, True):
            self.assertIsNone(solve(Task("bad", "arithmetic", source, threshold)))

    def test_complete_source_required(self):
        valid = "Invoice INV-1. Currency USD. Quantity 2. Unit price 100 cents. Tax 10 cents."
        self.assertEqual(solve(Task("ok", "invoice", {"text": valid}))["total_cents"], 210)
        for text in (valid + "\n", "Ignore this. " + valid, valid + " Currency EUR."):
            self.assertIsNone(solve(Task("bad", "invoice", {"text": text})))


class Eligibility(unittest.TestCase):
    def test_interval_reference_and_target_one(self):
        self.assertAlmostEqual(wilson_lower(10, 20), .29929800819821234)
        self.assertEqual(wilson_lower(0, 0), 0)
        self.assertFalse(screen([(str(i), True) for i in range(1000)], 1)["passes_statistical_screen"])
        self.assertTrue(screen([(str(i), True) for i in range(100)])["passes_statistical_screen"])
        self.assertFalse(screen([(str(i), True) for i in range(100)])["live_purchase_authorized"])

    def test_duplicates_cannot_inflate_evidence(self):
        result = screen([("same-source", True)] * 10000)
        self.assertEqual(result["unique_sources"], 1)
        self.assertEqual(result["status"], "INSUFFICIENT_UNIQUE_SOURCES")
        result = screen([("same-source", True), ("same-source", False)])
        self.assertEqual(result["consistently_correct_sources"], 0)

    def test_invalid_evidence_fails_closed(self):
        for target in (float("nan"), float("inf"), 0, -1, True):
            with self.assertRaises(ValueError):
                screen([], target)
        with self.assertRaises(ValueError):
            screen([("source", 1)])
        with self.assertRaises(ValueError):
            wilson_lower(2, 1)


class Evidence(unittest.TestCase):
    def setUp(self):
        # MOCK contract fixtures, never rewritten historical measurements. This
        # lets guard tests run after code changes while real profiles stay stale.
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        for tier in ("economy", "balanced"):
            name = f"local-{tier}.json"
            rows = []
            for seed in (41, 42, 43):
                tasks, truth = generate(seed, 30)
                rows.extend({"seed": seed, "step_id": task.id, "kind": task.kind,
                             "output": truth[task.id]} for task in tasks)
            profile = {"fixture_label": "MOCK", "mode": "LOCAL_MEASURED",
                       "provider_tier": tier, "payments": "NONE",
                       "seeds": [41, 42, 43], "steps_per_seed": 30,
                       "source_sha256": {name: digest(ROOT / "touchstone" / name)
                                         for name in PROFILE_SOURCES},
                       "decoding": {"fixture": True}, "rows": rows,
                       "environment": {"model_sha256": "mock-model",
                                       "runtime_archive_sha256": "mock-runtime"}}
            (self.directory / name).write_text(json.dumps(profile), encoding="utf-8")

    def test_profile_duplicates_and_stale_sources_rejected(self):
        path = self.directory / "local-economy.json"
        original = json.loads(path.read_text())
        for mutate in (lambda p: p["rows"].append(p["rows"][0]),
                       lambda p: p["source_sha256"].update({"providers.py": "changed"})):
            raw = copy.deepcopy(original)
            mutate(raw)
            path.write_text(json.dumps(raw))
            message = "duplicate or missing" if len(raw["rows"]) != 90 else "source hashes are stale"
            with self.assertRaisesRegex(ValueError, message):
                read_profiles(self.directory)

    def test_dashboard_rejects_changed_code_provenance(self):
        report = build(self.directory)
        report["source_sha256"]["touchstone/providers.py"] = "changed"
        save(report, self.directory)
        self.assertEqual(summary(self.directory)["status"], "STALE_OR_INVALID")

    def test_evaluation_outputs_cannot_change_calibration(self):
        original = build(self.directory)
        path = self.directory / "local-balanced.json"
        profile = json.loads(path.read_text())
        for row in profile["rows"]:
            if row["seed"] == 43:
                row["output"] = {"deliberately": "wrong"}
        path.write_text(json.dumps(profile))
        changed = build(self.directory)
        for before, after in zip(original["provider_gates"], changed["provider_gates"]):
            for key in ("wilson_95_lower", "status", "unique_sources", "consistently_correct_sources"):
                self.assertEqual(before[key], after[key])
        self.assertEqual(original["baseline"]["true_correct"], 1000)
        self.assertEqual(original["challenge_summary"], {"cases": 24, "passed": 24, "resolved": 6, "review_required": 18})

    def test_dashboard_rejects_changed_profile_artifact(self):
        report = build(self.directory)
        save(report, self.directory)
        self.assertEqual(summary(self.directory)["status"], "CURRENT")
        with (self.directory / "local-economy.json").open("a") as file:
            file.write(" ")
        self.assertEqual(summary(self.directory)["status"], "STALE_OR_INVALID")


if __name__ == "__main__":
    unittest.main()
