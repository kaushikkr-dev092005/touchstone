"""Multi-job financial invariants under contention and randomized operation order.

Roadmap exit gate (4-6 November): no job exceeds its hold, no allocation exceeds
funded float, every uncertain purchase stays visible, and a receipt is never
issued twice for one purchase key.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import random
import tempfile
import time
import unittest

from touchstone.engine import Engine
from touchstone.ledger import Ledger, PolicyError
from touchstone.payments import MockRail
from touchstone.providers import CATALOG, Quote
from touchstone.workload import generate

ACTIVE = ("RESERVED", "DISPATCHING", "PAID")


def assert_invariants(test, ledger, rail):
    with ledger.connect() as db:
        jobs = [dict(r) for r in db.execute("SELECT * FROM jobs")]
        runs = {r["id"]: r["float_total"] for r in db.execute("SELECT * FROM runs")}
        attempts = [dict(r) for r in db.execute("SELECT * FROM attempts")]
    for run_id, float_total in runs.items():
        allocated = sum(j["allocation"] for j in jobs if j["run_id"] == run_id)
        test.assertLessEqual(allocated, float_total, "allocations exceed funded operator float")
    for job in jobs:
        own = [a for a in attempts if a["job_id"] == job["id"]]
        in_flight = sum(a["price"] + a["verify_cost"] for a in own if a["state"] in ACTIVE)
        test.assertLessEqual(job["spent"] + in_flight, min(job["hold"], job["budget"]),
                             "spent plus in-flight exceeds the authorized hold")
        reserved_rail = sum(a["price"] for a in own if a["state"] in {"RESERVED", "DISPATCHING"})
        test.assertLessEqual(job["rail_spent"] + reserved_rail, job["allocation"],
                             "provider spend plus reservations exceeds allocated float")
        test.assertLessEqual(job["captured"], job["hold"])
        test.assertEqual(job["rail_spent"], sum(a["price"] for a in own if a["receipt"]))
        for step in {a["step_id"] for a in own}:
            active = [a for a in own if a["step_id"] == step and a["state"] in ACTIVE]
            test.assertLessEqual(len(active), 1, "a step has two live purchases")
            if any(a["passed"] == 1 for a in own if a["step_id"] == step):
                test.assertEqual(active, [], "an accepted step still has a live purchase")
    receipts = rail.receipts()
    test.assertEqual(len({r["key"] for r in receipts}), len(receipts), "rail issued two receipts for one key")
    keys = {a["key"] for a in attempts}
    test.assertTrue({r["key"] for r in receipts} <= keys, "rail receipt without a local reservation")


def offer(provider="balanced", ttl=300):
    return Quote(f"{provider}-q", provider, CATALOG[provider]["price"], CATALOG[provider]["latency"],
                 time.time() + ttl)


class ContentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledger = Ledger(self.root / "ledger.sqlite")
        self.rail = MockRail(self.root / "rail.sqlite")
        self.addCleanup(self.temp.cleanup)

    def three_jobs(self, hold, allocation, float_total, count=24):
        specs, tasks = [], {}
        for offset in range(3):
            generated, _ = generate(42 + offset, count)
            specs.append({"seed": 42 + offset, "policy": "touchstone", "hold": hold, "allocation": allocation,
                          "price_cap": 60000, "tasks": [t.public() for t in generated]})
            tasks[offset] = generated
        run_id = self.ledger.create_run(specs, float_total)
        jobs = self.ledger.jobs(run_id)
        return {job["id"]: tasks[index] for index, job in enumerate(jobs)}

    def test_float_is_the_binding_limit_under_twelve_way_contention(self):
        # Float 300k fully pre-allocated 100k per job: no job may top up, so each
        # can reserve exactly five 20k purchases however threads interleave.
        plan = self.three_jobs(hold=400000, allocation=100000, float_total=300000)
        work = [(job, task) for job, tasks in plan.items() for task in tasks]
        random.Random(7).shuffle(work)

        def attempt(item):
            job, task = item
            try:
                self.ledger.reserve(job, task, 0, offer("balanced"), 1000)
                return job
            except PolicyError:
                return None

        with ThreadPoolExecutor(max_workers=12) as pool:
            granted = [job for job in pool.map(attempt, work) if job]
        for job in plan:
            self.assertEqual(granted.count(job), 5, f"{job} reserved the wrong number of purchases")
        assert_invariants(self, self.ledger, self.rail)

    def test_hold_is_the_binding_limit_when_float_is_ample(self):
        plan = self.three_jobs(hold=100000, allocation=100000, float_total=900000)
        work = [(job, task) for job, tasks in plan.items() for task in tasks]
        random.Random(11).shuffle(work)

        def attempt(item):
            job, task = item
            try:
                self.ledger.reserve(job, task, 0, offer("economy"), 1000)
                return job
            except PolicyError:
                return None

        with ThreadPoolExecutor(max_workers=12) as pool:
            granted = [job for job in pool.map(attempt, work) if job]
        for job in plan:
            # 11,000 per purchase (10,000 price + 1,000 verification) against a 100,000 hold.
            self.assertEqual(granted.count(job), 9)
        assert_invariants(self, self.ledger, self.rail)

    def test_contended_purchases_settle_without_duplicate_receipts(self):
        plan = self.three_jobs(hold=400000, allocation=100000, float_total=300000, count=8)
        engine = Engine(self.ledger, self.rail)
        work = [(job, task) for job, tasks in plan.items() for task in tasks]
        random.Random(3).shuffle(work)

        def buy(item):
            job, task = item
            quote = offer("balanced")
            try:
                key = self.ledger.reserve(job, task, 0, quote, 1000)
            except PolicyError:
                return
            receipt = self.rail.pay(key, quote, lambda: {"total_cents": 1})
            self.ledger.record_paid(key, receipt)
            self.ledger.finish_attempt(key, receipt["output"], {"passed": True, "score": 1.0, "reason": "fixture"})

        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(buy, work))
        assert_invariants(self, self.ledger, self.rail)
        for job in plan:
            self.ledger.settle_job(job)
        assert_invariants(self, self.ledger, self.rail)
        report = engine.reconcile()
        self.assertTrue(report["matched"], report["mismatches"])
        self.assertEqual(report["ledger_provider_total"], report["rail_total"])


class RandomizedOperationTests(unittest.TestCase):
    """Seeded random interleavings, including crashes between remote and local commit."""

    def run_sequence(self, seed, steps=160):
        rng = random.Random(seed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger, rail = Ledger(root / "l.sqlite"), MockRail(root / "r.sqlite")
            engine = Engine(ledger, rail)
            tasks = {}
            specs = []
            for offset in range(3):
                generated, _ = generate(seed + offset, 10)
                tasks[offset] = generated
                specs.append({"seed": seed + offset, "policy": "touchstone", "hold": rng.choice([60000, 120000, 400000]),
                              "allocation": 50000, "price_cap": 60000, "tasks": [t.public() for t in generated]})
            run_id = ledger.create_run(specs, 200000)
            jobs = [j["id"] for j in ledger.jobs(run_id)]
            by_job = {job: tasks[i] for i, job in enumerate(jobs)}
            quotes_by_key = {}
            for _ in range(steps):
                op = rng.choice(["reserve"] * 5 + ["dispatch_only", "pay", "pay_crash", "finish", "void", "recover", "halt_resume"])
                state = ledger.attempts()
                try:
                    if op == "reserve":
                        job = rng.choice(jobs)
                        task = rng.choice(by_job[job])
                        past = [a for a in state if a["job_id"] == job and a["step_id"] == task.id]
                        quote = offer(rng.choice(list(CATALOG)))
                        key = ledger.reserve(job, task, len(past), quote, 1000)
                        quotes_by_key[key] = quote
                    elif op in {"dispatch_only", "pay", "pay_crash"}:
                        pending = [a for a in state if a["state"] == "RESERVED"]
                        if pending:
                            a = rng.choice(pending)
                            ledger.assert_can_pay(a["key"])
                            if op == 'dispatch_only':
                                assert_invariants(self, ledger, rail)
                                continue  # death after barrier, before any rail call
                            receipt = rail.pay(a["key"], quotes_by_key[a["key"]], lambda: {"total_cents": 1})
                            if op == "pay":  # pay_crash: remote succeeded, local commit never ran
                                ledger.record_paid(a["key"], receipt)
                    elif op == "finish":
                        paid = [a for a in state if a["state"] == "PAID"]
                        if paid:
                            a = rng.choice(paid)
                            ledger.finish_attempt(a["key"], {"total_cents": 1},
                                                  {"passed": rng.random() < .7, "score": 1.0, "reason": "fixture"})
                    elif op == "void":
                        # Only legitimate if the rail confirms no payment, as Engine.recover enforces.
                        reserved = [a for a in state if a["state"] in {'RESERVED', 'DISPATCHING'}
                                    and rail.lookup(a["key"])["state"] == "NOT_DISPATCHED"]
                        if reserved:
                            ledger.void(rng.choice(reserved)["key"], "fixture: rail confirms no payment", authoritative=True)
                    elif op == "recover":
                        engine.recover(run_id)
                    elif op == "halt_resume":
                        ledger.halt()
                        ledger.resume()
                except PolicyError:
                    pass  # a refused action is the control working
                assert_invariants(self, ledger, rail)
            # Drive every uncertain purchase to resolution; the same receipt must be reused.
            before = {r["key"]: r["id"] for r in rail.receipts()}
            engine.recover(run_id)
            after = {r["key"]: r["id"] for r in rail.receipts()}
            self.assertEqual(before, after, "recovery changed or duplicated a receipt")
            assert_invariants(self, ledger, rail)
            for a in ledger.attempts():
                if a["key"] in after:
                    self.assertIn(a["state"], {"PAID", "VERIFIED_OK", "VERIFIED_FAIL"},
                                  "remote payment exists but local state denies it")
            return {'label': 'MOCK', 'seed': seed, 'operations': steps, 'invariant_checks': steps+1,
                    'receipts': len(after), 'duplicate_receipts': 0, 'audit': ledger.audit()}

    def test_many_seeded_interleavings_hold_all_invariants(self):
        for seed in range(100, 108):
            with self.subTest(seed=seed):
                self.run_sequence(seed)


if __name__ == "__main__":
    unittest.main()
