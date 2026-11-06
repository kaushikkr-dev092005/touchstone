"""Round-robin orchestration across jobs; recovery precedes new purchases."""
import json
from contextlib import ExitStack
import os
import time
from .ledger import PolicyError
from .metal import PaymentPending
from .providers import Quote, quotes, simulate
from .router import Router
from .verifier import VERIFY_COST, VERIFIER_VERSION, check, source_supported
from .workload import Task, generate


class InjectedCrash(Exception):
    pass


class Engine:
    def __init__(self, ledger, rail, fault_pipeline=None):
        self.ledger, self.rail, self.fault_pipeline = ledger, rail, fault_pipeline

    def _fault(self, key, verdict):
        """A deterministic verification failure may become a signed fault receipt; never blocks procurement."""
        if self.fault_pipeline is not None and verdict.get("passed") is False:
            self.fault_pipeline.handle(key)

    def create_demo(self, seed=42, count=24, failed_call_policy='CUSTOMER_PAYS'):
        specs = []
        for offset, hold in enumerate([1000000, 750000, 750000]):
            tasks, _ = generate(seed + offset, count)
            specs.append({"seed": seed + offset, "policy": "touchstone", "hold": hold,
                          "price_cap": 60000, "allocation": 300000,
                          "tasks": [t.public() for t in tasks]})
        return self.ledger.create_run(specs, 1500000, failed_call_policy=failed_call_policy)

    def _jobs(self, run_id=None, job_id=None):
        jobs = self.ledger.jobs(run_id)
        if job_id is not None:
            jobs = [j for j in jobs if j['id'] == job_id]
            if not jobs:
                raise PolicyError('Job does not belong to this run')
        return jobs

    def recover(self, run_id=None, job_id=None):
        jobs = self._jobs(run_id, job_id)
        with ExitStack() as stack:
            for job in sorted(jobs, key=lambda j: j['id']):
                stack.enter_context(self.ledger.worker(job['id']))
            return self._recover(jobs)

    def _recover(self, selected_jobs):
        recovered = 0
        jobs = {j["id"]: j for j in selected_jobs}
        for a in self.ledger.attempts():
            if a["job_id"] not in jobs or a["state"] not in {"RESERVED", "DISPATCHING", "PAID"}:
                continue
            quote = json.loads(a["quote"])
            try:
                outcome = self.rail.lookup(a["key"], quote)
            except PaymentPending:
                outcome = {"state": "UNKNOWN"}
            state = outcome.get("state") if isinstance(outcome, dict) else "UNKNOWN"
            if state in {'UNKNOWN', 'RESERVED', 'PAID_OUTPUT_MISSING'} and hasattr(self.rail, 'recover'):
                try:
                    outcome = self.rail.recover(a["key"], quote)
                except PaymentPending:
                    outcome = {"state": "UNKNOWN"}
                state = outcome.get("state") if isinstance(outcome, dict) else "UNKNOWN"
            if state in {"NOT_DISPATCHED", "UNPAID_CONFIRMED"} and outcome.get("authoritative"):
                self.ledger.void(a["key"], "Rail authoritatively confirms no payment; release reservation", authoritative=True)
                continue
            if state != "PAID":
                reason = "Rail outcome remains unknown; reservation retained and this job is paused"
                self.ledger.status(a["job_id"], "PAUSED_RECOVERY", reason)
                self.ledger.event("RECOVERY_PENDING", {"job_id": a["job_id"], "key": a["key"], "state": state or "UNKNOWN", "mode": self.rail.mode})
                continue
            receipt = outcome
            self.ledger.record_paid(a["key"], receipt)
            task = next(Task(**t) for t in json.loads(jobs[a["job_id"]]["tasks"]) if t["id"] == a["step_id"])
            verdict = check(task, receipt["output"])
            self.ledger.finish_attempt(a["key"], receipt["output"], verdict)
            self._fault(a["key"], verdict)
            if not verdict.get("retryable", True):
                self.ledger.status(a["job_id"], "PAUSED_REVIEW", verdict["reason"])
            recovered += 1
        if recovered:
            self.ledger.event("RECOVERED", {"attempts": recovered, "mode": self.rail.mode})
        return recovered

    def run(self, run_id, delay=0, crash_at=None, kill_at=None, job_id=None):
        jobs = self._jobs(run_id, job_id)
        with ExitStack() as stack:
            owners = {job['id']: stack.enter_context(self.ledger.worker(job['id']))
                      for job in sorted(jobs, key=lambda j: j['id'])}
            self._run(run_id, delay, crash_at, kill_at, job_id, owners)
        return self.snapshot(run_id, job_id)

    def _run(self, run_id, delay, crash_at, kill_at, job_id, owners):
        if crash_at and kill_at:
            raise ValueError("Choose either exception-based crash injection or process termination")
        self._recover(self._jobs(run_id, job_id))
        routers = {}
        for j in self._jobs(run_id, job_id):
            router = routers[j["id"]] = Router(j["seed"])
            for a in self.ledger.attempts(j["id"]):
                if a["passed"] is not None and (not a["verdict"] or json.loads(a["verdict"]).get("retryable", True)):
                    kind = next(t["kind"] for t in json.loads(j["tasks"]) if t["id"] == a["step_id"])
                    router.observe(a["provider"], kind, a["passed"])
        while True:
            progressed = False
            for job in self._jobs(run_id, job_id):
                if job["status"] != "RUNNING":
                    continue
                router = routers[job["id"]]
                attempts = self.ledger.attempts(job["id"])
                tasks = [Task(**t) for t in json.loads(job["tasks"])]
                max_attempts = 2 if job["policy"] == "real-touchstone" else 3 if job["policy"] == "touchstone" else 1
                task = None
                for index, candidate in enumerate(tasks):
                    past = [a for a in attempts if a["step_id"] == candidate.id]
                    # A voided reservation (rail authoritatively confirmed no payment) bought
                    # nothing: it must not count toward the attempt limit or tier escalation.
                    live = [a for a in past if a["state"] != "VOID"]
                    exhausted = any(a["provider"] == "premium" and a["state"] == "VERIFIED_FAIL" for a in live)
                    if not exhausted and not any(a["passed"] == 1 for a in live) and len(live) < max_attempts:
                        task = candidate
                        break
                if task is None:
                    self.ledger.settle_job(job["id"])
                    progressed = True
                    continue
                supported, why = source_supported(task)
                if not supported:
                    # Never buy inference for a source that no provider answer could verify.
                    self.ledger.status(job["id"], "PAUSED_REVIEW", why)
                    continue
                attempt = 1 + max(a["attempt"] for a in past) if past else 0  # keys stay unique across voids
                # Demo job 2 grows 4x halfway through; identical index events in benchmark policies.
                inflated = job["policy"] == "touchstone" and job["id"].endswith("-2") and index >= len(tasks) // 2 and len(tasks) < 100
                scenario_index = int(index * 100 / len(tasks)) if len(tasks) < 100 else index
                previous_index = int((index - 1) * 100 / len(tasks)) if len(tasks) < 100 else index - 1
                real_policy = job["policy"] in {"real-cheapest", "real-premium", "real-touchstone"}
                offers = [] if real_policy else quotes(job["seed"], scenario_index, inflated)
                if hasattr(self.rail, "quote_for_task"):
                    live_offer = self.rail.quote_for_task(task)
                    if isinstance(live_offer, list):
                        offers.extend(live_offer)
                    elif live_offer is not None:
                        offers.append(live_offer)
                if attempt == 0 and not real_policy:
                    for threshold, label in {20: "Economy latency spike", 35: "Balanced price spike", 50: "Balanced quality drop"}.items():
                        if previous_index < threshold <= scenario_index:
                            self.ledger.event("CHAOS", {"job_id": job["id"], "index": index, "event": label})
                    if inflated and index == len(tasks) // 2:
                        self.ledger.event("CHAOS", {"job_id": job["id"], "index": index, "event": "4x prompt expansion"})
                offer, reason = router.select(offers, task, job, [a["provider"] for a in live])
                if offer is None:
                    self.ledger.status(job["id"], "PAUSED_POLICY", reason)
                    continue
                try:
                    key = self.ledger.reserve(job["id"], task, attempt, offer, VERIFY_COST,
                                              expected_version=job['mandate_version'])
                    if crash_at == "after_reserve":
                        raise InjectedCrash("Crash after reservation, before rail request")
                    if kill_at == "after_reserve":
                        os._exit(86)
                    self.ledger.event("ROUTED", {"job_id": job["id"], "step_id": task.id, "provider": offer.provider, "reason": reason, "quote": offer.public()})
                    self.ledger.assert_can_pay(key, owners[job['id']])
                    receipt = self.rail.pay(key, offer, lambda: simulate(task, offer.provider, job["seed"], scenario_index, attempt))
                    if crash_at == "after_rail":
                        raise InjectedCrash("Crash after durable rail receipt, before local payment commit")
                    if kill_at == "after_rail":
                        os._exit(86)
                    self.ledger.record_paid(key, receipt)
                    if crash_at == "after_paid":
                        raise InjectedCrash("Crash after payment commit, before verification")
                    if kill_at == "after_paid":
                        os._exit(86)
                    verdict = check(task, receipt["output"])
                    self.ledger.finish_attempt(key, receipt["output"], verdict)
                    self._fault(key, verdict)
                    if verdict.get("retryable", True):
                        router.observe(offer.provider, task.kind, verdict["passed"])
                    else:
                        self.ledger.status(job["id"], "PAUSED_REVIEW", verdict["reason"])
                    progressed = True
                except PolicyError as error:
                    self.ledger.status(job["id"], "PAUSED_POLICY", str(error))
                except PaymentPending:
                    self.ledger.status(job['id'], 'PAUSED_RECOVERY', 'Payment outcome unknown; reservation retained')
                if delay:
                    time.sleep(delay)
            if not progressed:
                return

    def reconcile(self, run_id=None, job_id=None):
        jobs = self._jobs(run_id, job_id)
        ids = {j["id"] for j in jobs}
        attempts = [a for a in self.ledger.attempts() if a["job_id"] in ids]
        keys = {a["key"] for a in attempts}
        receipts = [r for r in self.rail.receipts() if run_id is None and job_id is None or r["key"] in keys]
        paid = {a["key"]: a for a in attempts if a["receipt"]}
        mismatches = []
        for r in receipts:
            a = paid.get(r["key"])
            if not a or a["receipt"] != r["id"] or a["price"] != r["amount"] or a["provider"] != r["provider"] or json.loads(a["quote"])["id"] != r["quote_id"]:
                mismatches.append({"key": r["key"], "reason": "Rail receipt differs from local committed payment"})
        rail_keys = {r["key"] for r in receipts}
        mismatches += [{"key": k, "reason": "Local payment has no rail receipt"} for k in paid if k not in rail_keys]
        pending = sum(a["state"] in {"RESERVED", "DISPATCHING", "PAID"} for a in attempts)
        return {"matched": not mismatches and not pending,
                "ledger_provider_total": sum(a["price"] for a in paid.values()),
                "rail_total": sum(r["amount"] for r in receipts),
                "verification_total": sum(a["verify_cost"] for a in attempts if a["passed"] is not None),
                "customer_captured": sum(j["captured"] for j in jobs),
                "pending": pending, "mismatches": mismatches,
                "airwallex": "NOT_RECONCILED: customer holds/captures are simulated; no fiat-token bridge",
                "mode": self.rail.mode}

    def snapshot(self, run_id=None, job_id=None):
        jobs = self._jobs(run_id, job_id)
        ids = {j["id"] for j in jobs}
        attempts = [a for a in self.ledger.attempts() if a["job_id"] in ids]
        for j in jobs:
            own = [a for a in attempts if a["job_id"] == j["id"]]
            j["count"] = len(json.loads(j.pop("tasks")))
            j["accepted"] = sum(a["passed"] == 1 for a in own)
            j["failed_attempts"] = sum(a["passed"] == 0 for a in own)
            j["reserved"] = sum(a["price"] + a["verify_cost"] for a in own if a["state"] in {"RESERVED", "DISPATCHING", "PAID"})
        with self.ledger.connect() as db:
            runs = [dict(r) for r in db.execute("SELECT * FROM runs ORDER BY rowid DESC")]
            halted = bool(db.execute("SELECT halted FROM control").fetchone()[0])
        from .financials import summarize
        return {"jobs": jobs, "runs": runs, "halted": halted,
                "financials":summarize(jobs,attempts,runs,self.rail.mode),
                "attempts": [{**{k: a[k] for k in ("job_id", "step_id", "attempt", "state", "provider", "price", "verify_cost", "score", "reason", "receipt")},
                              "provider_metadata": json.loads(a["provider_metadata"]) if a.get("provider_metadata") else None}
                             for a in attempts[-80:]],
                "reconciliation": self.reconcile(run_id, job_id), "audit": self.ledger.audit(),
                "verifier_version": VERIFIER_VERSION,
                "modes": {"airwallex": "SIMULATED", "metal": self.rail.mode, "inference": self.rail.mode}}
