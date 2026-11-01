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
from .invoice_consistency import check_invoice_consistency, make_invoice_consistency_case, noisy_invoice_check

POLICIES = ["always-premium", "always-cheapest", "touchstone"]


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * p))] if values else 0


def evaluate_noisy_invoice_checker(case_count=20, repetitions=100):
    sample_sizes = (1, 2, 3, 5)
    false_accepts = {sample_size: 0 for sample_size in sample_sizes}
    exact_false_accepts = 0
    clean_accepts = {sample_size: 0 for sample_size in sample_sizes}
    trials = case_count * repetitions
    for case_index in range(case_count):
        task, correct = make_invoice_consistency_case(seed=7000 + case_index, line_count=10)
        incorrect = json.loads(json.dumps(correct))
        incorrect["line_items"][0]["line_total_cents"] += 1
        incorrect["line_items"][1]["line_total_cents"] -= 1
        exact_false_accepts += int(check_invoice_consistency(task, incorrect)["passed"])
        for repetition in range(repetitions):
            seed = case_index * repetitions + repetition
            for sample_size in sample_sizes:
                false_accepts[sample_size] += int(noisy_invoice_check(task, incorrect, seed, sample_size)["passed"])
                clean_accepts[sample_size] += int(noisy_invoice_check(task, correct, seed, sample_size)["passed"])
    return {
        "task": "10-line synthetic invoices with two offsetting one-cent line-total errors",
        "cases": case_count,
        "repetitions_per_case": repetitions,
        "trials_per_sample_size": trials,
        "exact_checker_false_accepts": exact_false_accepts,
        "exact_checker_false_accept_rate": exact_false_accepts / case_count,
        "noisy_checker": [
            {"sampled_rows": sample_size,
             "false_accepts": false_accepts[sample_size],
             "false_accept_rate": false_accepts[sample_size] / trials,
             "clean_accept_rate": clean_accepts[sample_size] / trials}
            for sample_size in sample_sizes
        ],
        "note": "Synthetic fault-injection estimate, not a production population rate or confidence interval.",
    }


def write_noisy_verification_chart(report, path):
    width, height = 720, 400
    left, right, top, bottom = 88, 660, 54, 310
    rows = report["noisy_checker"]
    exact_label = (f"Exact checker: {report['exact_checker_false_accepts']}/"
                   f"{report['cases']} injected cases")
    x_positions = {row["sampled_rows"]: left + index * (right - left) / max(1, len(rows) - 1)
                   for index, row in enumerate(rows)}
    y_position = lambda rate: bottom - rate * (bottom - top)
    plotted = " ".join(f"{x_positions[row['sampled_rows']]:.1f},{y_position(row['false_accept_rate']):.1f}"
                       for row in rows)
    elements = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="#fff"/>',
                '<text x="88" y="28" font-family="sans-serif" font-size="18" font-weight="bold">Synthetic invoice fault-injection false-accept rate</text>']
    for percent in (0, 25, 50, 75, 100):
        y = y_position(percent / 100)
        elements.extend([f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#d6d6d6"/>',
                         f'<text x="{left - 12}" y="{y + 5:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{percent}%</text>'])
    elements.extend([f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#333"/>',
                     f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#333"/>',
                     f'<polyline points="{plotted}" fill="none" stroke="#c2410c" stroke-width="3"/>'])
    for row in rows:
        x, y = x_positions[row["sampled_rows"]], y_position(row["false_accept_rate"])
        elements.extend([f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#c2410c"/>',
                         f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12">{row["false_accept_rate"]:.1%}</text>',
                         f'<text x="{x:.1f}" y="{bottom + 22}" text-anchor="middle" font-family="sans-serif" font-size="12">{row["sampled_rows"]}</text>'])
    elements.extend([f'<line x1="{left}" y1="{bottom:.1f}" x2="{right}" y2="{bottom:.1f}" stroke="#2563eb" stroke-width="2" stroke-dasharray="7 5"/>',
                     f'<text x="{(left + right) / 2:.1f}" y="{height - 36}" text-anchor="middle" font-family="sans-serif" font-size="13">Line items sampled per invoice</text>',
                     f'<line x1="{left}" y1="{height - 14}" x2="{left + 28}" y2="{height - 14}" stroke="#c2410c" stroke-width="3"/>',
                     f'<text x="{left + 36}" y="{height - 10}" font-family="sans-serif" font-size="12">Noisy checker</text>',
                     f'<line x1="{left + 185}" y1="{height - 14}" x2="{left + 213}" y2="{height - 14}" stroke="#2563eb" stroke-width="2" stroke-dasharray="7 5"/>',
                     f'<text x="{left + 221}" y="{height - 10}" font-family="sans-serif" font-size="12">{exact_label}</text>',
                     '<text x="88" y="388" font-family="sans-serif" font-size="11" fill="#555">20 synthetic 10-line invoices; two offsetting 1-cent errors; 100 seeded checks per case.</text>',
                     '</svg>'])
    Path(path).write_text("\n".join(elements) + "\n", encoding="utf-8")


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
    detected = [int(a["step_id"].split("-")[1]) - 50 for a in attempts if a["provider"] == "balanced" and a["passed"] == 0 and int(a["step_id"].split("-")[1]) >= 50]
    reconciliation = snapshot["reconciliation"]
    receipt_keys = [r["key"] for r in rail.receipts()]
    return {"seed": seed, "policy": policy, "steps": count, "accepted": len(accepted), "true_correct": correct,
            "true_success_rate": correct / count, "total_cost_micro_usd": job["spent"],
            "cost_per_true_correct_micro_usd": job["spent"] / correct if correct else None,
            "estimated_latency_p50_ms": percentile(latencies, .50), "estimated_latency_p95_ms": percentile(latencies, .95),
            "retries": sum(max(0, sum(a["step_id"] == t.id for a in attempts) - 1) for t in tasks),
            "attempted_steps": len({a["step_id"] for a in attempts}),
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
    metrics = ["total_cost_micro_usd", "cost_per_true_correct_micro_usd", "true_success_rate", "estimated_latency_p50_ms", "estimated_latency_p95_ms", "retries"]
    summary = [{"policy": p, **{m: statistics.median([r[m] for r in rows if r["policy"] == p and r[m] is not None]) for m in metrics}} for p in POLICIES]
    noisy_verification = evaluate_noisy_invoice_checker()
    report = {"mode": "SIMULATED", "verifier_version": VERIFIER_VERSION, "method": "Paired seeds; identical tasks, chaos indices and verifier across policies. All attempts and checking charges included. Latencies are simulator estimates. No GPU or live payments used.",
              "seeds": list(seeds), "steps_per_seed": count, "summary": summary, "runs": rows,
              "noisy_invoice_verification": noisy_verification,
              "gates": {"zero_budget_breaches": all(r["budget_breaches"] == 0 for r in rows),
                        "zero_price_cap_breaches": all(r["price_cap_breaches"] == 0 for r in rows),
                        "zero_duplicate_mock_payments": all(r["duplicate_payments"] == 0 for r in rows),
                        "all_reconciled": all(r["reconciled"] for r in rows),
                        "all_workloads_finished": all(r["status"] == "COMPLETED" and r["attempted_steps"] == count for r in rows)}}
    target = Path(output)
    target.mkdir(parents=True, exist_ok=True)
    (target / "simulated.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_noisy_verification_chart(noisy_verification, target / "noisy-verification.svg")
    lines = ["# Simulator benchmark", "", "Synthetic provider quality and estimated latency; these are not GPU/model or live-payment measurements.", "", f"Median across seeds {list(seeds)}, {count} tasks per seed. Costs include failed calls and verification.", "", "| Policy | Cost USD | True success | USD / true-correct step | Estimated p95 ms | Retries |", "|---|---:|---:|---:|---:|---:|"]
    for r in summary:
        lines.append(f"| {r['policy']} | {r['total_cost_micro_usd']/1e6:.3f} | {r['true_success_rate']:.1%} | {r['cost_per_true_correct_micro_usd']/1e6:.4f} | {r['estimated_latency_p95_ms']} | {r['retries']} |")
    lines += ["", "## Invoice verification fault injection", "", "The exact checker independently recomputes cited quantity × unit price, line extensions and invoice total. The deliberately noisy checker samples line arithmetic but checks the aggregate. We injected two offsetting one-cent line-total errors into 20 ten-line invoices and repeated seeded sampling 100 times per case.", "", "| Rows sampled | False accepts / 2,000 | False-accept rate | Clean accept rate |", "|---:|---:|---:|---:|"]
    lines += ["", "![Synthetic invoice false-accept rate by rows sampled](noisy-verification.svg)", ""]
    for row in noisy_verification["noisy_checker"]:
        lines.append(f"| {row['sampled_rows']} | {row['false_accepts']} | {row['false_accept_rate']:.1%} | {row['clean_accept_rate']:.1%} |")
    lines += ["", f"Exact checker's false-accept rate on this injected set: {noisy_verification['exact_checker_false_accept_rate']:.1%}. The noisy rates are synthetic fault-injection results, not population estimates or production payment gates; noisy verification is never used to authorize a live payment.", "", f"Verifier: `{VERIFIER_VERSION}`. Bounded source-evidence rules check cited invoice arithmetic; unknown or ambiguous sources require review. The other synthetic templates are within their supported scope. None of these results establish semantic accuracy on arbitrary customer text.", "", "The original membership-only baseline is retained in baseline-v1/. Its tautological calibration metric is historical and has been removed from current results. No cost or quality target was tuned to force a winning result.", "", "Regenerate: `python -m touchstone benchmark`.", ""]
    (target / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    return report
