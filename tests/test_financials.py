from pathlib import Path
import sqlite3
import tempfile
import unittest
from touchstone.engine import Engine
from touchstone.ledger import Ledger,PolicyError
from touchstone.payments import MockRail
from touchstone.providers import quotes
from touchstone.workload import generate


class FinancialTests(unittest.TestCase):
    def test_failed_call_cost_stays_spent_but_contract_decides_customer_capture(self):
        for policy,expected in [('CUSTOMER_PAYS',11000),('MERCHANT_ABSORBS',0)]:
            with self.subTest(policy=policy),tempfile.TemporaryDirectory() as directory:
                ledger=Ledger(Path(directory)/'ledger.sqlite');rail=MockRail(Path(directory)/'rail.sqlite')
                engine=Engine(ledger,rail);tasks,_=generate(42,1)
                run=ledger.create_run([dict(seed=42,policy='touchstone',hold=20000,allocation=20000,price_cap=10000,tasks=[tasks[0].public()])],20000,failed_call_policy=policy)
                job=ledger.jobs(run)[0]['id'];q=quotes(42,0)[0]
                key=ledger.reserve(job,tasks[0],0,q,1000)
                receipt=rail.pay(key,q,lambda:{'total_cents':-1})
                ledger.record_paid(key,receipt);ledger.finish_attempt(key,receipt['output'],{'passed':False,'score':0,'reason':'MOCK'})
                ledger.settle_job(job);ledger.settle_job(job)
                current=ledger.get_job(job)
                self.assertEqual(current['spent'],11000);self.assertEqual(current['rail_spent'],10000)
                self.assertEqual(current['captured'],expected);self.assertEqual(current['released'],20000-expected)
                pnl=engine.snapshot(run)['financials']['by_run'][0]
                self.assertEqual(pnl['provider_spend_micro_usd'],10000)
                self.assertEqual(pnl['absorbed_failures_micro_usd'],11000 if policy=='MERCHANT_ABSORBS' else 0)
                self.assertTrue(ledger.audit()['valid'])
                with ledger.connect() as db,self.assertRaises(sqlite3.IntegrityError):
                    db.execute("UPDATE runs SET failed_call_policy=? WHERE id=?",('CUSTOMER_PAYS' if policy=='MERCHANT_ABSORBS' else 'MERCHANT_ABSORBS',run))

    def test_unknown_payment_still_blocks_capture_under_merchant_absorption(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger=Ledger(Path(directory)/'ledger.sqlite');engine=Engine(ledger,MockRail(Path(directory)/'rail.sqlite'))
            run=engine.create_demo(count=1,failed_call_policy='MERCHANT_ABSORBS');job=ledger.jobs(run)[0]
            tasks,_=generate(42,1);ledger.reserve(job['id'],tasks[0],0,quotes(42,0)[0],1000)
            with self.assertRaises(PolicyError):ledger.settle_job(job['id'])

