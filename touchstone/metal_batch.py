"""Integration probes: serial wallet funding, concurrent per-job engine workers.

No Airwallex writes, automatic top-ups or withdrawals. Uncertain deposits stop
the batch and are checked for spendability without repeating the deposit.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re

from .engine import Engine
from .ledger import Ledger, PolicyError, canonical
from .leases import exclusive
from .metal import MetalRail, PaymentPending, task_resource_url
from .payments import MetalEngineRail
from .workload import generate


class MetalBatch:
    def __init__(self, directory, client_factory=MetalRail, funding_lock=None):
        self.directory = Path(directory)
        self.ledger = Ledger(self.directory / 'ledger.sqlite')
        self.client_factory = client_factory
        self.funding_lock = funding_lock
        with self.ledger.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS metal_batches(scope TEXT PRIMARY KEY, terms TEXT NOT NULL, run_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS metal_batch_wallets(
                    scope TEXT NOT NULL, job_id TEXT PRIMARY KEY, wallet TEXT UNIQUE NOT NULL,
                    phase TEXT NOT NULL, account TEXT);
            ''')

    def prepare(self, scope, origin, jobs, steps, budget, cap, aggregate, seed=42):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,36}', scope):
            raise ValueError('Batch scope must be 1-36 letters, digits, underscores or hyphens')
        if any(type(x) is not int or x <= 0 for x in (jobs, steps, budget, cap, aggregate)):
            raise ValueError('Positive integer job counts and micro-unit limits required')
        if jobs > 3 or steps > 50 or cap > budget or jobs * budget > aggregate:
            raise ValueError('Require 1-3 jobs, 1-50 steps and allocations within the aggregate cap')
        tasks = [generate(seed + n, steps)[0] for n in range(jobs)]
        task_resource_url(origin, tasks[0][0])  # reject credentials/unsafe origins before persisting
        terms = dict(origin=origin, jobs=jobs, steps=steps, budget=budget, cap=cap,
                     aggregate=aggregate, seed=seed, purpose='INTEGRATION_PROBE')
        with exclusive(self.directory / (scope + '.owner.sqlite')):
            with self.ledger.connect() as db:
                prior = db.execute('SELECT terms FROM metal_batches WHERE scope=?', (scope,)).fetchone()
            if prior:
                if prior['terms'] != canonical(terms):
                    raise ValueError('Batch scope is bound to different terms')
                return self.report(scope)
            run = self.ledger.create_run([dict(seed=seed+n, policy='metal-probe', hold=budget,
                allocation=budget, price_cap=cap, tasks=[t.public() for t in tasks[n]]) for n in range(jobs)], jobs*budget, float_mode='TESTNET')
            with self.ledger.tx() as db:
                db.execute('INSERT INTO metal_batches VALUES(?,?,?)', (scope, canonical(terms), run))
                for n, job in enumerate(self.ledger.jobs(run)):
                    db.execute('INSERT INTO metal_batch_wallets VALUES(?,?,?,?,NULL)',
                               (scope, job['id'], scope + '-j' + str(n+1), 'UNFUNDED'))
                self.ledger._event(db, 'METAL_BATCH_PREPARED', {'scope': scope, 'run_id': run, 'terms': terms,
                    'label': 'SIMULATED', 'note': 'Local mandates only; no customer authorization'})
        return self.report(scope)

    def _read(self, scope):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,36}', scope):
            raise ValueError('Invalid batch scope')
        with self.ledger.connect() as db:
            batch = db.execute('SELECT * FROM metal_batches WHERE scope=?', (scope,)).fetchone()
            if not batch:
                raise ValueError('Prepare this batch first')
            wallets = [dict(row) for row in db.execute('SELECT * FROM metal_batch_wallets WHERE scope=? ORDER BY job_id', (scope,))]
        return dict(batch), json.loads(batch['terms']), wallets

    def _state(self, wallet, phase, account=None):
        with self.ledger.tx() as db:
            db.execute('UPDATE metal_batch_wallets SET phase=?,account=COALESCE(?,account) WHERE job_id=?',
                       (phase, account, wallet['job_id']))
            self.ledger._event(db, 'METAL_WALLET_' + phase, {'scope': wallet['scope'], 'wallet': wallet['wallet'],
                'job_id': wallet['job_id'], 'account': account})

    def _client(self, wallet, terms):
        if self.client_factory is MetalRail:
            return MetalRail(wallet['wallet'], terms['origin'], terms['cap'], terms['budget'], execute=True)
        return self.client_factory(wallet['wallet'], terms['origin'], terms['cap'], terms['budget'])

    def fund(self, scope, execute=False):
        if not execute:
            return {**self.report(scope), 'requires_explicit_execute': True, 'writes_performed': False}
        if self.funding_lock is None:
            raise ValueError('A shared funding-account lock is required')
        self._read(scope)
        with exclusive(self.directory / (scope + '.owner.sqlite')), exclusive(self.funding_lock):
            _, terms, wallets = self._read(scope)
            for wallet in wallets:
                if wallet['phase'] == 'FUNDED':
                    continue
                client = self._client(wallet, terms)
                try:
                    balance = client.balance()
                    if balance.get('historical_payments', 0) or balance.get('pending_invoice', False):
                        raise PolicyError('Wallet has prior payments outside this unfunded mandate')
                    account = balance['account']
                    if wallet['account'] and account != wallet['account']:
                        raise PolicyError('Clearing wallet identity changed')
                    with self.ledger.connect() as db:
                        duplicate = db.execute('SELECT 1 FROM metal_batch_wallets WHERE account=? AND job_id<>?',
                                               (account, wallet['job_id'])).fetchone()
                    if duplicate:
                        raise PolicyError('Jobs must have distinct clearing wallets')
                    if int(balance['spendable_base_units']) < terms['budget'] * 10**12:
                        if wallet['phase'] != 'UNFUNDED':
                            return self.report(scope)  # uncertain/pending: never deposit again
                        funding = client.invoke('funding-status')
                        if int(funding['usdz_balance_base_units']) < terms['budget'] * 10**12 or int(funding['native_balance_base_units']) <= 0:
                            return {**self.report(scope), 'blocker': 'FAUCET_FUNDING_REQUIRED'}
                        self._state(wallet, 'DEPOSIT_DISPATCHING', account)
                        client.deposit(terms['budget'])
                        balance = client.balance()
                        if balance['account'] != account:
                            raise PolicyError('Clearing wallet identity changed after deposit')
                        if int(balance['spendable_base_units']) < terms['budget'] * 10**12:
                            self._state(wallet, 'AWAITING_SPENDABLE', account)
                            return self.report(scope)
                    self._state(wallet, 'FUNDED', account)
                except PaymentPending:
                    return {**self.report(scope), 'blocker': 'FUNDING_OUTCOME_UNKNOWN'}
        return self.report(scope)

    def run(self, scope, execute=False, recover=False, kill_at=None):
        if not execute:
            raise ValueError('Metal execution/recovery requires --execute and a written testnet cap')
        self._read(scope)
        with exclusive(self.directory / (scope + '.owner.sqlite')):
            batch, terms, wallets = self._read(scope)
            if any(w['phase'] != 'FUNDED' for w in wallets):
                raise PolicyError('All wallets must be confirmed funded before concurrent execution')
            if kill_at and (recover or len(wallets) != 1):
                raise ValueError('Kill proof requires one job and cannot be combined with recovery')
            def work(wallet):
                client = self._client(wallet, terms)
                rail = MetalEngineRail(wallet['wallet'], terms['origin'], terms['cap'], terms['budget'], client=client)
                engine = Engine(self.ledger, rail)
                if recover:
                    engine.recover(batch['run_id'], wallet['job_id'])
                else:
                    engine.run(batch['run_id'], job_id=wallet['job_id'], kill_at=kill_at)
                return engine.snapshot(batch['run_id'], wallet['job_id'])
            with ThreadPoolExecutor(max_workers=len(wallets)) as pool:
                results = list(pool.map(work, wallets))
        report = self.report(scope)
        report['jobs'] = results
        report['receipts_reconciled'] = all(j['reconciliation']['matched'] for j in results)
        report['label'] = 'MEASURED' if self.client_factory is MetalRail else 'MOCK'
        report['financial_evidence'] = 'TESTNET' if self.client_factory is MetalRail else 'MOCK'
        report['audit'] = self.ledger.audit()
        return report

    def report(self, scope):
        batch, terms, wallets = self._read(scope)
        attempts = [a for w in wallets for a in self.ledger.attempts(w['job_id'])]
        return {'label': 'BLOCKED', 'scope': scope, 'run_id': batch['run_id'], 'terms': terms,
            'wallets': wallets, 'funded': all(w['phase'] == 'FUNDED' for w in wallets),
            'paid_attempts': [{'key': a['key'], 'job_id': a['job_id'], 'receipt': a['receipt'],
                               'price': a['price'], 'state': a['state'], 'mandate_version': a['mandate_version']}
                              for a in attempts if a['receipt']],
            'pending_attempts': sum(a['state'] in {'RESERVED', 'DISPATCHING', 'PAID'} for a in attempts),
            'customer_mandates': 'SIMULATED', 'customer_captured': 0, 'automatic_withdrawals': False,
            'verification_fees': 'SIMULATED internal charge; not a paid external check',
            'audit': self.ledger.audit(), 'live_gate': 'Requires written testnet cap, provider and funded wallets'}
