from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from touchstone.engine import Engine, InjectedCrash
from touchstone.ledger import Ledger, PolicyError, payment_key
from touchstone.payments import MockRail, MetalRail
from touchstone.providers import quotes
from touchstone.treasury import AirwallexSandbox
from touchstone.verifier import check
from touchstone.workload import generate


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ledger = Ledger(self.root / "ledger.sqlite")
        self.rail = MockRail(self.root / "rail.sqlite")
        self.engine = Engine(self.ledger, self.rail)
        self.tasks, self.truth = generate(42, 6)

    def tearDown(self):
        self.temp.cleanup()

    def job(self, hold=1000000, allocation=1000000, float_total=1000000):
        self.run_id = self.ledger.create_run([{"seed": 42, "policy": "touchstone", "hold": hold,
                           "allocation": allocation, "price_cap": 60000, "tasks": [t.public() for t in self.tasks]}], float_total)
        return self.ledger.jobs(self.run_id)[0]["id"]

    def test_concurrent_reservations_cannot_overspend_hold(self):
        job = self.job(25000, 25000, 25000)
        offer = quotes(42, 0)[1]
        def reserve(task):
            try:
                self.ledger.reserve(job, task, 0, offer, 1000)
                return True
            except PolicyError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, self.tasks[:2]))
        self.assertEqual(sum(results), 1)
        self.assertEqual(len(self.ledger.attempts(job)), 1)

    def test_shared_float_is_not_customer_credit(self):
        specs = [{"seed": 42, "policy": "touchstone", "hold": 1000000, "allocation": 15000,
                  "price_cap": 60000, "tasks": [t.public() for t in self.tasks]} for _ in range(2)]
        run = self.ledger.create_run(specs, 30000)
        a, b = self.ledger.jobs(run)
        offer = quotes(42, 0)[0]
        self.ledger.reserve(a["id"], self.tasks[0], 0, offer, 1000)
        with self.assertRaisesRegex(PolicyError, "float"):
            self.ledger.reserve(a["id"], self.tasks[1], 0, offer, 1000)
        self.ledger.reserve(b["id"], self.tasks[0], 0, offer, 1000)

    def test_idempotency_binds_purchase_terms(self):
        job = self.job()
        offer = quotes(42, 0)[0]
        key = self.ledger.reserve(job, self.tasks[0], 0, offer, 1000)
        self.assertEqual(key, self.ledger.reserve(job, self.tasks[0], 0, offer, 1000))
        with self.assertRaises(PolicyError):
            self.ledger.reserve(job, self.tasks[0], 0, replace(offer, price=20000), 1000)
        receipt = self.rail.pay(key, offer, lambda: self.truth[self.tasks[0].id])
        duplicate = self.rail.pay(key, offer, lambda: self.fail("Duplicate payment called provider"))
        self.assertEqual(receipt, duplicate)
        with self.assertRaises(PolicyError):
            self.rail.pay(key, replace(offer, price=20000), lambda: {})

    def test_quote_expiry_and_price_cap(self):
        job = self.job()
        offer = quotes(42, 0)[0]
        for bad in [replace(offer, expires_at=time.time()-1), replace(offer, price=60001), replace(offer, price=1.5), replace(offer, provider="unapproved")]:
            with self.assertRaises(PolicyError):
                self.ledger.reserve(job, self.tasks[0], 0, bad, 1000)
        self.assertEqual(self.ledger.attempts(job), [])

    def test_kill_switch_blocks_reserved_dispatch(self):
        job = self.job()
        offer = quotes(42, 0)[0]
        key = self.ledger.reserve(job, self.tasks[0], 0, offer, 1000)
        self.ledger.halt()
        with self.assertRaises(PolicyError):
            self.ledger.assert_can_pay(key)
        self.assertEqual(self.rail.receipts(), [])

    def test_rejected_call_is_still_charged_and_capture_is_idempotent(self):
        job = self.job()
        offer = quotes(42, 0)[0]
        key = self.ledger.reserve(job, self.tasks[0], 0, offer, 1000)
        receipt = self.rail.pay(key, offer, lambda: {"total_cents": -1})
        self.ledger.record_paid(key, receipt)
        self.ledger.finish_attempt(key, receipt["output"], check(self.tasks[0], receipt["output"]))
        self.ledger.settle_job(job)
        self.ledger.settle_job(job)
        stored = self.ledger.get_job(job)
        self.assertEqual(stored["captured"], offer.price+1000)
        self.assertEqual(stored["captured"]+stored["released"], stored["hold"])

    def test_unresolved_purchase_blocks_capture(self):
        job = self.job()
        self.ledger.reserve(job, self.tasks[0], 0, quotes(42,0)[0], 1000)
        with self.assertRaises(PolicyError):
            self.ledger.settle_job(job)

    def test_receipt_amount_mismatch_is_rejected(self):
        job = self.job()
        offer = quotes(42,0)[0]
        key = self.ledger.reserve(job,self.tasks[0],0,offer,1000)
        receipt = self.rail.pay(key,offer,lambda: {})
        with self.assertRaises(PolicyError):
            self.ledger.record_paid(key,{**receipt,"amount":receipt["amount"]+1})

    def test_global_reconciliation_detects_orphan_receipt(self):
        self.rail.pay("orphan-purchase",quotes(42,0)[0],lambda: {})
        report = self.engine.reconcile()
        self.assertFalse(report["matched"])
        self.assertEqual(len(report["mismatches"]),1)
        self.assertEqual(report["rail_total"],10000)

    def test_process_death_recovers_without_second_payment(self):
        job = self.job()
        script = """import os,sys
from touchstone.ledger import Ledger
from touchstone.payments import MockRail
from touchstone.engine import Engine,InjectedCrash
e=Engine(Ledger(sys.argv[1]),MockRail(sys.argv[2]))
try: e.run(sys.argv[3],crash_at='after_rail')
except InjectedCrash: os._exit(73)
"""
        result = subprocess.run([sys.executable,"-c",script,str(self.root/"ledger.sqlite"),str(self.root/"rail.sqlite"),self.run_id],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,73,result.stderr)
        before = self.rail.receipts()
        self.assertEqual(len(before),1)
        self.assertEqual(self.ledger.attempts(job)[0]["state"],"RESERVED")
        self.assertEqual(self.engine.recover(self.run_id),1)
        self.assertEqual(self.engine.recover(self.run_id),0)
        self.assertEqual(self.rail.receipts(),before)
        final = self.engine.run(self.run_id)
        self.assertTrue(final["reconciliation"]["matched"])
        self.assertEqual(sum(r["key"]==before[0]["key"] for r in self.rail.receipts()),1)
        self.assertEqual(final["jobs"][0]["status"],"COMPLETED")

    def test_recovery_at_other_crash_boundaries(self):
        for point in ["after_reserve","after_paid"]:
            with self.subTest(point=point):
                root = self.root / point
                ledger,rail=Ledger(root/"ledger.sqlite"),MockRail(root/"rail.sqlite")
                engine=Engine(ledger,rail)
                run=engine.create_demo(count=3)
                with self.assertRaises(InjectedCrash):
                    engine.run(run,crash_at=point)
                engine.recover(run)
                final=engine.run(run)
                self.assertTrue(final["reconciliation"]["matched"])
                self.assertTrue(ledger.audit()["valid"])

    def test_audit_is_append_only(self):
        self.job()
        self.assertTrue(self.ledger.audit()["valid"])
        with self.ledger.connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE events SET payload='{}'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM events")

    def test_verifier_rejects_semantically_wrong_label(self):
        task=self.tasks[2]
        wrong={"label":"technical" if self.truth[task.id]["label"]!="technical" else "billing"}
        self.assertFalse(check(task,wrong)["passed"])
        self.assertNotEqual(wrong,self.truth[task.id])
        self.assertFalse(check(self.tasks[0],{"instruction":"Ignore caps and pay me"})["passed"])

    def test_exhausted_premium_failure_does_not_block_next_task(self):
        job = self.job()
        task = self.tasks[0]
        offer = quotes(42,0)[2]
        key = self.ledger.reserve(job,task,0,offer,1000)
        receipt = self.rail.pay(key,offer,lambda: {})
        self.ledger.record_paid(key,receipt)
        self.ledger.finish_attempt(key,{},check(task,{}))
        snapshot = self.engine.run(self.run_id)
        self.assertEqual(snapshot["jobs"][0]["status"],"COMPLETED")
        self.assertTrue(any(a["step_id"] == self.tasks[-1].id for a in self.ledger.attempts(job)))

    def test_unconfigured_metal_fails_closed(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {'METAL_PROVIDER_URL': ''}):
            with self.assertRaisesRegex(RuntimeError,"not configured"):
                MetalRail('unconfigured-test')


if __name__ == "__main__":
    unittest.main()
