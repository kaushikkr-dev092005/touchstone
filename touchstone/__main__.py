import argparse
import json
from pathlib import Path
import platform
import sqlite3
import sys


def main():
    parser = argparse.ArgumentParser(description="Touchstone inference procurement prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Show local integration readiness without revealing credentials")
    commands.add_parser("rpc-smoke", help="Read Metal chain ID and current block; no transactions")
    commands.add_parser("metal-funding", help="Read testnet wallet gas and USDZ balances; no transactions")
    commands.add_parser("banked-status", help="Read integrated sandbox/testnet job journal")
    commands.add_parser("banked-halt", help="Stop new integrated testnet purchases; allow recovery")
    commands.add_parser("banked-resume", help="Release the integrated purchase halt without changing limits")
    banked = commands.add_parser("banked-job", help="Run one recoverable Airwallex sandbox/Metal testnet integration probe")
    banked.add_argument("--scope", required=True)
    banked.add_argument("--provider-origin", default="http://127.0.0.1:8092")
    banked.add_argument("--task-file", help="Public task JSON; defaults to a simple protocol-probe calculation")
    banked.add_argument("--hold-usd", default="1.00")
    banked.add_argument("--allocation-usd", default="0.10")
    banked.add_argument("--price-cap-usd", default="0.05")
    banked.add_argument("--recover", action="store_true")
    banked.add_argument("--integration-probe", action="store_true", help="Explicitly test payments; does not claim model eligibility")
    evidence = commands.add_parser("procurement-evidence", help="Screen measured profiles and evaluate bounded tools; no payments")
    evidence.add_argument("--profiles", default="bench/results")
    evidence.add_argument("--output", default="bench/results")
    planning = commands.add_parser("plan", help="Resolve supported sources with local tools or defer for review; no payments")
    planning.add_argument("--input", help="JSON task or list of tasks; defaults to authored boundary cases")
    planning.add_argument("--output", default="data/local-plan.json")
    web = commands.add_parser("serve", help="Loopback dashboard; all services simulated")
    web.add_argument("--port", type=int, default=8088)
    web.add_argument("--data-dir", default="data")
    demo = commands.add_parser("demo", help="Run the three-job short-float scenario")
    demo.add_argument("--data-dir", default="data")
    demo.add_argument("--seed", type=int, default=42)
    bench = commands.add_parser("benchmark", help="Three paired policies, five seeds, simulator only")
    bench.add_argument("--steps", type=int, default=200)
    bench.add_argument("--output", default="bench/results")
    commands.add_parser("airwallex-smoke", help="Authenticate and read sandbox balances/accounts; no writes")
    holds = commands.add_parser("airwallex-hold", help="Execute a sandbox-only test-card hold/capture with durable recovery")
    holds.add_argument("--scope", required=True, help="Stable unique order ID; reuse after interruption")
    holds.add_argument("--hold-usd", default="1.00")
    holds.add_argument("--capture-usd", default="0.50")
    holds.add_argument("--recover", action="store_true")
    holds.add_argument("--journal", default="data/airwallex-operations.sqlite")
    profile = commands.add_parser("profile-local", help="Measure an already-running local model; no payment")
    profile.add_argument("--steps", type=int, default=12)
    profile.add_argument("--output", default="bench/results/local-profile.json")
    args = parser.parse_args()
    try:
        from .config import load_local
        load_local()
        if args.command == "doctor":
            from .readiness import inspect
            print(json.dumps(inspect(), indent=2))
        elif args.command == "rpc-smoke":
            from .rpc import inspect_rpc
            import hashlib, os, time
            from .config import ROOT
            result = inspect_rpc()
            target = ROOT / 'data/rpc-readiness.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({**result, "observed_at": time.time(),
                "endpoint_fingerprint": hashlib.sha256(os.environ['METAL_RPC_URL'].encode()).hexdigest()}), encoding='utf-8')
            print(json.dumps(result, indent=2))
        elif args.command == "metal-funding":
            from .metal import MetalRail
            from .config import ROOT
            result = MetalRail('funding-readiness', 'http://127.0.0.1:8092').invoke('funding-status')
            (ROOT / 'data/metal-funding-readiness.json').write_text(json.dumps(result), encoding='utf-8')
            print(json.dumps(result, indent=2))
        elif args.command in {'banked-status', 'banked-halt', 'banked-resume', 'banked-job'}:
            from .banked import BankedStore, BankedWorkflow
            from .config import ROOT
            store = BankedStore(ROOT / 'data/banked/ledger.sqlite', ROOT / 'data/metal/funding-owner.sqlite')
            if args.command == 'banked-status':
                print(json.dumps({"mode": "SANDBOX_TESTNET", "jobs": store.jobs(), "audit": store.ledger.audit()}, indent=2))
            elif args.command in {'banked-halt', 'banked-resume'}:
                store.ledger.halt() if args.command == 'banked-halt' else store.ledger.resume()
                print(json.dumps({"halted": args.command == 'banked-halt', "limits_changed": False}))
            else:
                from .treasury import AirwallexSandbox
                from .holds import SandboxHoldWorkflow, OperationJournal, micro_usd
                from .metal import MetalRail
                from .workload import Task
                if not args.integration_probe:
                    raise ValueError("Pass --integration-probe to test the payment protocol; autonomous model buying is not approved")
                task = Task(**json.loads(Path(args.task_file).read_text(encoding='utf-8'))) if args.task_file else Task(
                    'protocol-probe', 'arithmetic', {"amounts_cents": [1250,275,499], "discount_cents": 24})
                treasury = SandboxHoldWorkflow(AirwallexSandbox(), OperationJournal(ROOT / 'data/banked/airwallex.sqlite'))
                workflow = BankedWorkflow(store, treasury, lambda scope, url, cap, budget: MetalRail(scope, url, cap, budget))
                result = workflow.run(args.scope, task, args.provider_origin, micro_usd(args.hold_usd),
                    micro_usd(args.allocation_usd), micro_usd(args.price_cap_usd), args.recover, args.integration_probe)
                print(json.dumps(result, indent=2))
                return 0 if result['phase'] == 'COMPLETED' else 2
        elif args.command == "procurement-evidence":
            from .procurement_evidence import build, save
            report = build(args.profiles)
            save(report, args.output)
            print(json.dumps({"mode": report["mode"], "provider_gates": report["provider_gates"],
                              "baseline": {k: v for k, v in report["baseline"].items() if k != "rows"},
                              "challenge_summary": report["challenge_summary"], "payments_sent": 0}, indent=2))
        elif args.command == "plan":
            from .local_tools import plan
            from .workload import Task
            if args.input:
                raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
                raw = raw if isinstance(raw, list) else [raw]
            else:
                cases = json.loads((Path(__file__).resolve().parent.parent / "bench/planning_cases.json").read_text(encoding="utf-8"))
                raw = [{k: r[k] for k in ("id", "kind", "source")} for r in cases]
            if not raw or len(raw) > 2000 or any(not isinstance(r, dict) or not {"id", "kind", "source"} <= set(r)
                                               or set(r) - {"id", "kind", "source", "min_quality"} for r in raw):
                raise ValueError("Supply 1 to 2000 public tasks with id, kind, source and optional min_quality")
            decisions = [plan(Task(**r)) for r in raw]
            report = {"mode": "LOCAL_PREFLIGHT", "payments_sent": 0, "decisions": decisions}
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"mode": report["mode"], "tasks": len(decisions),
                              "resolved": sum(r["decision"] == "LOCAL_TOOL" for r in decisions),
                              "review_required": sum(r["decision"] == "REVIEW_REQUIRED" for r in decisions),
                              "payments_sent": 0, "output": str(target)}, indent=2))
        elif args.command == "serve":
            from .server import serve
            if not 1024 <= args.port <= 65535:
                parser.error("Use a port from 1024 to 65535")
            serve(args.port, args.data_dir)
        elif args.command == "demo":
            from .engine import Engine
            from .ledger import Ledger
            from .payments import MockRail
            engine = Engine(Ledger(Path(args.data_dir) / "ledger.sqlite"), MockRail(Path(args.data_dir) / "rail.sqlite"))
            print(json.dumps(engine.run(engine.create_demo(args.seed)), indent=2))
        elif args.command == "benchmark":
            from .benchmark import run_benchmark
            if not 1 <= args.steps <= 2000:
                parser.error("Use 1 to 2000 steps")
            report = run_benchmark(args.steps, output=args.output,
                                   progress=lambda seed, policy: print(f"Finished seed {seed}: {policy}", flush=True))
            print(json.dumps({"summary": report["summary"], "gates": report["gates"]}, indent=2))
        elif args.command == "airwallex-smoke":
            from .treasury import AirwallexSandbox
            from .config import ROOT
            result = AirwallexSandbox().smoke()
            (ROOT / 'data/airwallex-readiness.json').write_text(json.dumps(result), encoding='utf-8')
            (ROOT / 'bench/results/airwallex-readiness.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
            print(json.dumps(result, indent=2))
            return 0 if result['balance_read'] and result['global_accounts_read'] else 2
        elif args.command == "airwallex-hold":
            from .treasury import AirwallexSandbox
            from .holds import OperationJournal, SandboxHoldWorkflow, micro_usd
            workflow = SandboxHoldWorkflow(AirwallexSandbox(), OperationJournal(args.journal))
            result = workflow.run(args.scope, micro_usd(args.hold_usd), micro_usd(args.capture_usd), args.recover)
            print(json.dumps(result, indent=2))
            return 0 if result["complete"] else 2
        elif args.command == "profile-local":
            from .providers import local_inference
            from .verifier import check
            from .workload import generate
            import os
            import statistics
            if not 1 <= args.steps <= 200:
                parser.error("Use 1 to 200 profiling steps")
            tasks, truth = generate(42, args.steps)
            local_inference(tasks[0])  # warm-up excluded
            rows = []
            for task in tasks:
                output, latency = local_inference(task)
                rows.append({"step_id": task.id, "kind": task.kind, "latency_ms": latency,
                             "verifier_passed": check(task, output)["passed"], "true_correct": output == truth[task.id]})
            report = {"mode": "LOCAL_MEASURED", "payments": "NONE", "warmups_discarded": 1,
                      "hardware": "Record GPU, VRAM, driver, clocks, temperature and GGUF hash separately",
                      "model": os.environ.get("LOCAL_MODEL", "local-model"), "python": platform.python_version(),
                      "sqlite": sqlite3.sqlite_version, "true_success_rate": sum(r["true_correct"] for r in rows) / len(rows),
                      "median_latency_ms": statistics.median(r["latency_ms"] for r in rows), "rows": rows}
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Touchstone: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
