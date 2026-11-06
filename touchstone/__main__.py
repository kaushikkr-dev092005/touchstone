import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import platform
import sqlite3
import sys
import time


def main():
    parser = argparse.ArgumentParser(description="Touchstone inference procurement prototype")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Show local integration readiness without revealing credentials")
    comparison = commands.add_parser('compare', help='M4 matched four-policy comparison with explicit aggregate caps')
    comparison.add_argument('comparison_args', nargs=argparse.REMAINDER)
    aw_doctor = commands.add_parser("airwallex-doctor", help="Environment-only account/scope check; no private files")
    aw_doctor.add_argument("--probe-reads", action="store_true", help="Authenticate and probe balances/history/conversion reads only")
    aw_doctor.add_argument("--output", help="Save redacted readiness JSON")
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
    banked.add_argument("--execute", action="store_true", help="Allow sandbox/testnet money movement within the stated limits")
    banked.add_argument("--treasury-request-id", help="Require reconciled FX funding for this job scope; Metal funds stay separate")
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
    demo.add_argument('--failed-call-policy', choices=['CUSTOMER_PAYS','MERCHANT_ABSORBS'], default='CUSTOMER_PAYS')
    metal_engine = commands.add_parser("engine-metal", help="Run the engine with its explicit real Metal testnet provider tier")
    metal_engine.add_argument("--scope", required=True, help="Stable testnet wallet/job scope; reuse after interruption")
    metal_engine.add_argument("--steps", type=int, default=30)
    metal_engine.add_argument("--seed", type=int, default=42)
    metal_engine.add_argument("--budget-usd", required=True, help="Hard total job cap, including verification charges")
    metal_engine.add_argument("--price-cap-usd", required=True, help="Maximum Metal provider quote per step")
    metal_engine.add_argument("--provider-url", action="append", help="Approved provider origin; repeat for local and hosted tiers")
    metal_engine.add_argument("--policy", choices=["metal-probe", "real-cheapest", "real-premium", "real-touchstone"],
                              default="metal-probe", help="Live-provider policy; real policies never use simulator quotes")
    metal_engine.add_argument("--task-file", help="JSON list of public tasks; otherwise generated test tasks are used")
    metal_engine.add_argument("--execute", action="store_true", help="Explicitly authorize real testnet calls within the supplied cap")
    metal_engine.add_argument("--recover", action="store_true", help="Recover only; do not dispatch new tasks")
    metal_engine.add_argument("--quote-only", action="store_true", help="Fetch one live provider quote and send no payment")
    metal_engine.add_argument("--crash-at", choices=["after_reserve", "after_rail", "after_paid"],
                               help="Test a recovery boundary; after_rail performs a real paid request")
    metal_engine.add_argument("--kill-at", choices=["after_reserve", "after_rail", "after_paid"],
                               help="Abruptly terminate this process at a recovery boundary; after_rail spends testnet funds")
    metal_engine.add_argument('--output', help='Save redacted engine evidence for every policy')
    batch = commands.add_parser('metal-batch', help='Serially fund distinct wallets, then run concurrent integration probes')
    batch.add_argument('action', choices=['prepare', 'fund', 'run', 'recover', 'report'])
    batch.add_argument('--scope', required=True)
    batch.add_argument('--integration-probe', action='store_true')
    batch.add_argument('--execute', action='store_true')
    batch.add_argument('--recover', action='store_true', help='With run: reconcile only, without purchasing another task')
    batch.add_argument('--provider-origin', default='http://127.0.0.1:8092')
    batch.add_argument('--jobs', type=int, default=3)
    batch.add_argument('--steps', type=int, default=2)
    batch.add_argument('--wallet-budget-usd')
    batch.add_argument('--price-cap-usd')
    batch.add_argument('--aggregate-cap-usd')
    batch.add_argument('--state-dir', default='data/metal-batch')
    batch.add_argument('--kill-at', choices=['after_reserve', 'after_rail', 'after_paid'])
    batch.add_argument('--output')
    bench = commands.add_parser("benchmark", help="Three paired policies, five seeds, simulator only")
    bench.add_argument("--steps", type=int, default=200)
    bench.add_argument("--output", default="bench/results")
    commands.add_parser("airwallex-smoke", help="Authenticate and read sandbox balances/accounts; no writes")
    holds = commands.add_parser("airwallex-hold", help="Execute a sandbox-only test-card hold/capture with durable recovery")
    holds.add_argument("--scope", required=True, help="Stable unique order ID; reuse after interruption")
    holds.add_argument("--hold-usd", default="1.00")
    holds.add_argument("--capture-usd", default="0.50")
    holds.add_argument("--recover", action="store_true")
    holds.add_argument("--execute", action="store_true", help="Allow sandbox authorization/capture/cancel, including recovery writes")
    holds.add_argument("--journal", default="data/airwallex-operations.sqlite")
    checkout = commands.add_parser("airwallex-checkout", help="Start or inspect a hosted sandbox card authorization")
    checkout.add_argument("--scope", required=True, help="Stable unique order ID; reuse after interruption")
    checkout.add_argument("--hold-usd", default="1.00")
    checkout.add_argument("--status", action="store_true", help="Retrieve the session and verify an uncaptured authorization")
    checkout.add_argument("--recover", action="store_true", help="Reconcile an uncertain create through read-only session lookup")
    checkout.add_argument("--execute", action="store_true", help="Allow creation of a sandbox checkout session")
    checkout.add_argument("--journal", default="data/airwallex-operations.sqlite")
    retire = commands.add_parser("airwallex-retire", help="Retire a consumed create scope using evidence and read-back; no remote writes")
    retire.add_argument("--scope", required=True)
    retire.add_argument("--replacement-scope", required=True)
    retire.add_argument("--evidence", required=True, help="Redacted retirement attestation JSON")
    retire.add_argument("--journal", default="data/airwallex-operations.sqlite")
    retire.add_argument("--execute", action="store_true", help="Persist a local retirement tombstone")
    fx = commands.add_parser("airwallex-fx", help="Read wallet balances, quote FX, or explicitly create/reconcile a conversion")
    fx_actions = fx.add_subparsers(dest="fx_action", required=True)
    fx_actions.add_parser("balances", help="Read Airwallex wallet balances")
    fx_quote = fx_actions.add_parser("quote", help="Create a non-settling Airwallex FX quote")
    fx_quote.add_argument("--sell-currency", required=True)
    fx_quote.add_argument("--buy-currency", required=True)
    fx_quote.add_argument("--sell-amount", required=True)
    fx_quote.add_argument("--validity", default="MIN_15")
    fx_quote.add_argument("--output", default="data/airwallex-fx-quote.json")
    fx_convert = fx_actions.add_parser("convert", help="Preview or explicitly execute a wallet FX conversion")
    fx_convert.add_argument("--quote", default="data/airwallex-fx-quote.json")
    fx_convert.add_argument("--request-id", required=True)
    fx_convert.add_argument("--execute", action="store_true", help="Explicitly authorize the sandbox wallet conversion")
    fx_convert.add_argument("--max-sell-amount", help="Written approval cap in the sell currency; mandatory with --execute")
    fx_convert.add_argument("--sell-currency", help="Approved sell currency; mandatory with --execute")
    fx_convert.add_argument("--journal", default="data/airwallex-fx.sqlite")
    fx_report = fx_actions.add_parser("report", help="Reconcile a conversion request against wallet balance history")
    fx_report.add_argument("--request-id", required=True)
    fx_report.add_argument("--journal", default="data/airwallex-fx.sqlite")
    treasury_job = commands.add_parser("treasury-job", help="Link FX and separate demo float accounts to a job")
    treasury_actions = treasury_job.add_subparsers(dest="treasury_action", required=True)
    for action in ('prepare', 'run', 'reconcile', 'report'):
        stage = treasury_actions.add_parser(action)
        stage.add_argument('--scope', required=True)
        stage.add_argument('--ledger', default='data/banked/ledger.sqlite')
        stage.add_argument('--fx-journal', default='data/airwallex-fx.sqlite')
        stage.add_argument('--output', help='Save redacted job evidence')
        if action == 'prepare':
            stage.add_argument('--quote', required=True)
            stage.add_argument('--request-id', required=True)
            stage.add_argument('--customer-budget-currency', required=True)
            stage.add_argument('--customer-budget-amount', required=True)
            stage.add_argument('--demo-usdz-per-unit', required=True, help='SIMULATED accounting rate, not a token transfer')
        elif action == 'run':
            stage.add_argument('--execute', action='store_true')
            stage.add_argument('--sell-currency')
            stage.add_argument('--max-sell-amount')
    profile = commands.add_parser("profile-local", help="Measure an already-running local model; no payment")
    profile.add_argument("--steps", type=int, default=12)
    profile.add_argument("--output", default="bench/results/local-profile.json")
    args = parser.parse_args()
    owners = ExitStack()
    try:
        if args.command == 'compare':
            from .comparison import main as comparison_main
            return comparison_main(args.comparison_args)
        if args.command == 'metal-batch':
            if args.recover and args.action != 'run':
                raise ValueError('--recover is valid only with metal-batch run')
            if not args.integration_probe:
                raise ValueError('An explicit --integration-probe purpose is required; no model is qualified')
            if args.action in {'fund', 'run', 'recover'} and not args.execute:
                raise ValueError('Metal batch writes/recovery require --execute and a written testnet cap')
        if args.command == 'engine-metal' and not args.quote_only and not args.execute:
            raise ValueError('Metal execution/recovery requires --execute and a written testnet cap')
        if args.command == "airwallex-doctor":
            from .airwallex_doctor import inspect as inspect_airwallex
            result = inspect_airwallex(args.probe_reads)
            if args.output:
                target = Path(args.output)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, indent=2))
            return 0 if result["read_probe"] == "PASS" else 2
        if (args.command in {'airwallex-hold', 'banked-job'} or
            args.command == 'airwallex-checkout' and not args.status) and not args.execute:
            raise ValueError("Money-moving workflow requires --execute and written chat approval with a stated cap")
        from .config import load_local
        if args.command not in {'metal-batch', 'treasury-job', 'airwallex-retire', 'airwallex-fx', 'airwallex-hold', 'airwallex-checkout'}:
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
                workflow = BankedWorkflow(store, treasury, lambda scope, url, cap, budget: MetalRail(scope, url, cap, budget, execute=args.execute))
                result = workflow.run(args.scope, task, args.provider_origin, micro_usd(args.hold_usd),
                    micro_usd(args.allocation_usd), micro_usd(args.price_cap_usd), args.recover, args.integration_probe,
                    treasury_request_id=args.treasury_request_id)
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
            print(json.dumps(engine.run(engine.create_demo(args.seed, failed_call_policy=args.failed_call_policy)), indent=2))
        elif args.command == 'metal-batch':
            from .metal_batch import MetalBatch
            from .config import ROOT
            from .holds import micro_usd
            workflow = MetalBatch(args.state_dir, funding_lock=ROOT / 'data/metal/funding-owner.sqlite')
            if args.action == 'prepare':
                result = workflow.prepare(args.scope, args.provider_origin, args.jobs, args.steps,
                    micro_usd(args.wallet_budget_usd), micro_usd(args.price_cap_usd), micro_usd(args.aggregate_cap_usd))
            elif args.action == 'fund':
                result = workflow.fund(args.scope, execute=args.execute)
            elif args.action in {'run', 'recover'}:
                result = workflow.run(args.scope, execute=args.execute, recover=args.action == 'recover' or args.recover, kill_at=args.kill_at)
            else:
                result = workflow.report(args.scope)
            if args.output:
                target = Path(args.output)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            print(json.dumps(result, indent=2))
            return 0 if args.action in {'prepare', 'report'} or result.get('funded') and (args.action == 'fund' or result.get('receipts_reconciled')) else 2
        elif args.command == "engine-metal":
            from .config import ROOT
            from .engine import Engine, InjectedCrash
            from .holds import micro_usd
            from .ledger import Ledger
            from .metal import MetalRail
            from .payments import CompositeRail, MetalEngineRail, MockRail
            from .workload import generate, Task
            import re
            if args.quote_only and (args.execute or args.recover):
                raise ValueError("--quote-only cannot be combined with payment execution or recovery")
            if not args.execute and not args.recover and not args.quote_only:
                raise ValueError("No provider payment is sent unless --execute is supplied")
            if not 1 <= args.steps <= 50:
                parser.error("Use 1 to 50 engine tasks; 30-50 is the recommended live test range")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", args.scope):
                raise ValueError("Invalid Metal testnet scope")
            budget, cap = micro_usd(args.budget_usd), micro_usd(args.price_cap_usd)
            if budget <= 0 or cap <= 0 or cap > budget:
                raise ValueError("Require a positive total budget and per-step cap no greater than the budget")
            provider_urls = args.provider_url or [os.environ.get("METAL_PROVIDER_URL")]
            if any(not url for url in provider_urls) or len(set(provider_urls)) != len(provider_urls):
                raise ValueError("Configure distinct provider origins with --provider-url or METAL_PROVIDER_URL")
            if args.policy.startswith("real-") and len(provider_urls) < 2:
                raise ValueError("Real policy comparison requires separate local-GPU and hosted-premium provider origins")
            tasks = ([Task(**item) for item in json.loads(Path(args.task_file).read_text(encoding="utf-8"))]
                     if args.task_file else generate(args.seed, args.steps)[0])
            if not tasks or len(tasks) > args.steps or any(task.kind not in {"invoice", "arithmetic", "classification", "invoice_consistency", "invoice_extraction"} for task in tasks):
                raise ValueError("Supply 1 to --steps supported provider tasks")
            if args.quote_only:
                expected_provider_ids = ["local-gpu", "hosted-premium"] if args.policy.startswith("real-") else None
                live = MetalEngineRail(args.scope, provider_urls, cap, budget,
                                      expected_provider_ids=expected_provider_ids)
                quoted = live.quote_for_task(tasks[0])
                quotes = quoted if isinstance(quoted, list) else [quoted]
                quotes = [quote for quote in quotes if quote is not None]
                if not quotes:
                    reasons = ", ".join(sorted({e["error"] for e in getattr(live, "last_quote_errors", [])}))
                    raise RuntimeError("No live provider quote is available; no purchase was dispatched"
                                       + (f" ({reasons})" if reasons else ""))
                if args.policy.startswith("real-") and {quote.provider for quote in quotes} != {"local-gpu", "hosted-premium"}:
                    raise RuntimeError("Real quote preflight requires both local-gpu and hosted-premium; no payment was dispatched")
                report = {"mode": "LIVE_QUOTE_ONLY", "policy": args.policy, "payments_sent": 0,
                    "task": {"id": tasks[0].id, "kind": tasks[0].kind},
                    "quotes": [{"provider": quote.provider, "price_micro_usd": quote.price,
                                "latency_ms": quote.latency_ms, "queue_depth": quote.queue_depth,
                                "latency_samples": quote.latency_samples,
                                "latency_source": "completed_provider_deliveries" if quote.latency_samples else "default_before_first_delivery",
                                "expires_at": quote.expires_at, "mode": quote.mode} for quote in quotes]}
                if len(quotes) == 1:
                    report["quote"] = report["quotes"][0]
                print(json.dumps(report, indent=2))
                return 0
            from .leases import exclusive
            owners.enter_context(exclusive(ROOT / 'data/metal-engine' / (args.scope + '.owner.sqlite')))
            if args.policy.startswith("real-") and not args.recover:
                preflight = MetalEngineRail(args.scope, provider_urls, cap, budget,
                    expected_provider_ids=["local-gpu", "hosted-premium"]).quote_for_task(tasks[0])
                preflight = preflight if isinstance(preflight, list) else [preflight]
                if {quote.provider for quote in preflight if quote is not None} != {"local-gpu", "hosted-premium"}:
                    raise RuntimeError("Real payment blocked: both local-gpu and hosted-premium quotes must pass a no-payment preflight")
            data_dir = ROOT / "data/metal-engine"
            data_dir.mkdir(parents=True, exist_ok=True)
            scope_file = data_dir / (args.scope + ".json")
            if args.recover and not scope_file.exists():
                raise ValueError("Recovery requires an existing scope; it cannot create or dispatch a job")
            mandate = {"seed": args.seed, "steps": len(tasks), "budget": budget, "cap": cap,
                       "policy": args.policy,
                       "provider_url": provider_urls[0] if len(provider_urls) == 1 else provider_urls,
                       "task_digest": __import__("hashlib").sha256(json.dumps([task.public() for task in tasks], sort_keys=True).encode()).hexdigest()}
            if scope_file.exists():
                saved = json.loads(scope_file.read_text(encoding="utf-8"))
                if saved["mandate"] != mandate:
                    raise ValueError("Scope is already bound to different tasks or spend limits; recover the original scope")
                run_id = saved["run_id"]
            else:
                ledger = Ledger(data_dir / "ledger.sqlite")
                run_id = ledger.create_run([{"seed": args.seed, "policy": args.policy, "hold": budget,
                    "price_cap": cap, "allocation": budget, "tasks": [task.public() for task in tasks]}], budget, float_mode='TESTNET')
                scope_file.write_text(json.dumps({"run_id": run_id, "mandate": mandate}, indent=2) + "\n", encoding="utf-8")
            ledger = Ledger(data_dir / "ledger.sqlite")
            job = ledger.jobs(run_id)[0]
            live = MetalEngineRail(args.scope, mandate["provider_url"], cap, budget,
                                   client=MetalRail(args.scope, mandate["provider_url"][0] if isinstance(mandate["provider_url"], list) else mandate["provider_url"], cap, budget, execute=args.execute),
                                   expected_provider_ids=["local-gpu", "hosted-premium"] if job["policy"].startswith("real-") else None)
            rail = CompositeRail(MockRail(data_dir / args.scope / "simulated-rail.sqlite"), live)
            engine = Engine(ledger, rail)
            if args.recover:
                engine.recover(run_id)
                result = engine.snapshot(run_id)
            else:
                try:
                    result = engine.run(run_id, crash_at=args.crash_at, kill_at=args.kill_at)
                except InjectedCrash as error:
                    print(json.dumps({"mode": "TESTNET", "scope": args.scope, "run_id": run_id,
                                      "crash_injected": str(error), "next": "rerun with --recover"}, indent=2))
                    return 2
            attempts = ledger.attempts(job["id"])
            paid_attempts = [attempt for attempt in attempts if attempt["receipt"]]
            provider_spend = sum(attempt["price"] for attempt in paid_attempts)
            verification_spend = sum(attempt["verify_cost"] for attempt in attempts if attempt["passed"] is not None)
            verified_correct = len({attempt["step_id"] for attempt in attempts if attempt["passed"] == 1})
            hosted_usage = {name: sum((json.loads(attempt["provider_metadata"]) if attempt["provider_metadata"] else {}).get("usage", {}).get(name, 0)
                                      for attempt in paid_attempts)
                            for name in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}
            failed_spend = sum(attempt["price"] for attempt in paid_attempts if attempt["passed"] != 1)
            failed_spend += sum(attempt["verify_cost"] for attempt in attempts if attempt["passed"] == 0)
            report = {"label": "MEASURED" if paid_attempts else "BLOCKED", "mode": "TESTNET", "policy": job["policy"], "customer_hold": "SIMULATED",
                      "verification_fee_label": "SIMULATED",
                      "receipt_links": [{"key": a['key'], "receipt": a['receipt'], "price": a['price'],
                                         "mandate_version": a['mandate_version']} for a in paid_attempts],
                      "customer_captured_micro_usd": 0, "run_id": run_id, "scope": args.scope,
                      "job": job["id"], "seed": args.seed, "steps": len(tasks),
                      "task_digest": mandate["task_digest"], "observed_at": time.time(),
                      "paid_steps": len(paid_attempts), "simulator_fallbacks": 0,
                      "measured_cost": {"asset": "testnet USDZ, micro-USD accounting units",
                        "provider_spend_micro_usd": provider_spend,
                        "verification_spend_micro_usd": verification_spend,
                        "total_micro_usd": provider_spend + verification_spend,
                        "verified_correct_steps": verified_correct,
                        "cost_per_verified_correct_micro_usd": (provider_spend + verification_spend) / verified_correct if verified_correct else None,
                        "merchant_absorbed_failure_micro_usd": failed_spend,
                        "hosted_token_usage": hosted_usage,
                        "hosted_api_dollar_cost_included": False},
                      "snapshot": result}
            if job["policy"].startswith("real-"):
                results_dir = data_dir / "results"
                results_dir.mkdir(parents=True, exist_ok=True)
                target = results_dir / (args.scope + ".json")
                temporary = target.with_suffix(".tmp")
                temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
                temporary.replace(target)
                report["evidence_file"] = str(target.relative_to(ROOT))
            if args.output:
                target = Path(args.output)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
            print(json.dumps(report, indent=2, allow_nan=False))
            return 0 if result["jobs"][0]["status"] == "COMPLETED" else 2
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
        elif args.command == "airwallex-checkout":
            from .treasury import AirwallexSandbox
            from .holds import OperationJournal, micro_usd
            from .checkout import HostedCheckoutWorkflow
            workflow = HostedCheckoutWorkflow(AirwallexSandbox(), OperationJournal(args.journal))
            result = workflow.status(args.scope, micro_usd(args.hold_usd), args.recover) if args.status else \
                workflow.start(args.scope, micro_usd(args.hold_usd), args.recover)
            print(json.dumps(result, indent=2))
            return 0 if result.get("authorization_ready") or result.get("checkout_url") else 2
        elif args.command == "treasury-job":
            from .banked import BankedStore
            from .treasury_job import TreasuryFunding
            from .fx import FxJournal
            from .treasury import AirwallexSandbox
            needs_client = args.treasury_action == 'reconcile' or args.treasury_action == 'run' and args.execute
            workflow = TreasuryFunding(BankedStore(args.ledger), AirwallexSandbox() if needs_client else None, FxJournal(args.fx_journal))
            if args.treasury_action == 'prepare':
                quote = json.loads(Path(args.quote).read_text(encoding='utf-8'))
                result = workflow.prepare(args.scope, args.request_id, quote, args.customer_budget_currency,
                                          args.customer_budget_amount, args.demo_usdz_per_unit)
            elif args.treasury_action == 'run':
                result = workflow.execute(args.scope, args.execute, args.sell_currency, args.max_sell_amount)
            elif args.treasury_action == 'reconcile':
                result = workflow.reconcile(args.scope)
            else:
                result = workflow.report(args.scope)
            if args.output:
                target = Path(args.output)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            print(json.dumps(result, indent=2))
        elif args.command == "airwallex-retire":
            from .holds import OperationJournal
            from .treasury import AirwallexSandbox
            if not args.execute:
                print(json.dumps({"label": "BLOCKED", "state": "PREVIEW", "scope": args.scope,
                                  "replacement_scope": args.replacement_scope, "money_moved": False,
                                  "next": "Review evidence, then pass --execute to record local retirement"}))
                return 0
            evidence = json.loads(Path(args.evidence).read_text(encoding='utf-8'))
            result = OperationJournal(args.journal).retire(args.scope, args.replacement_scope, evidence, AirwallexSandbox())
            print(json.dumps(result, indent=2))
        elif args.command == "airwallex-fx":
            from .treasury import AirwallexSandbox
            from .fx import FxJournal, execute_conversion, spend_report
            client = AirwallexSandbox() if args.fx_action != 'convert' or args.execute else None
            if args.fx_action == "balances":
                print(json.dumps({"mode": "SANDBOX", "balances": client.current_balances(), "writes_performed": False}, indent=2))
            elif args.fx_action == "quote":
                result = client.create_fx_quote(args.sell_currency, args.buy_currency, args.sell_amount, args.validity)
                target = Path(args.output)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({"mode": "SANDBOX", "quote_id": result["quote_id"],
                                  "sell_currency": result["sell_currency"], "sell_amount": result["sell_amount"],
                                  "buy_currency": result["buy_currency"], "buy_amount": result["buy_amount"],
                                  "client_rate": result.get("client_rate"), "valid_to_at": result.get("valid_to_at"),
                                  "quote_file": str(target), "conversion_created": False}, indent=2))
            elif args.fx_action == "convert":
                quote = json.loads(Path(args.quote).read_text(encoding="utf-8"))
                if not args.execute:
                    print(json.dumps({"mode": "SANDBOX", "request_id": args.request_id,
                                      "quote_id": quote.get("quote_id"), "conversion_created": False,
                                      "requires_explicit_execute": True}, indent=2))
                    return 0
                from .treasury_job import validate_cap
                validate_cap(quote, args.sell_currency, args.max_sell_amount)
                conversion = execute_conversion(client, FxJournal(args.journal), quote, args.request_id)
                print(json.dumps({"mode": "SANDBOX", "conversion": conversion,
                                  "note": "Use airwallex-fx report to verify wallet balance-history entries"}, indent=2))
            else:
                print(json.dumps(spend_report(client, FxJournal(args.journal), args.request_id), indent=2))
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
    finally:
        owners.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
