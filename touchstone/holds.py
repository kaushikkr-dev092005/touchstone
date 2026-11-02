"""Recoverable sandbox pre-authorization/capture workflow, separate from mock jobs."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid
from urllib.parse import urlencode

from .ledger import ClosingConnection, canonical
from .treasury import AirwallexHTTPError


class OutcomeUnknown(RuntimeError):
    pass


class CreateRejected(RuntimeError):
    """Definitive configuration rejection; the create UUID is consumed."""


class ScopeRetired(RuntimeError):
    pass


def micro_usd(value):
    try:
        amount = Decimal(str(value))
        micros = amount * 1000000
        if not amount.is_finite() or micros != micros.to_integral_value() or amount < 0:
            raise ValueError("Amount must be nonnegative USD with at most six decimal places")
        return int(micros)
    except (ArithmeticError, TypeError):  # InvalidOperation and Overflow (e.g. "1e999999")
        raise ValueError("Invalid USD amount") from None


def api_usd(micros):
    if type(micros) is not int or micros < 0 or micros % 10000:
        raise ValueError("Card amounts must be exact whole cents; fractional cents cannot be silently rounded")
    return float(Decimal(micros) / 1000000)


def public_intent(raw):
    fields = ("id", "status", "amount", "currency", "captured_amount", "merchant_order_id", "updated_at",
              "account_id", "expires_at", "mode", "payment_intent_id", "created_at")
    return {k: raw[k] for k in fields if k in raw}


class OperationJournal:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS operations(
              scope TEXT NOT NULL, action TEXT NOT NULL, request_id TEXT UNIQUE NOT NULL,
              path TEXT NOT NULL, digest TEXT NOT NULL, state TEXT NOT NULL, response TEXT,
              PRIMARY KEY(scope,action))""")
            db.execute('CREATE TABLE IF NOT EXISTS operation_errors(scope TEXT,action TEXT,status INTEGER,code TEXT,PRIMARY KEY(scope,action))')
            db.execute('''CREATE TABLE IF NOT EXISTS retired_scopes(
                scope TEXT PRIMARY KEY, replacement TEXT UNIQUE NOT NULL,
                evidence TEXT NOT NULL, retired_at REAL NOT NULL)''')

    @staticmethod
    def _active(db, scope):
        if db.execute('SELECT 1 FROM retired_scopes WHERE scope=?', (scope,)).fetchone():
            raise ScopeRetired("Scope is permanently retired; use its fresh replacement scope")

    def assert_active(self, scope):
        with self.connect() as db:
            self._active(db, scope)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        return db

    def get(self, scope, action):
        with self.connect() as db:
            row = db.execute("SELECT * FROM operations WHERE scope=? AND action=?", (scope, action)).fetchone()
            return dict(row) if row else None

    def begin(self, scope, action, path, body):
        digest = hashlib.sha256(canonical(body).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db, scope)
            row = db.execute("SELECT * FROM operations WHERE scope=? AND action=?", (scope, action)).fetchone()
            if row:
                if row["digest"] != digest or row["path"] != path:
                    raise ValueError("Existing operation is bound to different terms; refusing a changed retry")
                if row["state"] == "OBSERVED":
                    return row["request_id"], json.loads(row["response"])
                if row["state"] == "REJECTED_NO_OBJECT":
                    raise CreateRejected("Create rejected without an object; request ID consumed. Retire scope with evidence before a fresh scope.")
                raise OutcomeUnknown(f"{action} is {row['state']}; retrieve and reconcile before any new write")
            request_id = str(uuid.uuid4())
            db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,NULL)", (scope, action, request_id, path, digest, "IN_FLIGHT"))
            return request_id, None

    def bind_terms(self, scope, hold, capture):
        digest = hashlib.sha256(canonical({"hold": hold, "capture": capture, "currency": "USD"}).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active(db, scope)
            row = db.execute("SELECT digest FROM operations WHERE scope=? AND action='terms'", (scope,)).fetchone()
            if row and row["digest"] != digest:
                raise ValueError("Existing operation is bound to different terms; refusing a changed retry")
            if not row:
                db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,?)",
                           (scope, "terms", str(uuid.uuid4()), "/local/approved-terms", digest, "OBSERVED", "{}"))

    def bind_authorization(self, scope, hold):
        digest = hashlib.sha256(canonical({"hold": hold, "currency": "USD"}).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._active(db, scope)
            row = db.execute("SELECT digest FROM operations WHERE scope=? AND action='authorization_terms'", (scope,)).fetchone()
            if row and row[0] != digest:
                raise ValueError("Authorization scope is bound to a different hold")
            if not row:
                db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?)', (scope, 'authorization_terms', str(uuid.uuid4()),
                    '/local/authorization', digest, 'OBSERVED', '{}'))

    def observe(self, scope, action, response):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._active(db, scope)
            db.execute("UPDATE operations SET state='OBSERVED',response=? WHERE scope=? AND action=?",
                       (canonical(public_intent(response)), scope, action))

    def uncertain(self, scope, action):
        with self.connect() as db:
            db.execute("UPDATE operations SET state='UNKNOWN' WHERE scope=? AND action=?", (scope, action))

    def error(self, scope, action, error):
        if isinstance(error, AirwallexHTTPError):
            with self.connect() as db:
                db.execute('INSERT OR REPLACE INTO operation_errors VALUES(?,?,?,?)', (scope, action, error.status, error.code))

    def errors(self, scope):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT action,status,code FROM operation_errors WHERE scope=?', (scope,))]

    def claim_create_retry(self, scope, prior):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._active(db, scope)
            row = db.execute("SELECT * FROM operations WHERE scope=? AND action='create'", (scope,)).fetchone()
            if not row or row['state'] != prior['state'] or row['request_id'] != prior['request_id']:
                raise OutcomeUnknown("Create state changed; no replay sent")
            if row['state'] not in {'UNKNOWN', 'IN_FLIGHT'}:
                raise OutcomeUnknown("Create is not eligible for same-request recovery")
            db.execute("UPDATE operations SET state='IN_FLIGHT' WHERE scope=? AND action='create'", (scope,))

    def classify_create_error(self, scope, action, error):
        self.error(scope, action, error)
        state = "UNKNOWN"
        if action == "create" and isinstance(error, AirwallexHTTPError) and 400 <= error.status < 500:
            if error.code == "configuration_error":
                state = "REJECTED_NO_OBJECT"
            elif error.code == "duplicate_request":
                state = "REQUEST_ID_CONSUMED"
        with self.connect() as db:
            db.execute('UPDATE operations SET state=? WHERE scope=? AND action=?', (state, scope, action))
        return state

    def retire(self, scope, replacement, evidence, client):
        """Local tombstone, not cancellation. Empty lookup alone cannot retire uncertainty."""
        if any(not isinstance(s, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', s) for s in (scope, replacement)) or scope == replacement:
            raise ValueError("Retirement requires distinct valid old and fresh replacement scopes")
        required = {"scope", "request_id", "kind", "reference", "no_object_created"}
        if not isinstance(evidence, dict) or set(evidence) != required:
            raise ValueError("Provide only scope, request_id, kind, reference and no_object_created evidence fields")
        if (evidence["scope"] != scope or evidence["no_object_created"] is not True
            or evidence["kind"] not in {"RECORDED_CONFIGURATION_ERROR", "AIRWALLEX_SUPPORT"}
            or not isinstance(evidence["reference"], str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', evidence["reference"])):
            raise ValueError("Retirement needs a recorded rejection or support reference affirming no object was created")
        prior = self.get(scope, 'create')
        if not prior or prior['request_id'] != evidence['request_id'] or prior['state'] not in {'UNKNOWN', 'REQUEST_ID_CONSUMED', 'REJECTED_NO_OBJECT'}:
            raise ValueError("Evidence does not match a stuck or rejected create request")
        if evidence['kind'] == 'RECORDED_CONFIGURATION_ERROR':
            errors = self.errors(scope)
            if not any(e['action'] == 'create' and e['code'] == 'configuration_error' and 400 <= e['status'] < 500 for e in errors):
                raise ValueError("No persisted configuration rejection matches this request; support evidence is required")
        result = client.request('GET', '/api/v1/pa/payment_intents?' + urlencode({'merchant_order_id': scope, 'page_size': 100}))
        if not isinstance(result, dict) or result.get('items') != [] or result.get('has_more') is not False:
            raise OutcomeUnknown("Retirement blocked: read-back is nonempty or incomplete")
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._active(db, scope)
            self._active(db, replacement)
            current = db.execute("SELECT * FROM operations WHERE scope=? AND action='create'", (scope,)).fetchone()
            if not current or current['state'] != prior['state'] or current['request_id'] != prior['request_id']:
                raise OutcomeUnknown("Operation changed during retirement; review again")
            if db.execute('SELECT 1 FROM operations WHERE scope=?', (replacement,)).fetchone():
                raise ValueError("Replacement scope has already been used")
            if db.execute("SELECT 1 FROM operations WHERE scope=? AND action NOT IN ('create','terms','authorization_terms')", (scope,)).fetchone():
                raise ValueError("Scope has other financial operations; retirement cannot clear them")
            db.execute('INSERT INTO retired_scopes VALUES(?,?,?,?)', (scope, replacement, canonical(evidence), time.time()))
            db.execute("UPDATE operations SET state='RETIRED' WHERE scope=? AND action='create'", (scope,))
        return {"label": getattr(client, 'evidence_label', 'MOCK'), "scope": scope, "replacement_scope": replacement, "state": "RETIRED",
                "request_id_consumed": True, "evidence_kind": evidence['kind'], "evidence_reference": evidence['reference'],
                "remote_writes_performed": False, "money_moved": False,
                "caveat": "Support evidence is an operator attestation; retirement does not cancel a remote object"}


class SandboxHoldWorkflow:
    """One immutable customer authorization, one capture and optional remainder cancel.

    Only a fixed public Airwallex sandbox test card is supported by this smoke workflow.
    It never attaches simulated procurement spend to a real customer payment.
    """
    def __init__(self, client, journal):
        self.client, self.journal = client, journal

    def _write(self, scope, action, path, body):
        request_id, cached = self.journal.begin(scope, action, path, body)
        if cached is not None:
            return cached
        try:
            raw = self.client.request("POST", path, {**body, "request_id": request_id})
            if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
                raise RuntimeError("Missing intent ID in sandbox response")
            self.journal.observe(scope, action, raw)
            return public_intent(raw)
        except Exception as error:
            state = self.journal.classify_create_error(scope, action, error)
            if state == 'REJECTED_NO_OBJECT':
                raise CreateRejected("PaymentIntent create rejected by merchant configuration; no object created, request ID consumed") from None
            raise OutcomeUnknown(f"{action} outcome requires reconciliation; rerun the same scope with --recover") from None

    def _recover_create(self, scope, hold):
        self.journal.assert_active(scope)
        prior = self.journal.get(scope, 'create')
        if prior and prior['state'] == 'REJECTED_NO_OBJECT':
            raise CreateRejected("Create was definitively rejected; consumed request ID cannot be retried")
        result = self.client.request('GET', '/api/v1/pa/payment_intents?' + urlencode({'merchant_order_id':scope, 'page_size':100}))
        matches = [x for x in result.get('items', []) if x.get('merchant_order_id') == scope]
        if len(matches) == 1 and not result.get('has_more'):
            self._validate(matches[0], scope, hold)
            self.journal.observe(scope, 'create', matches[0])
            return
        if matches or result.get('has_more'):
            raise OutcomeUnknown('Cannot uniquely recover create; no replacement order sent')
        # Airwallex explicitly documents returning the original create response
        # for the SAME request_id. Reuse the exact persisted UUID and body,
        # after checking reads; never generate another create request ID.
        # https://www.airwallex.com/docs/payments/get-started/using-payments-intent-api
        if prior['state'] == 'REQUEST_ID_CONSUMED' or any(e['action'] == 'create' and e['code'] == 'duplicate_request' for e in self.journal.errors(scope)):
            raise OutcomeUnknown("Request ID consumed; no replay allowed. Retire with evidence and use a fresh scope")
        body = {'amount':api_usd(hold), 'currency':'USD', 'merchant_order_id':scope}
        if prior['digest'] != hashlib.sha256(canonical(body).encode()).hexdigest():
            raise ValueError('Create recovery terms changed')
        self.journal.claim_create_retry(scope, prior)
        try:
            intent = self.client.request('POST', prior['path'], {**body, 'request_id':prior['request_id']})
            self._validate(intent, scope, hold)
            self.journal.observe(scope, 'create', intent)
        except Exception as error:
            state = self.journal.classify_create_error(scope, 'create', error)
            if state == 'REJECTED_NO_OBJECT':
                raise CreateRejected("Create rejected without an object; original request ID is consumed") from None
            raise OutcomeUnknown('Original create request remains unresolved; no new request ID used') from None

    @staticmethod
    def _validate(intent, scope, hold):
        if not re.fullmatch(r"int_[A-Za-z0-9]+", intent.get("id", "")):
            raise ValueError("Invalid payment intent ID")
        if intent.get("currency") != "USD" or micro_usd(intent.get("amount")) != hold or intent.get("merchant_order_id") != scope:
            raise ValueError("Sandbox intent does not match the approved order, currency and hold")

    def _get(self, intent_id):
        if not re.fullmatch(r"int_[A-Za-z0-9]+", intent_id):
            raise ValueError("Invalid payment intent ID")
        return public_intent(self.client.request("GET", f"/api/v1/pa/payment_intents/{intent_id}"))

    def authorize(self, scope, hold=1000000, recover=False):
        """Authorize first; the final captured amount is bound after actual spend."""
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", scope) or type(hold) is not int or not 0 < hold <= 10000000:
            raise ValueError("Invalid sandbox authorization scope or amount")
        api_usd(hold)
        self.journal.bind_authorization(scope, hold)
        hosted = self.journal.get(scope, "hosted_authorization")
        if hosted:
            if hosted["state"] != "OBSERVED" or self.journal.get(scope, "create"):
                raise OutcomeUnknown("Hosted authorization conflicts with an unresolved direct create; reconcile before proceeding")
            intent = json.loads(hosted["response"])
            self._validate(intent, scope, hold)
            current = self._get(intent["id"])
            self._validate(current, scope, hold)
            ready = current.get("status") == "REQUIRES_CAPTURE" and micro_usd(current.get("captured_amount", 0)) == 0
            return {"mode": "SANDBOX", "intent": current, "ready": ready, "approved_micro_usd": hold}
        if self.journal.get(scope, "checkout_create"):
            raise OutcomeUnknown("Hosted checkout is pending; complete it and verify with airwallex-checkout --status")
        create = self.journal.get(scope, "create")
        if create and create["state"] != "OBSERVED" and recover:
            self._recover_create(scope, hold)
        intent = self._write(scope, "create", "/api/v1/pa/payment_intents/create",
                             {"amount": api_usd(hold), "currency": "USD", "merchant_order_id": scope})
        self._validate(intent, scope, hold)
        current = self._get(intent["id"])
        self._validate(current, scope, hold)
        confirm = self.journal.get(scope, "confirm")
        if confirm and confirm["state"] != "OBSERVED" and recover and current.get("status") == "REQUIRES_CAPTURE":
            self.journal.observe(scope, "confirm", current)
        if current.get("status") == "REQUIRES_PAYMENT_METHOD":
            self._write(scope, "confirm", f"/api/v1/pa/payment_intents/{intent['id']}/confirm", {
                "payment_method": {"type": "card", "card": {"number": "4035501000000008", "expiry_month": "12", "expiry_year": "2030", "cvc": "123", "name": "Touchstone Sandbox"}},
                "payment_method_options": {"card": {"authorization_type": "pre_auth", "auto_capture": False}}})
            current = self._get(intent["id"])
            self._validate(current, scope, hold)
        ready = current.get("status") == "REQUIRES_CAPTURE" and micro_usd(current.get("captured_amount", 0)) == 0
        return {"mode": "SANDBOX", "intent": current, "ready": ready, "approved_micro_usd": hold}

    def refresh(self, scope, hold, intent_id):
        current = self._get(intent_id)
        self._validate(current, scope, hold)
        if current.get("status") != "REQUIRES_CAPTURE" or micro_usd(current.get("captured_amount", 0)):
            raise OutcomeUnknown("Customer authorization is no longer available; no purchase dispatched")
        return current

    def run(self, scope, hold=1000000, capture=500000, recover=False):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", scope):
            raise ValueError("Scope must be 1-48 letters, digits, underscores or hyphens")
        if not 0 < hold <= 10000000 or not 0 <= capture <= hold:
            raise ValueError("Sandbox smoke holds are limited to USD 10; capture must fit the hold")
        api_usd(hold)
        api_usd(capture)
        # Bind capture terms before ANY network write, including create/confirm.
        self.journal.bind_terms(scope, hold, capture)
        hosted = self.journal.get(scope, "hosted_authorization")
        if hosted:
            if hosted["state"] != "OBSERVED" or self.journal.get(scope, "create"):
                raise OutcomeUnknown("Hosted authorization conflicts with an unresolved direct create; reconcile before proceeding")
            intent = json.loads(hosted["response"])
            self._validate(intent, scope, hold)
        else:
            if self.journal.get(scope, "checkout_create"):
                raise OutcomeUnknown("Hosted checkout is pending; complete it and verify with airwallex-checkout --status")
            create = self.journal.get(scope, "create")
            if create and create["state"] != "OBSERVED" and recover:
                self._recover_create(scope, hold)
            intent = self._write(scope, "create", "/api/v1/pa/payment_intents/create",
                                 {"amount": api_usd(hold), "currency": "USD", "merchant_order_id": scope})
            self._validate(intent, scope, hold)
        intent_id = intent["id"]
        current = self._get(intent_id)
        self._validate(current, scope, hold)
        if recover:
            for action in ("confirm", "capture", "cancel"):
                op = self.journal.get(scope, action)
                if not op or op["state"] == "OBSERVED":
                    continue
                settled = (action == "confirm" and current.get("status") in {"REQUIRES_CAPTURE", "SUCCEEDED", "CANCELLED"}
                           or action == "capture" and micro_usd(current.get("captured_amount", 0)) == capture and capture > 0
                           or action == "cancel" and current.get("status") == "CANCELLED")
                if not settled:
                    raise OutcomeUnknown(f"{action} remains unconfirmed; no additional write sent")
                self.journal.observe(scope, action, current)
        if current["status"] == "REQUIRES_PAYMENT_METHOD":
            self._write(scope, "confirm", f"/api/v1/pa/payment_intents/{intent_id}/confirm", {
                "payment_method": {"type": "card", "card": {"number": "4035501000000008", "expiry_month": "12", "expiry_year": "2030", "cvc": "123", "name": "Touchstone Sandbox"}},
                "payment_method_options": {"card": {"authorization_type": "pre_auth", "auto_capture": False}}})
            current = self._get(intent_id)
            self._validate(current, scope, hold)
        captured = micro_usd(current.get("captured_amount", 0))
        if captured not in {0, capture}:
            raise ValueError("Unexpected captured amount; stopping for reconciliation")
        if current["status"] == "REQUIRES_CAPTURE" and captured == 0 and capture:
            self._write(scope, "capture", f"/api/v1/pa/payment_intents/{intent_id}/capture", {"amount": api_usd(capture)})
            current = self._get(intent_id)
            self._validate(current, scope, hold)
            captured = micro_usd(current.get("captured_amount", 0))
        if current["status"] == "REQUIRES_CAPTURE" and captured == capture:
            self._write(scope, "cancel", f"/api/v1/pa/payment_intents/{intent_id}/cancel", {})
            current = self._get(intent_id)
            self._validate(current, scope, hold)
        captured = micro_usd(current.get("captured_amount", 0))
        closed = current.get("status") in {"SUCCEEDED", "CANCELLED"} and captured == capture
        return {"mode": "SANDBOX", "scope": scope, "intent": current, "complete": closed,
                "approved_micro_usd": hold, "captured_micro_usd": captured,
                "unused_authorization_micro_usd": hold - captured,
                "issuer_release_timing": "Not measured; unused amount is not a confirmed wallet credit",
                "next_action": "none" if closed else "Inspect intent status and any required customer action in the sandbox portal",
                "dashboard_mode_changed": False}
