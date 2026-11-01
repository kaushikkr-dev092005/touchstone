"""Loopback dashboard and SSE. All browser mutations require a session token."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlparse

from .engine import Engine
from .ledger import Ledger, PolicyError
from .payments import MockRail

ROOT = Path(__file__).resolve().parent.parent


def usd_to_micros(value):
    if not isinstance(value, str):
        raise ValueError("Limit amounts must be decimal USD strings")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("Limit amounts must be valid decimal USD strings") from None
    micros = amount * 1_000_000
    if not amount.is_finite() or amount <= 0 or micros != micros.to_integral_value():
        raise ValueError("Limit amounts must be positive and precise to at most six decimals")
    return int(micros)


def serve(port=8088, data_dir="data"):
    ledger = Ledger(Path(data_dir) / "ledger.sqlite")
    engine = Engine(ledger, MockRail(Path(data_dir) / "rail.sqlite"))
    if any(j["status"] == "RUNNING" for j in ledger.jobs()):
        ledger.halt("Server restart paused orphaned jobs; operator resume reconciles pending purchases first")
    token = secrets.token_urlsafe(32)
    worker = None
    worker_lock = threading.Lock()
    last_error = None

    def start_worker(run_id):
        nonlocal worker, last_error
        def work():
            nonlocal last_error
            try:
                engine.run(run_id, delay=.12)
            except Exception as error:
                last_error = type(error).__name__
                ledger.event("WORKER_ERROR", {"type": last_error})
        last_error = None
        worker = threading.Thread(target=work, daemon=True)
        worker.start()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def allowed(self):
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def send_bytes(self, status, body, mime="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", f"default-src 'self'; script-src 'nonce-{token}'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def respond(self, status, payload):
            self.send_bytes(status, json.dumps(payload, allow_nan=False).encode())

        def do_GET(self):
            if not self.allowed():
                return self.respond(403, {"error": "Loopback host required"})
            path = urlparse(self.path).path
            if path == "/":
                page = (ROOT / "apps/dashboard/index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", token)
                return self.send_bytes(200, page.encode(), "text/html; charset=utf-8")
            if path == "/api/state":
                return self.respond(200, {**engine.snapshot(), "worker_error": last_error,
                                          "worker_running": bool(worker and worker.is_alive())})
            if path == "/api/benchmark":
                p = ROOT / "bench/results/simulated.json"
                return self.respond(200, json.loads(p.read_text()) if p.exists() else {"summary": [], "mode": "NOT_RUN"})
            if path == "/api/noisy-verification-chart":
                chart = ROOT / "bench/results/noisy-verification.svg"
                if not chart.exists():
                    return self.respond(404, {"error": "Generate the benchmark before loading the chart"})
                return self.send_bytes(200, chart.read_bytes(), "image/svg+xml; charset=utf-8")
            if path == "/api/readiness":
                from .readiness import inspect
                return self.respond(200, inspect())
            if path == "/api/procurement-evidence":
                from .procurement_evidence import summary
                return self.respond(200, summary())
            if path == "/api/banked-jobs":
                from .banked import BankedStore
                p = ROOT / 'data/banked/ledger.sqlite'
                if not p.exists():
                    return self.respond(200, {"mode": "SANDBOX_TESTNET", "jobs": [], "funded_run_verified": False})
                store = BankedStore(p)
                return self.respond(200, {"mode": "SANDBOX_TESTNET", "jobs": store.jobs(), "audit": store.ledger.audit()})
            if path == "/api/audit":
                return self.respond(200, {"audit": ledger.audit(), "events": ledger.events(limit=100000)})
            if path == "/api/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    try:
                        cursor = max(0, int(self.headers.get("Last-Event-ID", "0")))
                    except ValueError:
                        cursor = 0
                    for _ in range(1800):
                        events = ledger.events(cursor, 100)
                        if events:
                            cursor = events[-1]["id"]
                        payload = json.dumps({"state": engine.snapshot(), "events": events, "worker_error": last_error})
                        self.wfile.write(f"id: {cursor}\ndata: {payload}\n\n".encode())
                        self.wfile.flush()
                        time.sleep(.9)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                self.close_connection = True
                return
            return self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if not self.allowed() or self.headers.get("X-Touchstone-Token") != token:
                return self.respond(403, {"error": "Local session token required"})
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
                return self.respond(403, {"error": "Origin refused"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 4096:
                    return self.respond(413, {"error": "Request too large"})
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
                with worker_lock:
                    busy = worker and worker.is_alive()
                    if self.path == "/api/halt":
                        ledger.halt()
                        return self.respond(200, {"halted": True})
                    if busy:
                        return self.respond(409, {"error": "A run is active; halt it before changing execution"})
                    if self.path == "/api/approve-increase":
                        approved = ledger.approve_mandate_increase(
                            payload.get("job_id"), payload.get("expected_version"),
                            usd_to_micros(payload.get("hold_usd")),
                            usd_to_micros(payload.get("budget_usd")),
                            usd_to_micros(payload.get("price_cap_usd")),
                            usd_to_micros(payload.get("allocation_usd")),
                            payload.get("approver"), payload.get("reason"))
                        return self.respond(200, {"approved": True, "resumed": False,
                            "remote_authorization_changed": False, **approved})
                    if self.path == "/api/demo":
                        if any(j["status"] != "COMPLETED" for j in ledger.jobs()):
                            return self.respond(409, {"error": "Resume or close the previous jobs before starting another run"})
                        ledger.resume()
                        seed = payload.get("seed", 42)
                        if type(seed) is not int or not 0 <= seed <= 100000:
                            raise ValueError("Seed must be an integer from 0 to 100000")
                        run_id = engine.create_demo(seed)
                        start_worker(run_id)
                        return self.respond(202, {"run_id": run_id})
                    if self.path == "/api/resume":
                        jobs = [j for j in ledger.jobs() if j["status"] != "COMPLETED"]
                        if not jobs:
                            raise ValueError("No paused jobs")
                        ledger.resume()
                        start_worker(jobs[0]["run_id"])
                        return self.respond(202, {"resumed": True, "limits_changed": False})
                    if self.path == "/api/close":
                        engine.recover()
                        for j in ledger.jobs():
                            if j["status"] != "COMPLETED":
                                ledger.settle_job(j["id"])
                        return self.respond(200, {"closed": True, "mode": "SIMULATED"})
                    return self.respond(404, {"error": "Not found"})
            except (ValueError, PolicyError, json.JSONDecodeError) as error:
                return self.respond(400, {"error": str(error)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Touchstone: http://127.0.0.1:{port} | SIMULATED treasury, rail and inference", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        ledger.halt()
        server.server_close()
