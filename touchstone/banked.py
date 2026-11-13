"""One recoverable sandbox/testnet job, with real adapters behind one journal.

The integration-probe purpose is explicit: it tests the financial protocol, not
model eligibility or savings. Autonomous model procurement remains gated.
"""
import base64
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlparse

from .holds import OutcomeUnknown, CreateRejected, ScopeRetired
from .ledger import Ledger, PolicyError, canonical
from .metal import MetalQuote, PaymentPending
from .verifier import check


def resource_url(base, task):
    parsed = urlparse(base)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("Use the provider origin without a path or query")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}):
        raise ValueError("Provider origin must be HTTPS or loopback HTTP")
    public = canonical(task.public()).encode()
    if len(public) > 12000:
        raise ValueError("Integration probe task is too large")
    return base.rstrip('/') + '/inference/' + hashlib.sha256(public).hexdigest() + '?task=' + base64.urlsafe_b64encode(public).decode().rstrip('=')


class BankedStore:
    def __init__(self, path, owner_path=None):
        self.ledger = Ledger(path)
        self.path = Path(path)
        self.owner_path = Path(owner_path) if owner_path else Path(str(self.path) + '.owner.sqlite')
        with self.ledger.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS banked_jobs(scope TEXT PRIMARY KEY, mandate TEXT NOT NULL, state TEXT NOT NULL)")

    @contextmanager
    def owner(self):
        # Serializes funded test jobs sharing the EVM funding account. This
        # avoids cross-process nonce and shared-balance allocation races.
        self.owner_path.parent.mkdir(parents=True, exist_ok=True)
        lock = sqlite3.connect(self.owner_path, timeout=.2)
        try:
            lock.execute('PRAGMA locking_mode=EXCLUSIVE')
            lock.execute('BEGIN EXCLUSIVE')
            lock.execute('CREATE TABLE IF NOT EXISTS owner(id INTEGER)')
        except sqlite3.OperationalError:
            lock.close()
            raise RuntimeError("Another banked job owns the funding account; retry after it finishes") from None
        try:
            yield
        finally:
            lock.rollback()
            lock.close()

    def bind(self, scope, mandate):
        with self.ledger.tx() as db:
            row = db.execute('SELECT * FROM banked_jobs WHERE scope=?', (scope,)).fetchone()
            if row:
                if row['mandate'] != canonical(mandate):
                    raise ValueError("Scope is already bound to different job terms; refusing a changed retry")
                return json.loads(row['state'])
            state = {"scope": scope, "phase": "CREATED", "mode": "SANDBOX_TESTNET", "purpose": "INTEGRATION_PROBE",
                     "spent_micro_usd": 0, "captured_micro_usd": 0, "checking_fee_micro_usd": 0,
                     "float_returned_confirmed": False, "customer_closed": False,
                     "mandate_expires_at": time.time()+3600, "confirmed_claims": {}}
            db.execute('INSERT INTO banked_jobs VALUES(?,?,?)', (scope, canonical(mandate), canonical(state)))
            self.ledger._event(db, 'BANKED_JOB_APPROVED', {"scope": scope, "mandate_digest": hashlib.sha256(canonical(mandate).encode()).hexdigest(), "mode": "SANDBOX_TESTNET"})
            return state

    def update(self, scope, state, **fields):
        state = {**state, **fields}
        with self.ledger.tx() as db:
            db.execute('UPDATE banked_jobs SET state=? WHERE scope=?', (canonical(state), scope))
            self.ledger._event(db, 'BANKED_' + state['phase'], {"scope": scope, "mode": "SANDBOX_TESTNET",
                "spent_micro_usd": state['spent_micro_usd'], "captured_micro_usd": state['captured_micro_usd']})
        return state

    def jobs(self):
        with self.ledger.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT state FROM banked_jobs ORDER BY rowid DESC')]

    def receipt(self, scope):
        """Portable journal receipt. Fiat and tokens are never summed or bridged."""
        with self.ledger.connect() as db:
            row=db.execute('SELECT mandate,state FROM banked_jobs WHERE scope=?',(scope,)).fetchone()
        if row is None:raise ValueError('Unknown integrated job scope')
        mandate,state=json.loads(row['mandate']),json.loads(row['state'])
        provider=state.get('receipt') or {}
        body=((state.get('result') or {}).get('output') or {}).get('body') or {}
        if not isinstance(body,dict):body={}
        from .study_costs import published_cost
        return {'version':1,'scope':scope,'mode':state['mode'],'phase':state['phase'],
            'assurance':'WORKFLOW_JOURNAL_NOT_INDEPENDENT_SETTLEMENT',
            'mandate_sha256':hashlib.sha256(canonical(mandate).encode()).hexdigest(),
            'task_sha256':hashlib.sha256(canonical(mandate['task']).encode()).hexdigest(),
            'qualification':mandate.get('qualification'),
            'fiat':{'currency':'USD','environment':'AIRWALLEX_SANDBOX',
                'authorization_id':(state.get('authorization') or {}).get('id'),
                'approved_micro_usd':mandate['hold'],'captured_micro_usd':state['captured_micro_usd'],
                'unused_authorization_micro_usd':state.get('unused_authorization_micro_usd'),
                'customer_closed':state['customer_closed'],'issuer_release_verified':False},
            'token':{'currency':'USDZ','chain_id':63825,'environment':'METAL_TESTNET',
                'provider_spend_micro_usdz':state['spent_micro_usd'],'receipt_id':provider.get('id'),
                'receipt_status':provider.get('status'),'onchain_payment_transaction_id':provider.get('transaction'),
                'unused_float_policy':mandate.get('unused_float_policy','RETURN_WHEN_CLAIMABLE'),
                'retained_float_base_units':state.get('retained_float_base_units'),
                'returned_float_micro_usdz':state.get('float_returned_micro_usd',0),
                'return_confirmed':state['float_returned_confirmed'],'final_settlement_verified':False},
            'provider_metadata':body.get('provider_metadata'),
            'hosted_api_credit_estimate':published_cost(body.get('provider_metadata')),
            'verification':state.get('verdict'),
            'reconciliation':state.get('reconciliation'),'audit':self.ledger.audit(),
            'bridge_or_fx_executed':False,'invoice_payment_authorized':False}

    def assert_dispatch(self):
        with self.ledger.connect() as db:
            if db.execute('SELECT halted FROM control').fetchone()[0]:
                raise PolicyError("Banked payment dispatches are halted")


class BankedWorkflow:
    def __init__(self, store, treasury, rail_factory):
        self.store, self.treasury, self.rail_factory = store, treasury, rail_factory

    def run(self, scope, task, origin, hold=1000000, allocation=100000, price_cap=50000, recover=False, integration_probe=False,
            treasury_request_id=None, allow_funding=True, return_float=True,
            qualification_profile=None, qualification_corpus=None):
        if not integration_probe:
            raise ValueError("This command requires --integration-probe; no model is approved for autonomous paid procurement")
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', scope):
            raise ValueError("Invalid scope")
        if any(type(v) is not int or v <= 0 for v in (hold, allocation, price_cap)) or not price_cap <= allocation <= hold <= 10000000 or hold % 10000:
            raise ValueError("Require positive cap <= allocation <= hold <= USD 10, with a whole-cent hold")
        if type(allow_funding) is not bool or type(return_float) is not bool:
            raise ValueError('Funding and unused-float policies must be explicit booleans')
        if not isinstance(task.id, str) or not isinstance(task.kind, str) or task.kind not in {'invoice','arithmetic','classification','invoice_extraction'}:
            raise ValueError("Unsupported probe task")
        url = resource_url(origin, task)
        mandate = {"task": task.public(), "provider_url": url, "hold": hold, "allocation": allocation,
                   "price_cap": price_cap, "purpose": "INTEGRATION_PROBE", "checking_fee": 0,
                   "fractional_cent_policy": "merchant absorbs; capture rounds down", "network": 63825}
        # Preserve immutable historical mandates when the legacy policy is used.
        if not allow_funding:mandate['funding_policy']='EXISTING_FLOAT_ONLY'
        if not return_float:mandate['unused_float_policy']='RETAIN_IN_ORIGINAL_WALLET'
        qualified_model=None
        if task.kind=='invoice_extraction':
            from .invoice_extraction import supported
            if not supported(task):raise ValueError('Unsupported invoice source; no authorization sent')
            if not qualification_profile or not qualification_corpus:
                raise ValueError('Invoice demonstration requires current measured qualification and its frozen corpus')
            from .invoice_corpus import load
            from .invoice_study import evaluate_profile
            manifest,records,truth=load(qualification_corpus,include_truth=True)
            raw=json.loads(Path(qualification_profile).read_text(encoding='utf-8'))
            result=evaluate_profile(records,truth,raw,dataset_version=manifest['dataset_version'],corpus_sha256=manifest['sources_sha256'])
            if not result['eligible'] or raw['label']!='MEASURED' or raw['tier']!='hosted-premium':
                raise ValueError('Invoice model did not pass the unchanged qualification gate')
            qualified_model=raw['model_id']
            mandate['qualification']={'profile_sha256':hashlib.sha256(canonical(raw).encode()).hexdigest(),
                                      'model_id':qualified_model,'corpus_sha256':manifest['sources_sha256']}
        from .treasury_job import read_treasury_jobs
        funding = next((job for job in read_treasury_jobs(self.store.ledger) if job['scope'] == scope), None)
        if funding and not treasury_request_id:
            raise ValueError("This scope has treasury funding; bind it with --treasury-request-id")
        if treasury_request_id:
            if not funding or funding['request_id'] != treasury_request_id or funding['phase'] != 'RECONCILED':
                raise ValueError("Job treasury funding must match a reconciled FX request")
            mandate['treasury_request_id'] = treasury_request_id
        with self.store.owner():
            state = self.store.bind(scope, mandate)
            if funding and 'treasury_funding' not in state:
                state = self.store.update(scope, state, treasury_funding=funding)
            if state['phase'] in {'COMPLETED','CLOSED_FLOAT_RETAINED'}:
                return state
            rail = self.rail_factory(scope, url, price_cap, allocation)
            try:
                if 'authorization' not in state:
                    authorization = self.treasury.authorize(scope, hold, recover)
                    if not authorization['ready']:
                        return self.store.update(scope, state, phase='AWAITING_AUTHORIZATION', authorization_status=authorization['intent'].get('status'))
                    state = self.store.update(scope, state, phase='AUTHORIZED', authorization=authorization['intent'])
                if 'funding' not in state:
                    balance = rail.balance()
                    if balance.get('historical_payments', 0) or balance.get('pending_invoice', False):
                        raise ValueError("Existing wallet history is outside this new banked mandate")
                    spendable = int(balance['spendable_base_units'])
                    if spendable < allocation * 10**12:
                        if not allow_funding:
                            return self.store.update(scope,state,phase='AWAITING_EXISTING_FLOAT',
                                funding_policy='NO_DEPOSIT_AUTHORIZED')
                        if state['phase'] in {'FUNDING', 'AWAITING_SPENDABLE_DEPOSIT'}:
                            return self.store.update(scope, state, phase='AWAITING_SPENDABLE_DEPOSIT')
                        status = rail.invoke('funding-status')
                        if int(status['usdz_balance_base_units']) < allocation * 10**12 or int(status['native_balance_base_units']) == 0:
                            return self.store.update(scope, state, phase='AWAITING_TESTNET_FUNDS', funding_address=status['address'])
                        state = self.store.update(scope, state, phase='FUNDING')
                        rail.deposit(allocation)
                        balance = rail.balance()
                        if int(balance['spendable_base_units']) < allocation * 10**12:
                            return self.store.update(scope, state, phase='AWAITING_SPENDABLE_DEPOSIT')
                    state = self.store.update(scope, state, phase='FUNDED', funding={"account": balance['account'],
                        "allocation_micro_usd": allocation, "assurance": balance['assurance'],
                        "starting_spendable_base_units":str(balance['spendable_base_units'])})
                if 'quote' not in state:
                    quote = rail.quote()
                    if quote.price > min(price_cap, allocation, hold):
                        raise ValueError("Provider quote exceeds the approved mandate")
                    reservation = hashlib.sha256((scope + ':' + quote.id).encode()).hexdigest()
                    state = self.store.update(scope, state, phase='RESERVED', quote=quote.public(), reservation=reservation,
                        recovery_required=False)
                quote = MetalQuote(**state['quote'])
                if 'receipt' not in state:
                    local = rail.lookup(state['reservation'])
                    if local['state'] in {'UNKNOWN','RESERVED'} and recover:
                        recovered = rail.recover(state['reservation'])
                        local = {'state': recovered['state'], 'result': recovered}
                    if local['state'] == 'UNPAID_CONFIRMED' and recover:
                        refreshed = rail.quote()
                        if refreshed.terms['offer'] != quote.terms['offer'] or refreshed.terms['url'] != quote.terms['url']:
                            raise ValueError('A retry cannot change the reserved seller or price')
                        state = self.store.update(scope, state, quote=refreshed.public())
                        quote = refreshed
                        local = {'state': 'NOT_DISPATCHED', 'result': None}
                    if local['state'] == 'NOT_DISPATCHED':
                        if time.time() >= state['mandate_expires_at'] or time.time() >= quote.expires_at:
                            return self.store.update(scope, state, phase='EXPIRED_BEFORE_PAYMENT')
                        authorization = None
                        if getattr(rail, 'mode', 'MOCK') == 'TESTNET':
                            from .procurement_approval import banked_terms, bind_dispatch, ApprovalError
                            # Persist the payer scope as part of this new quote;
                            # completed historical receipts never enter this path.
                            if not state['quote'].get('payer_scope'):
                                state = self.store.update(scope, state, quote={**state['quote'], 'payer_scope': scope})
                                quote = MetalQuote(**state['quote'])
                            try:
                                with self.store.ledger.connect() as db:
                                    terms = banked_terms(self.store.ledger, scope, db)
                                self.store.ledger.approvals.prepare(terms)
                                with self.store.ledger.tx() as db:
                                    if db.execute('SELECT halted FROM control').fetchone()[0]:
                                        raise PolicyError('Banked payment dispatches are halted')
                                    authorization = self.store.ledger.approvals.consume(db, state['reservation'], banked_terms(self.store.ledger, scope, db))
                                    state = {**state, 'phase': 'PAYMENT_DISPATCHING'}
                                    db.execute('UPDATE banked_jobs SET state=? WHERE scope=?', (canonical(state), scope))
                                    self.store.ledger._event(db, 'BANKED_PAYMENT_DISPATCHING', {'scope':scope,'purchase_key':state['reservation'],'approval_id':authorization['approval_id']})
                                bind_dispatch(rail, authorization)
                            except ApprovalError as error:
                                self.store.ledger.event('PROCUREMENT_APPROVAL_BLOCKED', {'purchase_key': state['reservation'], 'code': error.code})
                                return self.store.update(scope, state, phase='PAUSED_APPROVAL', approval_error=error.code)
                        self.treasury.refresh(scope, hold, state['authorization']['id'])
                        self.store.assert_dispatch()
                        state = self.store.update(scope, state, phase='PAYMENT_DISPATCHING')
                        result = rail.pay(state['reservation'], quote)
                    elif local['state'] in {'DELIVERED','PAID_OUTPUT_MISSING'}:
                        result = local['result']
                    else:
                        if not recover:
                            return self.store.update(scope, state, phase='PAYMENT_PENDING')
                        result = rail.recover(state['reservation'])
                    if result['state'] == 'UNPAID_CONFIRMED':
                        return self.store.update(scope, state, phase='UNPAID_RETRY_AVAILABLE')
                    receipt = result['receipt']
                    invoice = receipt['invoice']
                    offer = quote.terms['offer']
                    if (int(invoice['amount']) != quote.price*10**12 or invoice['network'] != 'eip155:63825'
                        or invoice['recipient'].lower() != offer['payTo'].lower()
                        or invoice['asset'].lower() != offer['asset'].lower()
                        or invoice['settlement'].lower() != offer['extra']['settlement'].lower()
                        or not invoice['id'].startswith(offer['extra']['invoicePrefix'] + ':')):
                        raise ValueError("Receipt does not match the reserved invoice")
                    state = self.store.update(scope, state, phase='PAID', receipt=receipt, spent_micro_usd=quote.price, result=result)
                if state['result']['state'] != 'DELIVERED':
                    if not recover:
                        return self.store.update(scope, state, phase='DELIVERY_PENDING')
                    result = rail.recover(state['reservation'])
                    if result['state'] != 'DELIVERED':
                        return self.store.update(scope, state, phase='DELIVERY_PENDING')
                    if result['receipt'] != state['receipt']:
                        raise ValueError("Recovered delivery changed its paid receipt")
                    state = self.store.update(scope, state, phase='PAID', result=result)
                if 'verdict' not in state:
                    body = state['result'].get('output', {}).get('body')
                    output = body.get('output') if isinstance(body, dict) else None
                    metadata=body.get('provider_metadata') if isinstance(body,dict) else None
                    if qualified_model and (not isinstance(metadata,dict)
                        or metadata.get('provider_type')!='ANTHROPIC_API' or metadata.get('provider_model')!=qualified_model):
                        return self.store.update(scope,state,phase='DELIVERY_IDENTITY_MISMATCH',
                            recovery_required=False,qualification_identity_verified=False)
                    state = self.store.update(scope, state, phase='VERIFIED', output=output, verdict=check(task, output))
                if not state['customer_closed']:
                    capture = state['spent_micro_usd'] // 10000 * 10000
                    state = self.store.update(scope, state, phase='CAPTURING')
                    settled = self.treasury.run(scope, hold, capture, recover)
                    if not settled['complete']:
                        return self.store.update(scope, state, phase='CAPTURE_PENDING')
                    state = self.store.update(scope, state, phase='CUSTOMER_CLOSED', customer_closed=True,
                        captured_micro_usd=capture, merchant_rounding_micro_usd=state['spent_micro_usd']-capture,
                        unused_authorization_micro_usd=hold-capture, capture=settled['intent'])
                if not return_float:
                    balance=rail.balance()
                    retained=int(balance['spendable_base_units'])
                    start=int(state['funding'].get('starting_spendable_base_units',allocation*10**12))
                    expected=start-state['spent_micro_usd']*10**12
                    matched=retained==expected and not balance.get('pending_invoice',False)
                    # A deliberately retained balance is not a refund or final settlement.
                    return self.store.update(scope,state,phase='CLOSED_FLOAT_RETAINED' if matched else 'CLOSED_RECONCILIATION_PENDING',
                        unused_float_policy='RETAIN_IN_ORIGINAL_WALLET',withdrawal=None,
                        retained_float_base_units=str(retained),float_returned_confirmed=False,recovery_required=False,
                        reconciliation={'receipt_matches_quote':True,'provider_spend_micro_usdz':state['spent_micro_usd'],
                            'customer_capture_micro_usd':state['captured_micro_usd'],'bridge_or_fx_executed':False,
                            'bank_and_token_balances_separate':True,'retained_balance_matches':matched,
                            'final_settlement_verified':False})
                withdrawal = rail.withdraw()
                claims = dict(state['confirmed_claims'])
                for claim in withdrawal.get('claimed', []):
                    if not claim['deferred']:
                        amount = int(claim['amount'])
                        if amount % 10**12:
                            raise ValueError("Withdrawal claim is not exact micro-USD")
                        claims[claim['tx']] = amount // 10**12
                required_return = allocation-state['spent_micro_usd']
                returned = sum(claims.values()) >= required_return
                # 'empty' can mean the current epoch has not finalized. Only
                # actual distinct non-deferred claims prove allocated float returned.
                finished = returned and withdrawal.get('queued') is None and withdrawal.get('status') != 'waiting'
                return self.store.update(scope, state, phase='COMPLETED' if finished else 'CLOSED_FLOAT_PENDING',
                    withdrawal=withdrawal, float_returned_confirmed=returned, confirmed_claims=claims,
                    float_returned_micro_usd=sum(claims.values()), recovery_required=False,
                    reconciliation={"receipt_matches_quote": True, "provider_spend_micro_usd": state['spent_micro_usd'],
                        "customer_capture_micro_usd": state['captured_micro_usd'], "bridge_or_fx_executed": False,
                        "bank_and_token_balances_separate": True})
            except (CreateRejected, ScopeRetired):
                return self.store.update(scope, state, phase='BLOCKED_CONFIGURATION', recovery_required=False,
                                         bank_errors=self.treasury.journal.errors(scope))
            except (OutcomeUnknown, PaymentPending):
                # Keep the exact phase, quote and original reservation. A later
                # --recover reads authoritative state before another effect.
                return self.store.update(scope, state, recovery_required=True, bank_errors=self.treasury.journal.errors(scope))
            except PolicyError:
                return self.store.update(scope, state, phase='PAUSED_BEFORE_PAYMENT')
