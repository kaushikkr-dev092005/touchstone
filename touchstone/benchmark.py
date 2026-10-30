"""Paired, seeded simulator evaluation. Never presented as measured LLM performance."""
import json
from pathlib import Path
import statistics
import tempfile
from .engine import Engine
from .ledger import Ledger
from .payments import MockRail
from .workload import generate, score_truth
from .verifier import VERIFIER_VERSION

POLICIES = ["always-premium", "always-cheapest", "touchstone"]


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * p))] if values else 0


def evaluate(seed, count, policy, directory):
    tasks, truth = generate(seed, count)
    ledger = Ledger(Path(directory) / "ledger.sqlite")
    rail = MockRail(Path(directory) / "rail.sqlite")
    engine = Engine(ledger, rail)
    run_id = ledger.create_run([{"seed": seed, "policy": policy, "hold": count * 200000,
                                 "price_cap": 250000, "allocation": count * 200000,
                                 "tasks": [t.public() for t in tasks]}], count * 200000)
    snapshot = engine.run(run_id)
    job = snapshot["jobs"][0]
    attempts = ledger.attempts(job["id"])
    accepted = {a["step_id"]: json.loads(a["output"]) for a in attempts if a["passed"] == 1}
    correct = score_truth(tasks, truth, accepted)
    latencies = []
    for task in tasks:
        # Estimated service latency of all paid attempts, not benchmark wall-clock time.
        latencies.append(sum(json.loads(a["quote"])["latency_ms"] for a in attempts if a["step_id"] == task.id))
    calibration = [abs(a["score"] - float(json.loads(a["output"]) == truth[a["step_id"]])) for a in attempts if a["score"] is not None]
    detected = [int(a["step_id"].split("-")[1]) - 50 for a in attempts if a["provider"] == "balanced" and a["passed"] == 0 and int(a["step_id"].split("-")[1]) >= 50]
    reconciliation = snapshot["reconciliation"]
    receipt_keys = [r["key"] for r in rail.receipts()]
    return {"seed": seed, "policy": policy, "steps": count, "accepted": len(accepted), "true_correct": correct,
            "true_success_rate": correct / count, "total_cost_micro_usd": job["spent"],
            "cost_per_true_correct_micro_usd": job["spent"] / correct if correct else None,
            "estimated_latency_p50_ms": percentile(latencies, .50), "estimated_latency_p95_ms": percentile(latencies, .95),
            "retries": sum(max(0, sum(a["step_id"] == t.id for a in attempts) - 1) for t in tasks),
            "attempted_steps": len({a["step_id"] for a in attempts}),
            "verifier_calibration_mae": statistics.mean(calibration) if calibration else None,
            "quality_drop_detection_delay_steps": min(detected) if detected else None,
            "budget_breaches": int(job["spent"] > job["hold"]),
            "price_cap_breaches": sum(a["price"] > job["price_cap"] for a in attempts),
            "duplicate_payments": len(receipt_keys) - len(set(receipt_keys)),
            "reconciled": reconciliation["matched"], "status": job["status"]}


def run_benchmark(count=200, seeds=(41, 42, 43, 44, 45), output="bench/results", progress=None):
    rows = []
    with tempfile.TemporaryDirectory(prefix="touchstone-bench-") as temp:
        for seed in seeds:
            for policy in POLICIES:
                rows.append(evaluate(seed, count, policy, Path(temp) / f"{seed}-{policy}"))
                if progress:
                    progress(seed, policy)
    metrics = ["total_cost_micro_usd", "cost_per_true_correct_micro_usd", "true_success_rate", "estimated_latency_p50_ms", "estimated_latency_p95_ms", "retries", "verifier_calibration_mae"]
    summary = [{"policy": p, **{m: statistics.median([r[m] for r in rows if r["policy"] == p and r[m] is not None]) for m in metrics}} for p in POLICIES]
    report = {"mode": "SIMULATED", "verifier_version": VERIFIER_VERSION, "method": "Paired seeds; identical tasks, chaos indices and verifier across policies. All attempts and checking charges included. Latencies are simulator estimates. No GPU or live payments used.",
              "seeds": list(seeds), "steps_per_seed": count, "summary": summary, "runs": rows,
              "gates": {"zero_budget_breaches": all(r["budget_breaches"] == 0 for r in rows),
                        "zero_price_cap_breaches": all(r["price_cap_breaches"] == 0 for r in rows),
                        "zero_duplicate_mock_payments": all(r["duplicate_payments"] == 0 for r in rows),
                        "all_reconciled": all(r["reconciled"] for r in rows),
                        "all_workloads_finished": all(r["status"] == "COMPLETED" and r["attempted_steps"] == count for r in rows)}}
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    (target / "simulated.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Simulator benchmark", "", "Synthetic provider quality and estimated latency; these are not GPU/model or live-payment measurements.", "", f"Median across seeds {list(seeds)}, {count} tasks per seed. Costs include failed calls and verification.", "", "| Policy | Cost USD | True success | USD / true-correct step | Estimated p95 ms | Retries | Calibration MAE |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in summary:
        lines.append(f"| {r['policy']} | {r['total_cost_micro_usd']/1e6:.3f} | {r['true_success_rate']:.1%} | {r['cost_per_true_correct_micro_usd']/1e6:.4f} | {r['estimated_latency_p95_ms']} | {r['retries']} | {r['verifier_calibration_mae']:.3f} |")
    lines += ["", f"Verifier: `{VERIFIER_VERSION}`. Classification uses bounded source-evidence rules; unknown or ambiguous sources require review. These synthetic templates are within its supported scope. This does not establish semantic accuracy on arbitrary customer text.", "", "The original membership-only baseline is retained in baseline-v1/. No cost or quality target was tuned to force a winning result.", "", "Regenerate: `python -m touchstone benchmark`.", ""]
    (target / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    return report
