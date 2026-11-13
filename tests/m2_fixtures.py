"""Durable controlled Metal adapter. Never connects to a wallet or service."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from touchstone.metal import MetalQuote, PaymentPending
from touchstone.payments import MockRail


class FixtureFactory:
    def __init__(self, directory, barrier=None, lose_deposit=False, pending_deposit=False):
        self.directory = Path(directory)
        self.barrier = barrier
        self.lose_deposit = lose_deposit
        self.pending_deposit = pending_deposit
        self.events = []

    def __call__(self, wallet, origin, cap, budget):
        return FixtureClient(self, wallet, origin)


class FixtureClient:
    def authorize_purchase(self, authorization):
        # Production ledger already checked a real ephemeral human signature.
        self.authorization = authorization
    mode = 'MOCK'

    def __init__(self, factory, wallet, origin):
        self.factory, self.wallet, self.provider_url = factory, wallet, origin
        self.rail = MockRail(factory.directory / (wallet + '.sqlite'))
        with self.rail.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS funds(amount INTEGER); CREATE TABLE IF NOT EXISTS terms(key TEXT PRIMARY KEY, value TEXT);')

    def balance(self):
        with self.rail.connect() as db:
            row = db.execute('SELECT amount FROM funds').fetchone()
        return {'account': self.wallet, 'spendable_base_units': str((row[0] if row else 0)*10**12),
                'historical_payments': len(self.rail.receipts()), 'pending_invoice': False, 'assurance': 'MOCK'}

    def deposit(self, amount):
        self.factory.events.append(('deposit', self.wallet))
        with self.rail.connect() as db:
            if db.execute('SELECT 1 FROM funds').fetchone():
                raise AssertionError('Duplicate controlled deposit')
            db.execute('INSERT INTO funds VALUES(?)', (0 if self.factory.pending_deposit else amount,))
        if self.factory.lose_deposit:
            raise PaymentPending('Controlled unknown deposit')

    def invoke(self, command):
        if command == 'funding-status':
            return {'usdz_balance_base_units': str(10**22), 'native_balance_base_units': '1'}
        assert command == 'receipts'
        with self.rail.connect() as db:
            rows = db.execute('SELECT key,value FROM terms').fetchall()
        return [{'key': row['key'], 'terms': json.loads(row['value']),
                 'receipt': self._result(row['key'])['receipt']} for row in rows if self._result(row['key'])]

    def quote(self, url):
        raw = {'url': url, 'provider_id': 'metal-provider', 'offer': {'amount': str(10000*10**12)},
               'expires_at': (time.time()+120)*1000}
        identity = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        return MetalQuote(identity, 'metal-provider', 10000, raw['expires_at']/1000, raw, mode='MOCK')

    def pay(self, key, quote):
        self.factory.events.append(('pay', self.wallet))
        if self.factory.barrier:
            self.factory.barrier.wait(timeout=10)
        with self.rail.connect() as db:
            db.execute('INSERT OR IGNORE INTO terms VALUES(?,?)', (key, json.dumps(quote.terms)))
        self.rail.pay(key, quote, lambda: {'total_cents': -1})  # deliberate quality failure
        return self._result(key)

    def _result(self, key):
        row = self.rail.lookup(key)
        if row['state'] != 'PAID':
            return None
        return {'state': 'DELIVERED', 'receipt': {'id': row['id'], 'invoice': {'amount': str(row['amount']*10**12)}},
                'output': {'body': {'output': row['output']}}}

    def lookup(self, key):
        result = self._result(key)
        return {'state': 'DELIVERED', 'result': result} if result else {'state': 'NOT_DISPATCHED'}

    def recover(self, key, quote=None):
        return self._result(key)
