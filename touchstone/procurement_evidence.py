"""Reproducible, offline evidence for deciding whether inference is warranted."""
import hashlib
import json
from pathlib import Path
import statistics
import time

from .eligibility import screen, source_key
from .local_tools import plan, TOOL_VERSION
from .workload import Task, generate

ROOT = Path(__file__).resolve().parent.parent
PROFILE_SOURCES = ("providers.py", "verifier.py", "workload.py")
EVIDENCE_SOURCES = (*PROFILE_SOURCES, "local_tools.py", "eligibility.py", "procurement_evidence.py")
CALIBRATION_SEEDS = (41, 42)
EVALUATION_SEEDS = (43,)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_equal(actual, expected):
    try:
        return json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        return False


def read_profiles(directory):
    """Refuse stale, partial or mismatched artifacts before computing a gate."""
    profiles = {}
    hashes = {name: digest(ROOT / "touchstone" / name) for name in PROFILE_SOURCES}
    for tier in ("economy", "balanced"):
        path = Path(directory) / f"local-{tier}.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("source_sha256") != hashes:
            raise ValueError(f"{tier}: profile source hashes are stale; regenerate profiles")
        if raw.get("mode") != "LOCAL_MEASURED" or raw.get("provider_tier") != tier or raw.get("payments") != "NONE":
            raise ValueError(f"{tier}: invalid measured profile identity")
        if raw.get("seeds") != [*CALIBRATION_SEEDS, *EVALUATION_SEEDS] or raw.get("steps_per_seed") != 30:
            raise ValueError(f"{tier}: experiment requires the versioned 3 x 30 paired profile")
        keys = [(r["seed"], r["step_id"]) for r in raw["rows"]]
        expected = {(seed, t.id) for seed in raw["seeds"] for t in generate(seed, 30)[0]}
        if len(keys) != len(set(keys)) or set(keys) != expected:
            raise ValueError(f"{tier}: duplicate or missing profile cases")
        for row in raw["rows"]:
            task = next(t for t in generate(row["seed"], 30)[0] if t.id == row["step_id"])
            if row.get("kind") != task.kind or "output" not in row:
                raise ValueError(f"{tier}: malformed profile row")
        profiles[tier] = raw
    if profiles["economy"]["decoding"] != profiles["balanced"]["decoding"]:
        raise ValueError("Cannot compare different decoding configurations")
    return profiles


def build(directory=ROOT / "bench/results"):
    directory = Path(directory)
    profiles = read_profiles(directory)
    tasks, truths = {}, {}
    for seed in (*CALIBRATION_SEEDS, *EVALUATION_SEEDS):
        generated, truth = generate(seed, 30)
        tasks.update({(seed, t.id): t for t in generated})
        truths.update({(seed, key): value for key, value in truth.items()})
    gates = []
    for tier, profile in profiles.items():
        for kind in ("invoice", "arithmetic", "classification"):
            calibration, evaluation = [], []
            for row in profile["rows"]:
                if row["kind"] != kind:
                    continue
                key = (row["seed"], row["step_id"])
                obs = (source_key(tasks[key]), strict_equal(row["output"], truths[key]))
                (calibration if row["seed"] in CALIBRATION_SEEDS else evaluation).append(obs)
            calibration_keys = {r[0] for r in calibration}
            unseen = [r for r in evaluation if r[0] not in calibration_keys]
            gates.append({"provider": tier, "kind": kind, **screen(calibration),
                          "evaluation_observations": len(evaluation),
                          "evaluation_correct": sum(r[1] for r in evaluation),
                          "evaluation_unseen_sources": len({r[0] for r in unseen}),
                          "evaluation_unseen_correct": sum(r[1] for r in unseen),
                          "deployment_scope": "generated-source-fixtures-only"})
    # New seeds for deterministic coverage. Public inputs enter the planner;
    # private answers are read afterward, only to score the result.
    baseline = []
    for seed in range(101, 106):
        generated, truth = generate(seed, 200)
        for task in generated:
            started = time.perf_counter_ns()
            decision = plan(task)
            elapsed = (time.perf_counter_ns() - started) / 1e6
            baseline.append({"seed": seed, "step_id": task.id, "kind": task.kind,
                             "decision": decision["decision"], "latency_ms": round(elapsed, 6),
                             "true_correct": strict_equal(decision["output"], truth[task.id])})
    cases_path = ROOT / "bench/planning_cases.json"
    challenges = []
    for case in json.loads(cases_path.read_text(encoding="utf-8")):
        task = Task(**{k: case[k] for k in ("id", "kind", "source")})
        result = plan(task)
        correct = strict_equal(result["output"], case["expected"])
        challenges.append({"task": task.public(), **result,
                           "expected_decision": "REVIEW_REQUIRED" if case["expected"] is None else "LOCAL_TOOL",
                           "case_passed": correct})
    timings = sorted(r["latency_ms"] for r in baseline)
    source_hashes = {f"touchstone/{name}": digest(ROOT / "touchstone" / name) for name in EVIDENCE_SOURCES}
    source_hashes["bench/planning_cases.json"] = digest(cases_path)
    inputs = {f"local-{tier}.json": digest(directory / f"local-{tier}.json") for tier in profiles}
    return {
        "mode": "OFFLINE_PROCUREMENT_EVIDENCE", "payments_sent": 0,
        "tool_version": TOOL_VERSION, "source_sha256": source_hashes, "profile_sha256": inputs,
        "required_success_rate": .95, "calibration_seeds": list(CALIBRATION_SEEDS),
        "evaluation_seeds": list(EVALUATION_SEEDS),
        "partition_caveat": "Retrospective split of previously inspected profiles, not a pristine prospective holdout. Exact repeated sources are collapsed; template correlation remains. Evaluation rows do not enter the screen.",
        "quality_caveat": "Wilson lower bounds are screening diagnostics on narrow fixtures, not deployment accuracy guarantees. Task.min_quality is a response-check score, separate from the 95% provider success target.",
        "provider_identity": {tier: {"model_sha256": p["environment"]["model_sha256"],
                                      "runtime_archive_sha256": p["environment"]["runtime_archive_sha256"],
                                      "decoding": p["decoding"]} for tier, p in profiles.items()},
        "provider_gates": gates, "live_purchase_authorized": False,
        "baseline": {"seeds": list(range(101, 106)), "steps": len(baseline),
                     "true_correct": sum(r["true_correct"] for r in baseline),
                     "provider_spend_micro_usd": 0, "inference_calls": 0,
                     "cpu_latency_p50_ms": statistics.median(timings),
                     "cpu_latency_p95_ms": timings[int((len(timings)-1)*.95)],
                     "cost_caveat": "No provider purchase. CPU, development, review and service costs are not priced; this is not a zero-total-cost claim.",
                     "rows": baseline},
        "challenge_summary": {"cases": len(challenges), "passed": sum(r["case_passed"] for r in challenges),
                              "resolved": sum(r["decision"] == "LOCAL_TOOL" for r in challenges),
                              "review_required": sum(r["decision"] == "REVIEW_REQUIRED" for r in challenges)},
        "planning_examples": challenges,
    }


def save(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "procurement-evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    baseline, challenges = report["baseline"], report["challenge_summary"]
    lines = ["# Procurement evidence", "", "Offline planning and real local tool execution. No payments sent.", "",
             f"Bounded tools solved {baseline['true_correct']}/{baseline['steps']} generated tasks over five new seeds with no model calls or provider spend. CPU p50 {baseline['cpu_latency_p50_ms']:.4f} ms; p95 {baseline['cpu_latency_p95_ms']:.4f} ms (single local run).",
             "", baseline["cost_caveat"], "",
             f"Authored boundary cases: {challenges['passed']}/{challenges['cases']} expectations met; {challenges['resolved']} resolved and {challenges['review_required']} deliberately deferred for review. Review is not task completion or measured real-world accuracy.", "",
             "| Provider | Task | Unique calibration sources | Consistently correct | Wilson lower bound | Screen |",
             "|---|---|---:|---:|---:|---|"]
    for row in report["provider_gates"]:
        lines.append(f"| {row['provider']} | {row['kind']} | {row['unique_sources']} | {row['consistently_correct_sources']} | {row['wilson_95_lower']:.1%} | {row['status']} |")
    lines += ["", "Screen target: 95% success and at least 20 unique calibration sources, separately for each task kind. No model has live purchase authorization.",
              "", report["partition_caveat"], "", report["quality_caveat"], "",
              "The classifier profile repeats only three distinct messages. Its 30 measurements per model do not represent 30 unique customer scenarios. Evaluation seed 43 has no unseen classification sources.", "",
              "The simulator dashboard retains its original financial stress scenario. The planning preview and CLI execute bounded tools separately, with explicit review on unsupported input. Neither the statistical screen nor this report enables a paid adapter.", "",
              "Next experiment: define representative de-identified finance-ops inputs and independent expected outcomes; freeze prompts/tools, collect a new prospective calibration/evaluation split, and measure a model only where deterministic tools abstain. Connect payment only after measured eligibility and funded recovery proof.", "",
              "Wilson formula reference: [NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).", ""]
    (directory / "PROCUREMENT_RESULTS.md").write_text("\n".join(lines), encoding="utf-8")


def summary(directory=ROOT / "bench/results"):
    """Only display evidence whose code, cases and input profiles still match."""
    directory = Path(directory)
    try:
        report = json.loads((directory / "procurement-evidence.json").read_text(encoding="utf-8"))
        expected_files = {f"touchstone/{name}" for name in EVIDENCE_SOURCES} | {"bench/planning_cases.json"}
        if set(report["source_sha256"]) != expected_files:
            raise ValueError("Incomplete evidence provenance")
        if set(report["profile_sha256"]) != {"local-economy.json", "local-balanced.json"}:
            raise ValueError("Incomplete profile provenance")
        if any(digest(ROOT / name) != value for name, value in report["source_sha256"].items()):
            raise ValueError("Evidence code or cases changed")
        if any(digest(directory / name) != value for name, value in report["profile_sha256"].items()):
            raise ValueError("Measured profile changed")
        return {"status": "CURRENT", **{k: report[k] for k in (
            "mode", "provider_gates", "challenge_summary", "planning_examples", "live_purchase_authorized")},
                "baseline": {k: v for k, v in report["baseline"].items() if k != "rows"}}
    except FileNotFoundError:
        return {"status": "NOT_RUN", "live_purchase_authorized": False}
    except (KeyError, ValueError, TypeError, OSError):
        return {"status": "STALE_OR_INVALID", "live_purchase_authorized": False}
