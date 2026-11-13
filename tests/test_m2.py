from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from m2_fixtures import FixtureFactory
import test_banked
from touchstone.engine import Engine
from touchstone.ledger import Ledger, PolicyError
from touchstone.leases import LeaseBusy
from touchstone.metal_batch import MetalBatch
from touchstone.payments import MockRail
from touchstone.providers import quotes
from touchstone.workload import generate


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = Ledger(self.root/'ledger.sqlite')
        self.tasks, _ = generate(42, 3)
        self.run_id = self.ledger.create_run([dict(seed=42, policy='touchstone', hold=40000,
            price_cap=10000, allocation=40000, tasks=[t.public() for t in self.tasks])], 40000)
        self.job = self.ledger.jobs(self.run_id)[0]['id']
        self.offer = quotes(42, 0)[0]

    def reserve(self, n=0):
        return self.ledger.reserve(self.job, self.tasks[n], 0, self.offer, 1000, expected_version=1)

    def test_dispatch_version_is_bound_and_rechecked_atomically(self):
        key = self.reserve()
        with self.ledger.tx() as db:
            db.execute('UPDATE jobs SET mandate_version=2 WHERE id=?', (self.job,))
        with self.assertRaisesRegex(PolicyError, 'version'):
            self.ledger.assert_can_pay(key)
        with self.assertRaisesRegex(PolicyError, 'version'):
            self.reserve(1)
        self.assertEqual(self.ledger.attempts(self.job)[0]['state'], 'RESERVED')
        self.assertFalse(any(e['kind']=='DISPATCHING' for e in self.ledger.events()))

    def test_contended_dispatch_is_authorized_once_and_hold_remains_reserved(self):
        key = self.reserve()
        def dispatch(_):
            try:
                self.ledger.assert_can_pay(key)
                return True
            except PolicyError:
                return False
        with ThreadPoolExecutor(4) as pool:
            self.assertEqual(sum(pool.map(dispatch, range(4))), 1)
        self.assertEqual(self.ledger.attempts(self.job)[0]['state'], 'DISPATCHING')
        with self.assertRaises(PolicyError):
            self.ledger.settle_job(self.job)
        with self.assertRaises(PolicyError):
            self.ledger.void(key, 'unproven')
        snap = Engine(self.ledger, MockRail(self.root/'rail.sqlite')).snapshot(self.run_id)
        self.assertEqual(snap['jobs'][0]['reserved'], 11000)
        self.assertEqual(snap['reconciliation']['pending'], 1)

    def test_lease_blocks_competing_worker_and_fences_old_owner(self):
        key = self.reserve()
        with self.ledger.worker(self.job) as old:
            with self.assertRaises(LeaseBusy):
                with self.ledger.worker(self.job):
                    self.fail('Two owners')
            with self.assertRaises(PolicyError):
                self.ledger.assert_can_pay(key, 'other-owner')
        with self.ledger.worker(self.job) as current:
            with self.assertRaises(PolicyError):
                self.ledger.assert_can_pay(key, old)
            self.ledger.assert_can_pay(key, current)
        self.assertTrue(self.ledger.audit()['valid'])

    def test_other_process_cannot_recover_a_job_owned_by_a_live_worker(self):
        script = '''import sys
from touchstone.ledger import Ledger
from touchstone.leases import LeaseBusy
try:
    with Ledger(sys.argv[1]).worker(sys.argv[2]):
        raise SystemExit(3)
except LeaseBusy:
    raise SystemExit(17)
'''
        with self.ledger.worker(self.job):
            child = subprocess.run([sys.executable, '-c', script, self.ledger.path, self.job], capture_output=True, timeout=30)
        self.assertEqual(child.returncode, 17)

    def test_halt_wins_before_barrier_but_does_not_erase_dispatched_obligation(self):
        key = self.reserve()
        self.ledger.halt()
        with self.assertRaises(PolicyError):
            self.ledger.assert_can_pay(key)
        self.ledger.resume()
        self.ledger.assert_can_pay(key)
        self.ledger.halt()
        rail = MockRail(self.root/'rail.sqlite')
        receipt = rail.pay(key, self.offer, lambda: {'total_cents': -1})
        self.ledger.record_paid(key, receipt)
        self.assertEqual(self.ledger.get_job(self.job)['rail_spent'], 10000)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        from signed_fixture import signed_fixtures
        signed_fixtures(self, self.root)
        self.factory = FixtureFactory(self.root/'remote')
        self.batch = MetalBatch(self.root/'batch', self.factory, self.root/'funding-owner.sqlite')

    def prepare(self, jobs=3):
        return self.batch.prepare('probe', 'http://127.0.0.1:8092', jobs, 2, 40000, 10000, 120000)

    def test_serial_funding_precedes_concurrent_jobs_and_repeat_does_not_pay(self):
        self.prepare()
        self.assertFalse(self.batch.fund('probe')['writes_performed'])
        with self.assertRaises(ValueError):
            self.batch.run('probe')
        with self.assertRaises(PolicyError):
            self.batch.run('probe', execute=True)
        funded = self.batch.fund('probe', execute=True)
        self.assertTrue(funded['funded'])
        self.assertEqual(len({w['account'] for w in funded['wallets']}), 3)
        self.factory.barrier = threading.Barrier(3)
        report = self.batch.run('probe', execute=True)
        self.assertEqual(self.factory.events[:3], [('deposit', 'probe-j1'), ('deposit', 'probe-j2'), ('deposit', 'probe-j3')])
        self.assertEqual(len(report['paid_attempts']), 6)
        self.assertEqual(len({a['receipt'] for a in report['paid_attempts']}), 6)
        self.assertTrue(report['receipts_reconciled'])
        self.assertEqual(report['pending_attempts'], 0)
        before = list(self.factory.events)
        self.batch.run('probe', execute=True, recover=True)
        self.batch.run('probe', execute=True)
        self.batch.fund('probe', execute=True)
        self.assertEqual(self.factory.events, before)

    def test_unknown_deposit_is_not_retried_and_blocks_later_wallets(self):
        self.prepare()
        self.factory.lose_deposit = self.factory.pending_deposit = True
        for _ in range(2):
            self.assertFalse(self.batch.fund('probe', execute=True)['funded'])
        self.assertEqual(self.factory.events, [('deposit', 'probe-j1')])
        with self.assertRaises(PolicyError):
            self.batch.run('probe', execute=True)

    def test_caps_and_changed_terms_fail_before_remote_calls(self):
        with self.assertRaises(ValueError):
            self.batch.prepare('probe', 'http://127.0.0.1:8092', 3, 2, 40000, 10000, 119999)
        self.prepare()
        with self.assertRaises(ValueError):
            self.batch.prepare('probe', 'http://127.0.0.1:8092', 3, 3, 40000, 10000, 120000)
        self.assertEqual(self.factory.events, [])

    def test_process_kill_after_metal_adapter_receipt_recovers_without_second_payment(self):
        self.prepare(1)
        self.batch.fund('probe', execute=True)
        script = '''import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()/'tests'))
from m2_fixtures import FixtureFactory
from touchstone.metal_batch import MetalBatch
root=Path(sys.argv[1])
import unittest
from signed_fixture import signed_fixtures
signed_fixtures(unittest.TestCase(),root)
MetalBatch(root/'batch', FixtureFactory(root/'remote'), root/'funding-owner.sqlite').run('probe',execute=True,kill_at='after_rail')
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.root)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 86, result.stderr)
        attempts = self.batch.ledger.attempts()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]['state'], 'DISPATCHING')
        report = self.batch.run('probe', execute=True, recover=True)
        self.assertEqual(len(report['paid_attempts']), 1)
        self.assertEqual(report['pending_attempts'], 0)
        self.assertTrue(report['receipts_reconciled'])
        again = self.batch.run('probe', execute=True, recover=True)
        self.assertEqual(again['paid_attempts'], report['paid_attempts'])
        self.assertFalse(any(e[0]=='pay' for e in self.factory.events))


class ExecuteTests(unittest.TestCase):
    def test_money_commands_refuse_before_loading_private_config(self):
        from touchstone.__main__ import main
        cases = [ ['engine-metal', '--scope', 'x', '--budget-usd', '.04', '--price-cap-usd', '.01', '--recover'],
                  ['metal-batch', 'run', '--scope', 'x', '--integration-probe'] ]
        for args in cases:
            with self.subTest(args=args), patch('sys.argv', ['touchstone', *args]), \
                 patch('touchstone.config.load_local', side_effect=AssertionError('Config read')), \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(), 1)

    def test_adapter_default_cannot_dispatch_money_even_with_a_transport(self):
        from touchstone.metal import MetalRail
        with patch('touchstone.metal.load_local'), patch.dict('os.environ', {'METAL_RPC_URL': 'fixture'}):
            rail = MetalRail('fixture', 'http://127.0.0.1:8092', transport=lambda _: self.fail('Dispatched'))
            for command in ('pay', 'deposit', 'withdraw', 'recover'):
                with self.subTest(command=command), self.assertRaises(ValueError):
                    rail.invoke(command)

    def test_recovery_uses_original_quote_resource(self):
        from touchstone.payments import MetalEngineRail
        from unittest.mock import Mock
        client = Mock()
        client.recover.return_value = {'state': 'UNKNOWN'}
        rail = MetalEngineRail('fixture', 'http://127.0.0.1:8092', client=client)
        quote = {'terms': {'url': 'http://127.0.0.1:8092/inference/original'}}
        rail.recover('original-reservation', quote)
        client.recover.assert_called_once_with('original-reservation', quote)


class TestnetFloatTests(unittest.TestCase):
    def test_testnet_float_cannot_top_up_or_return_without_an_actual_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory)/'ledger.sqlite')
            rail = MockRail(Path(directory)/'remote.sqlite')
            tasks, _ = generate(42, 3)
            run = ledger.create_run([dict(seed=42, policy='metal-probe', hold=100000,
                allocation=20000, price_cap=10000, tasks=[t.public() for t in tasks])], 100000, float_mode='TESTNET')
            job = ledger.jobs(run)[0]['id']
            quote = quotes(42, 0)[0]
            for task in tasks[:1]:
                key = ledger.reserve(job, task, 0, quote, 1000)
                receipt = rail.pay(key, quote, lambda: {'total_cents': -1})
                ledger.record_paid(key, receipt)
                ledger.finish_attempt(key, receipt['output'], {'passed': False, 'score': 0, 'reason': 'MOCK'})
            unused_reservation = ledger.reserve(job, tasks[1], 0, quote, 1000)
            with self.assertRaisesRegex(PolicyError, 'allocation exhausted'):
                ledger.reserve(job, tasks[2], 0, quote, 1000)
            ledger.void(unused_reservation, 'Controlled purchase never dispatched')
            ledger.settle_job(job)
            self.assertEqual(ledger.get_job(job)['allocation'], 20000)
            close = ledger.events()[-1]['payload']
            self.assertEqual(close['unused_float_returned'], 0)
            self.assertEqual(close['unused_float_pending'], 10000)
            self.assertEqual(close['float_mode'], 'TESTNET')


class SubCentRelease(unittest.TestCase):
    def test_subcent_provider_charge_releases_hold_without_capture(self):
        fixture = test_banked.BankedJobs()
        fixture.setUp()
        try:
            fixture.rail.price = 5000
            fixture.rail.withdrawal['claimed'][0]['amount'] = str(95000*10**12)
            report = fixture.run_job()
            self.assertEqual(report['captured_micro_usd'], 0)
            self.assertEqual(report['merchant_rounding_micro_usd'], 5000)
            self.assertEqual(report['unused_authorization_micro_usd'], 1000000)
            self.assertFalse(any(c[0]=='POST' and c[1].endswith('/capture') for c in fixture.bank.calls))
            self.assertEqual(sum(c[0]=='POST' and c[1].endswith('/cancel') for c in fixture.bank.calls), 1)
            fixture.run_job(recover=True)
            self.assertEqual(fixture.rail.payments, 1)
        finally:
            fixture.doCleanups()
