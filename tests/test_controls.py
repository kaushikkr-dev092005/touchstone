from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from touchstone.engine import Engine, InjectedCrash
from touchstone.ledger import Ledger, PolicyError, payment_key
from touchstone.payments import CompositeRail, MockRail, MetalRail
from touchstone.providers import quotes
from touchstone.router import Router
from touchstone.server import usd_to_micros
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

    def test_approved_mandate_increase_is_versioned_and_audited_before_resume(self):
        job_id = self.job(hold=1000000, allocation=800000, float_total=1000000)
        self.ledger.status(job_id, "PAUSED_POLICY", "Customer hold exhausted")
        approved = self.ledger.approve_mandate_increase(
            job_id, 1, 1250000, 1250000, 60000, 1000000, "Kaushik Kumar", "Customer approved a higher simulated hold")
        self.assertEqual(approved["mandate_version"], 2)
        self.assertEqual(approved["status"], "PAUSED_POLICY")
        stored = self.ledger.get_job(job_id)
        self.assertEqual((stored["hold"], stored["budget"], stored["allocation"], stored["mandate_version"]),
                         (1250000, 1250000, 1000000, 2))
        approval_event = next(event for event in reversed(self.ledger.events()) if event["kind"] == "MANDATE_INCREASE_APPROVED")
        self.assertEqual(approval_event["payload"]["approver"], "Kaushik Kumar")
        self.assertEqual(approval_event["payload"]["mode"], "SIMULATED")
        self.assertTrue(self.ledger.audit()["valid"])
        self.ledger.resume()
        self.assertEqual(self.ledger.get_job(job_id)["status"], "RUNNING")

    def test_mandate_increase_requires_pause_fresh_version_and_unused_float(self):
        job_id = self.job(hold=1000000, allocation=1000000, float_total=1000000)
        args = (job_id, 1, 1250000, 1250000, 60000, 1100000, "Operator", "Approved by operator")
        with self.assertRaisesRegex(PolicyError, "policy-paused"):
            self.ledger.approve_mandate_increase(*args)
        self.ledger.status(job_id, "PAUSED_POLICY", "Needs a new authorization")
        with self.assertRaisesRegex(PolicyError, "float"):
            self.ledger.approve_mandate_increase(*args)
        approved = self.ledger.approve_mandate_increase(job_id, 1, 1250000, 1250000, 60000, 1000000,
                                                       "Operator", "Approved by operator")
        with self.assertRaisesRegex(PolicyError, "version changed"):
            self.ledger.approve_mandate_increase(*args[:1], 1, 1500000, 1500000, 60000, 1000000,
                                                 "Operator", "Stale approval")
        self.assertEqual(approved["mandate_version"], 2)

    def test_mandate_increase_cannot_hide_an_unresolved_purchase(self):
        job_id = self.job(hold=1000000, allocation=1000000, float_total=1000000)
        self.ledger.reserve(job_id, self.tasks[0], 0, quotes(42, 0)[0], 1000)
        self.ledger.status(job_id, "PAUSED_POLICY", "Paused during recovery")
        with self.assertRaisesRegex(PolicyError, "unresolved"):
            self.ledger.approve_mandate_increase(job_id, 1, 1250000, 1250000, 60000, 1000000,
                                                 "Operator", "Do not bypass payment recovery")

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

    def test_dashboard_limit_parser_uses_exact_decimal_micro_usd(self):
        self.assertEqual(usd_to_micros("1.25"), 1250000)
        self.assertEqual(usd_to_micros("0.010001"), 10001)
        with self.assertRaisesRegex(ValueError, "decimal USD strings"):
            usd_to_micros(1.25)
        with self.assertRaisesRegex(ValueError, "six decimals"):
            usd_to_micros("1.0000001")

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
        script = """import sys
from touchstone.ledger import Ledger
from touchstone.payments import MockRail
from touchstone.engine import Engine
e=Engine(Ledger(sys.argv[1]),MockRail(sys.argv[2]))
e.run(sys.argv[3],kill_at='after_rail')
"""
        result = subprocess.run([sys.executable,"-c",script,str(self.root/"ledger.sqlite"),str(self.root/"rail.sqlite"),self.run_id],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,86,result.stderr)
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

    def test_unknown_live_rail_outcome_keeps_reservation_and_pauses_job(self):
        job = self.job()
        quote = quotes(42, 0)[0]
        key = self.ledger.reserve(job, self.tasks[0], 0, quote, 1000)
        class UnknownRail:
            mode = "TESTNET"
            def lookup(self, key, quote=None):
                return None
            def receipts(self):
                return []
        engine = Engine(self.ledger, UnknownRail())
        self.assertEqual(engine.recover(self.run_id), 0)
        attempt = self.ledger.attempts(job)[0]
        self.assertEqual(attempt["key"], key)
        self.assertEqual(attempt["state"], "RESERVED")
        self.assertEqual(self.ledger.get_job(job)["status"], "PAUSED_RECOVERY")
        self.assertEqual(self.ledger.get_job(job)["spent"], 0)

    def test_engine_can_route_real_metal_tier_through_unified_rail(self):
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class MetalOffer:
            id: str = "metal-quote-1"
            provider: str = "metal-provider"
            price: int = 10000
            latency_ms: int = 0
            expires_at: float = time.time() + 60
            mode: str = "TESTNET"
            terms: dict = None
            def public(self):
                return {"id": self.id, "provider": self.provider, "price": self.price,
                        "latency_ms": self.latency_ms, "expires_at": self.expires_at,
                        "mode": self.mode, "terms": {"url": "http://127.0.0.1/inference/task"}}
        class MetalTier:
            mode = "TESTNET"
            def __init__(self):
                self.receipt = None
            def quote_for_task(self, task):
                return MetalOffer()
            def pay(self, key, quote, output_factory=None):
                self.receipt = {"key": key, "id": "metal-receipt-1", "amount": quote.price,
                                "provider": quote.provider, "quote_id": quote.id,
                                "output": self.truth}
                return self.receipt
            def lookup(self, key, quote=None):
                return self.receipt or {"state": "NOT_DISPATCHED", "authoritative": True}
            def recover(self, key, quote=None):
                return self.receipt
            def receipts(self):
                return [self.receipt] if self.receipt else []
        task = self.tasks[0]
        tier = MetalTier()
        tier.truth = self.truth[task.id]
        rails = CompositeRail(self.rail, tier)
        run = self.ledger.create_run([{"seed": 42, "policy": "metal-probe", "hold": 30000,
            "price_cap": 20000, "allocation": 30000, "tasks": [task.public()]}], 30000)
        snapshot = Engine(self.ledger, rails).run(run)
        self.assertEqual(snapshot["attempts"][0]["provider"], "metal-provider")
        self.assertTrue(snapshot["reconciliation"]["matched"])
        self.assertEqual(snapshot["jobs"][0]["status"], "COMPLETED")

    def test_engine_metal_quote_only_does_not_dispatch_or_create_a_run(self):
        from types import SimpleNamespace
        from touchstone import __main__ as cli

        class QuoteOnlyRail:
            def __init__(self, *args, **kwargs):
                self.quoted_task = None

            def quote_for_task(self, task):
                self.quoted_task = task
                return SimpleNamespace(provider="metal-provider", price=10000, latency_ms=250,
                                       queue_depth=1, latency_samples=0,
                                       expires_at=time.time() + 30, mode="TESTNET")

        argv = ["touchstone", "engine-metal", "--scope", "quote-check", "--steps", "1",
                "--budget-usd", "0.05", "--price-cap-usd", "0.05", "--provider-url",
                "http://127.0.0.1:8092", "--quote-only"]
        output = io.StringIO()
        with patch.object(sys, "argv", argv), patch("touchstone.payments.MetalEngineRail", QuoteOnlyRail), redirect_stdout(output):
            self.assertEqual(cli.main(), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["mode"], "LIVE_QUOTE_ONLY")
        self.assertEqual(report["payments_sent"], 0)
        self.assertEqual(report["quote"]["price_micro_usd"], 10000)

    def test_thompson_policy_is_seeded_and_respects_hard_caps(self):
        job = {"policy": "thompson", "price_cap": 30000, "budget": 40000, "spent": 0}
        first, _ = Router(seed=7).select(quotes(42, 0, chaos=False), self.tasks[0], job, [])
        second, _ = Router(seed=7).select(quotes(42, 0, chaos=False), self.tasks[0], job, [])
        self.assertEqual(first, second)
        self.assertLessEqual(first.price, job["price_cap"])

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

    def test_metal_quote_carries_live_queue_and_latency_observations(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {'METAL_PROVIDER_URL': 'http://127.0.0.1:8092', 'METAL_RPC_URL': 'http://127.0.0.1:8545'}):
            rail = MetalRail('queue-metadata-test', 'http://127.0.0.1:8092', transport=lambda request: {
                'url': 'http://127.0.0.1:8092/inference/task', 'expires_at': (time.time() + 30) * 1000,
                'offer': {'amount': str(12000 * 10**12)}, 'queue_depth': 2, 'latency_ms': 3000,
                'latency_samples': 4})
        quote = rail.quote('http://127.0.0.1:8092/inference/task')
        self.assertEqual(quote.price, 12000)
        self.assertEqual(quote.queue_depth, 2)
        self.assertEqual(quote.latency_ms, 3000)
        self.assertEqual(quote.latency_samples, 4)

    def test_metal_quote_failure_is_not_reported_as_uncertain_payment(self):
        from types import SimpleNamespace
        from touchstone.metal import PaymentPending
        with patch.dict('os.environ', {'METAL_PROVIDER_URL': 'http://127.0.0.1:8092',
                                       'METAL_RPC_URL': 'http://127.0.0.1:8545'}), \
             patch('touchstone.metal.node_executable', return_value='node'), \
             patch('touchstone.metal.subprocess.run', return_value=SimpleNamespace(
                 stdout='{"ok":false,"error":"provider unavailable"}', returncode=1)):
            rail = MetalRail('quote-error-test', 'http://127.0.0.1:8092')
            with self.assertRaisesRegex(RuntimeError, 'no purchase was dispatched') as error:
                rail.quote('http://127.0.0.1:8092/inference/task')
        self.assertNotIsInstance(error.exception, PaymentPending)


if __name__ == "__main__":
    unittest.main()
