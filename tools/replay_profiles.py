"""Compare policies on paired measured outputs; prices are explicit assumptions."""
import json
import hashlib
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.verifier import check, VERIFY_COST, VERIFIER_VERSION
from touchstone.workload import generate


def main():
    profiles = {tier: json.loads((ROOT / "bench/results" / f"local-{tier}.json").read_text()) for tier in ("economy", "balanced")}
    if len({p.get("decoding") for p in profiles.values()}) != 1:
        raise ValueError("Cannot compare profiles made with different decoding configurations")
    sources_hash = {name: hashlib.sha256((ROOT / "touchstone" / name).read_bytes()).hexdigest()
                   for name in ("providers.py", "verifier.py", "workload.py")}
    if any(p.get("source_sha256") != sources_hash for p in profiles.values()):
        raise ValueError("Profile source hashes differ from the current workload, verifier or inference client; regenerate or explicitly version the experiment")
    indexed = {tier: {(r["seed"], r["step_id"]): r for r in p["rows"]} for tier, p in profiles.items()}
    if set(indexed["economy"]) != set(indexed["balanced"]):
        raise ValueError("Profiles must contain exactly the same seeds and tasks")
    cases = sorted(indexed["economy"])
    # Assumed procurement prices, not measured electricity costs or actual payments.
    prices = {"economy": 10000, "balanced": 20000}
    sources, truths = {}, {}
    for seed in sorted({k[0] for k in cases}):
        count = profiles["economy"]["steps_per_seed"]
        tasks, truth = generate(seed, count)
        sources[seed], truths[seed] = {t.id: t for t in tasks}, truth
    rows = []
    for policy in ("always-economy", "always-balanced", "verify-then-escalate"):
        for seed, step_id in cases:
            task = sources[seed][step_id]
            tiers = ["balanced"] if policy == "always-balanced" else ["economy", "balanced"] if policy == "verify-then-escalate" else ["economy"]
            cost, latency, calls, accepted = 0, 0, [], None
            for tier in tiers:
                measured = indexed[tier][(seed, step_id)]
                cost += prices[tier] + VERIFY_COST
                latency += measured["latency_ms"]
                calls.append(tier)
                verdict = check(task, measured["output"])
                if verdict["passed"]:
                    accepted = measured["output"]
                    break
                if not verdict.get("retryable", True):
                    break
            # Ground truth is used only after decisions to score the accepted result.
            rows.append({"policy": policy, "seed": seed, "step_id": step_id, "calls": calls,
                         "assumed_cost_micro_usd": cost, "replayed_latency_ms": latency,
                         "accepted": accepted is not None, "true_correct": accepted == truths[seed][step_id]})
    summaries = []
    for policy in ("always-economy", "always-balanced", "verify-then-escalate"):
        own = [r for r in rows if r["policy"] == policy]
        correct = sum(r["true_correct"] for r in own)
        cost = sum(r["assumed_cost_micro_usd"] for r in own)
        latency = sorted(r["replayed_latency_ms"] for r in own)
        summaries.append({"policy": policy, "steps": len(own), "true_success_rate": correct / len(own),
                          "assumed_cost_micro_usd": cost, "assumed_cost_per_true_correct_micro_usd": cost / correct if correct else None,
                          "replayed_latency_p50_ms": statistics.median(latency), "replayed_latency_p95_ms": latency[int((len(latency)-1)*.95)],
                          "escalations": sum(len(r["calls"]) > 1 for r in own)})
    report = {"mode": "LOCAL_PROFILE_REPLAY", "payments": "NONE", "verifier_version": VERIFIER_VERSION, "source_sha256": sources_hash,
              "method": "Same paired model outputs and seeds. Online source checks choose escalation; private truth scores decisions afterward. Actual call latency is replayed, not newly measured concurrent service latency. Model prices are assumptions.",
              "assumed_price_micro_usd": prices, "checking_charge_micro_usd": VERIFY_COST,
              "gpu_offload_confirmed": all(p["gpu_offload_confirmed"] for p in profiles.values()),
              "seeds": sorted(sources), "summary": summaries, "rows": rows}
    target = ROOT / "bench/results"
    (target / "local-replay.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    text = ["# Paired local model profile replay", "", "Actual model outputs and call timings; assumed procurement prices; no financial payments.", "",
            "| Policy | True success | Assumed USD total | Assumed USD / true-correct | Replayed p95 ms | Escalations |",
            "|---|---:|---:|---:|---:|---:|"]
    for r in summaries:
        unit = f"{r['assumed_cost_per_true_correct_micro_usd']/1e6:.4f}" if r["assumed_cost_per_true_correct_micro_usd"] is not None else "undefined"
        text.append(f"| {r['policy']} | {r['true_success_rate']:.1%} | {r['assumed_cost_micro_usd']/1e6:.3f} | {unit} | {r['replayed_latency_p95_ms']} | {r['escalations']} |")
    text += ["", report["method"], "", "This is a narrow synthetic-source experiment, not a general invoice/OCR benchmark or a funded x402 run. Raw profiles retain model hashes, runtime version, GPU telemetry, outputs and per-call latency.", ""]
    (target / "LOCAL_RESULTS.md").write_text("\n".join(text), encoding="utf-8")
    print(json.dumps({"mode": report["mode"], "summary": summaries}, indent=2))


if __name__ == "__main__":
    main()
