"""Job-linked FX accounting. The demo USDZ entry never funds a real wallet."""
from decimal import Decimal
import json
import re

from .fx import execute_conversion, spend_report
from .ledger import canonical
from .treasury import _amount, _currency


def units(value):
    amount = _amount(value) * 1_000_000
    if amount != amount.to_integral_value():
        raise ValueError("Treasury accounting requires at most six decimal places")
    return int(amount)


def validate_cap(quote, currency, maximum):
    if currency != quote.get('sell_currency') or units(quote.get('sell_amount')) > units(maximum):
        raise ValueError("FX quote exceeds the approved sell-currency cap")


class TreasuryFunding:
    def __init__(self, store, client, journal):
        self.store, self.client, self.journal = store, client, journal
        with store.ledger.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS treasury_jobs(
                    scope TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, terms TEXT NOT NULL, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS treasury_entries(
                    scope TEXT NOT NULL, account TEXT NOT NULL, currency TEXT NOT NULL,
                    amount_microunits INTEGER NOT NULL, conversion_id TEXT NOT NULL, label TEXT NOT NULL,
                    PRIMARY KEY(scope,account), UNIQUE(account,conversion_id));
                CREATE TRIGGER IF NOT EXISTS treasury_entries_no_update BEFORE UPDATE ON treasury_entries
                    BEGIN SELECT RAISE(ABORT,'treasury entries are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS treasury_entries_no_delete BEFORE DELETE ON treasury_entries
                    BEGIN SELECT RAISE(ABORT,'treasury entries are append-only'); END;
            ''')

    def prepare(self, scope, request_id, quote, budget_currency, budget_amount, demo_rate):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', scope) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', request_id):
            raise ValueError("Valid job scope and unique conversion request ID required")
        _currency(budget_currency)
        validate_cap(quote, budget_currency, budget_amount)
        _currency(quote['buy_currency'])
        units(quote['buy_amount'])
        rate = _amount(demo_rate)
        if rate > 100:
            raise ValueError("Demo rate must be at most 100 USDZ per bought currency unit")
        fields = ('quote_id', 'sell_currency', 'buy_currency', 'sell_amount', 'buy_amount',
                  'dealt_currency', 'conversion_date', 'valid_to_at', 'client_rate')
        safe_quote = {key: quote[key] for key in fields if key in quote}
        if not isinstance(safe_quote.get('quote_id'), str) or not safe_quote['quote_id']:
            raise ValueError("A saved FX quote is required")
        terms = {'quote': safe_quote, 'customer_budget_currency': budget_currency,
                 'customer_budget_microunits': units(budget_amount), 'demo_usdz_per_unit': str(rate)}
        state = {'label': 'BLOCKED', 'scope': scope, 'request_id': request_id, 'phase': 'QUOTED',
                 'customer_budget_label': 'SIMULATED', 'customer_authorization_verified': False,
                 'bank_and_token_balances_separate': True, 'metal_funded': False, 'accounts': []}
        with self.store.ledger.tx() as db:
            prior = db.execute('SELECT * FROM treasury_jobs WHERE scope=? OR request_id=?', (scope, request_id)).fetchone()
            if prior:
                if prior['scope'] != scope or prior['request_id'] != request_id or prior['terms'] != canonical(terms):
                    raise ValueError("Treasury scope/request ID is bound to different terms")
                return self.report(scope)
            if db.execute('SELECT 1 FROM banked_jobs WHERE scope=?', (scope,)).fetchone():
                raise ValueError("Treasury must be prepared before the banked job starts")
            db.execute('INSERT INTO treasury_jobs VALUES(?,?,?,?)', (scope, request_id, canonical(terms), canonical(state)))
            self.store.ledger._event(db, 'TREASURY_QUOTED', {**state, 'terms': terms})
        return self.report(scope)

    def record(self, scope, phase, **values):
        with self.store.ledger.tx() as db:
            row = db.execute('SELECT state FROM treasury_jobs WHERE scope=?', (scope,)).fetchone()
            if not row:
                raise ValueError("Prepare the treasury job first")
            current = json.loads(row[0])
            if current['phase'] == 'RECONCILED':
                return
            state = {**current, 'phase': phase, **values}
            db.execute('UPDATE treasury_jobs SET state=? WHERE scope=?', (canonical(state), scope))
            self.store.ledger._event(db, 'TREASURY_' + phase, state)

    def execute(self, scope, execute=False, sell_currency=None, max_sell_amount=None):
        report = self.report(scope)
        if not execute:
            return {**report, 'requires_explicit_execute': True, 'writes_performed': False}
        terms = report['terms']
        validate_cap(terms['quote'], sell_currency, max_sell_amount)
        if report['phase'] == 'RECONCILED':
            return report
        self.record(scope, 'CONVERSION_PENDING')
        # A persisted request ID can only reconcile, never create another conversion.
        execute_conversion(self.client, self.journal, terms['quote'], report['request_id'])
        return self.reconcile(scope)

    def reconcile(self, scope):
        report = self.report(scope)
        if report['phase'] == 'RECONCILED':
            return report
        result = spend_report(self.client, self.journal, report['request_id'])
        if result['reconciliation'] != 'MATCHED_WALLET_HISTORY':
            self.record(scope, 'AWAITING_WALLET_HISTORY', reconciliation=result['reconciliation'])
            return self.report(scope)
        conversion = result['conversion']
        quote = report['terms']['quote']
        if (conversion['request_id'] != report['request_id'] or conversion['quote_id'] != quote['quote_id']
            or conversion['sell_currency'] != quote['sell_currency'] or conversion['buy_currency'] != quote['buy_currency']
            or units(conversion['sell_amount']) != units(quote['sell_amount'])
            or units(conversion['buy_amount']) != units(quote['buy_amount'])):
            raise ValueError("Reconciled FX operation differs from the job mandate")
        conversion_id = conversion['conversion_id']
        if not isinstance(conversion_id, str) or not conversion_id:
            raise ValueError("Missing conversion ID")
        label = getattr(self.client, 'evidence_label', 'MOCK')
        if label not in {'MEASURED', 'MOCK'}:
            raise ValueError("Unsupported adapter evidence label")
        demo = Decimal(str(conversion['buy_amount'])) * Decimal(report['terms']['demo_usdz_per_unit']) * 1_000_000
        if demo != demo.to_integral_value():
            raise ValueError("Demo rate produces fractional micro-units; choose an exact rate")
        entries = [
            {'account': 'AIRWALLEX_SELL', 'currency': conversion['sell_currency'],
             'amount_microunits': -units(conversion['sell_amount']), 'label': label},
            {'account': 'AIRWALLEX_TREASURY_FLOAT', 'currency': conversion['buy_currency'],
             'amount_microunits': units(conversion['buy_amount']), 'label': label},
            {'account': 'METAL_DEMO_FLOAT', 'currency': 'USDZ',
             'amount_microunits': int(demo), 'label': 'SIMULATED'},
        ]
        with self.store.ledger.tx() as db:
            current = json.loads(db.execute('SELECT state FROM treasury_jobs WHERE scope=?', (scope,)).fetchone()[0])
            if current['phase'] == 'RECONCILED':
                return self.report(scope)
            for entry in entries:
                db.execute('INSERT INTO treasury_entries VALUES(?,?,?,?,?,?)',
                           (scope, entry['account'], entry['currency'], entry['amount_microunits'], conversion_id, entry['label']))
            state = {**current, 'label': label, 'phase': 'RECONCILED', 'conversion_id': conversion_id,
                     'accounts': entries, 'wallet_history': result['balance_history'],
                     'reconciliation': result['reconciliation'],
                     'demo_rate_label': 'SIMULATED', 'metal_funded': False,
                     'note': 'Demo rate is accounting only; actual Metal spend requires a separately funded wallet'}
            db.execute('UPDATE treasury_jobs SET state=? WHERE scope=?', (canonical(state), scope))
            self.store.ledger._event(db, 'TREASURY_RECONCILED', state)
        return self.report(scope)

    def report(self, scope):
        with self.store.ledger.connect() as db:
            row = db.execute('SELECT * FROM treasury_jobs WHERE scope=?', (scope,)).fetchone()
        if not row:
            raise ValueError("Unknown treasury job scope")
        return {**json.loads(row['state']), 'terms': json.loads(row['terms']), 'audit': self.store.ledger.audit()}


def read_treasury_jobs(ledger):
    with ledger.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='treasury_jobs'").fetchone():
            return []
        return [{**json.loads(row['state']), 'terms': json.loads(row['terms'])}
                for row in db.execute('SELECT * FROM treasury_jobs ORDER BY rowid DESC')]
