import json
import os
import re
from urllib.parse import urlencode, urlsplit

from .holds import OutcomeUnknown, SandboxHoldWorkflow, api_usd, micro_usd, public_intent


CHECKOUT_API_VERSION = "2026-05-29"
CHECKOUT_SESSIONS_PATH = "/api/v1/checkout/checkout_sessions"


class HostedCheckoutWorkflow:
    def __init__(self, client, journal, success_url=None):
        self.client = client
        self.journal = journal
        self.account_id = getattr(client, "account_id", None)
        self.success_url = success_url or os.environ.get("AIRWALLEX_CHECKOUT_SUCCESS_URL", "https://www.airwallex.com")
        parsed = urlsplit(self.success_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("Hosted checkout success URL must be a public HTTPS URL without credentials or fragment")

    def _request(self, method, path, body=None):
        return self.client.request(method, path, body, api_version=CHECKOUT_API_VERSION)

    def _validate_scope(self, scope, hold):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", scope) or type(hold) is not int or not 0 < hold <= 10000000:
            raise ValueError("Invalid hosted-checkout scope or amount; sandbox holds are limited to USD 10")
        api_usd(hold)
        if not isinstance(self.account_id, str) or not re.fullmatch(r"acct_[A-Za-z0-9]+", self.account_id):
            raise ValueError("Set AIRWALLEX_ACCOUNT_ID from the sandbox Account details page for hosted checkout")

    def _body(self, scope, hold):
        return {
            "account_id": self.account_id,
            "mode": "PAYMENT",
            "currency": "USD",
            "success_url": self.success_url,
            "ui_mode": "HOSTED",
            "invoice_creation": {"enabled": False},
            "payment_intent_data": {"merchant_order_id": scope},
            "line_items": [{
                "price": {
                    "currency": "USD",
                    "pricing_model": "FLAT",
                    "flat_amount": api_usd(hold),
                    "product": {"name": "Touchstone sandbox authorization"},
                },
                "quantity": 1,
            }],
            "payment_options": {
                "payment_method_types": ["card"],
                "authorization_type": "final_auth",
                "auto_capture": False,
            },
            "metadata": {"touchstone_scope": scope, "touchstone_purpose": "sandbox_authorization"},
        }

    def _session(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"bco_[A-Za-z0-9]+", session_id):
            raise ValueError("Invalid Airwallex Checkout Session ID")
        return self._request("GET", f"{CHECKOUT_SESSIONS_PATH}/{session_id}")

    def _validate_session(self, session, scope):
        if (not isinstance(session, dict) or not re.fullmatch(r"bco_[A-Za-z0-9]+", session.get("id", ""))
                or session.get("mode") != "PAYMENT" or session.get("account_id") != self.account_id
                or session.get("currency") != "USD"):
            raise ValueError("Checkout Session does not match the sandbox payment account")
        intent_data = session.get("payment_intent_data")
        metadata = session.get("metadata")
        payment_options = session.get("payment_options")
        if (not isinstance(intent_data, dict) or intent_data.get("merchant_order_id") != scope
                or not isinstance(metadata, dict) or metadata.get("touchstone_scope") != scope
                or not isinstance(payment_options, dict) or payment_options.get("auto_capture") is not False):
            raise ValueError("Checkout Session does not match the approved scope or uncaptured-hold terms")
        if session.get("status") == "ACTIVE":
            parsed = urlsplit(session.get("url", ""))
            if (parsed.scheme != "https" or parsed.hostname != "checkout.airwallex.com" or parsed.username
                    or parsed.password or parsed.fragment):
                raise ValueError("Airwallex returned an unexpected hosted-checkout URL")

    def _recover_create(self, scope, prior):
        path = CHECKOUT_SESSIONS_PATH + "?" + urlencode({"account_id": self.account_id, "page_size": 100})
        matches = []
        for _ in range(10):
            result = self._request("GET", path)
            if not isinstance(result, dict) or not isinstance(result.get("items"), list):
                raise OutcomeUnknown("Checkout Session lookup was inconclusive; no replacement checkout was created")
            matches.extend(item for item in result["items"] if isinstance(item, dict)
                           and isinstance(item.get("metadata"), dict)
                           and item["metadata"].get("touchstone_scope") == scope)
            if len(matches) > 1:
                raise OutcomeUnknown("Multiple Checkout Sessions match this scope; no replacement checkout was created")
            cursor = result.get("page_after")
            if not cursor:
                break
            path = CHECKOUT_SESSIONS_PATH + "?" + urlencode({"account_id": self.account_id, "page_size": 100,
                                                              "page_after": cursor})
        else:
            raise OutcomeUnknown("Checkout Session search reached its safe page limit; no replacement checkout was created")
        if len(matches) != 1:
            raise OutcomeUnknown("Checkout Session is not uniquely visible yet; inspect the sandbox portal before retrying")
        session = matches[0]
        self._validate_session(session, scope)
        self.journal.observe(scope, "checkout_create", session)
        return session["id"]

    def start(self, scope, hold=1000000, recover=False):
        self._validate_scope(scope, hold)
        self.journal.bind_authorization(scope, hold)
        if self.journal.get(scope, "create"):
            raise OutcomeUnknown("A direct PaymentIntent already exists for this scope; reconcile it instead of creating hosted checkout")
        body = self._body(scope, hold)
        path = CHECKOUT_SESSIONS_PATH + "/create"
        prior = self.journal.get(scope, "checkout_create")
        if prior and prior["state"] != "OBSERVED":
            if not recover:
                raise OutcomeUnknown("Checkout Session create is unresolved; rerun the same scope with --recover")
            session_id = self._recover_create(scope, prior)
        elif prior:
            session_id = json.loads(prior["response"])["id"]
        else:
            request_id, cached = self.journal.begin(scope, "checkout_create", path, body)
            if cached is not None:
                session_id = cached["id"]
            else:
                try:
                    session = self._request("POST", path, {**body, "request_id": request_id})
                    self._validate_session(session, scope)
                    self.journal.observe(scope, "checkout_create", session)
                    session_id = session["id"]
                except Exception as error:
                    self.journal.error(scope, "checkout_create", error)
                    self.journal.uncertain(scope, "checkout_create")
                    raise OutcomeUnknown("Checkout Session create is unresolved; rerun the same scope with --recover") from None
        session = self._session(session_id)
        self._validate_session(session, scope)
        if session.get("status") == "ACTIVE":
            return {"mode": "SANDBOX_HOSTED_CHECKOUT", "scope": scope, "checkout_session_id": session_id,
                    "status": "ACTIVE", "checkout_url": session["url"], "expires_at": session.get("expires_at"),
                    "authorization_ready": False, "payment_created": False}
        return self.status(scope, hold, recover=False)

    def status(self, scope, hold=1000000, recover=False):
        self._validate_scope(scope, hold)
        self.journal.bind_authorization(scope, hold)
        operation = self.journal.get(scope, "checkout_create")
        if not operation:
            raise ValueError("No hosted checkout exists for this scope; start one before checking status")
        if operation["state"] != "OBSERVED":
            if not recover:
                raise OutcomeUnknown("Checkout Session create is unresolved; rerun with --recover")
            session_id = self._recover_create(scope, operation)
        else:
            session_id = json.loads(operation["response"])["id"]
        session = self._session(session_id)
        self._validate_session(session, scope)
        result = {"mode": "SANDBOX_HOSTED_CHECKOUT", "scope": scope, "checkout_session_id": session_id,
                  "status": session.get("status"), "expires_at": session.get("expires_at"),
                  "authorization_ready": False, "payment_created": session.get("status") == "COMPLETED"}
        if session.get("status") != "COMPLETED":
            return result
        intent_id = session.get("payment_intent_id")
        if not isinstance(intent_id, str) or not re.fullmatch(r"int_[A-Za-z0-9]+", intent_id):
            return {**result, "payment_status": "PENDING", "next_action": "Poll again after hosted checkout settles"}
        raw_intent = self.client.request("GET", f"/api/v1/pa/payment_intents/{intent_id}")
        SandboxHoldWorkflow._validate(raw_intent, scope, hold)
        intent = public_intent(raw_intent)
        captured = micro_usd(raw_intent.get("captured_amount", 0))
        if raw_intent.get("status") == "SUCCEEDED" or captured:
            raise ValueError("Hosted checkout captured funds despite the uncaptured-hold mandate; stop for reconciliation")
        if raw_intent.get("status") != "REQUIRES_CAPTURE":
            return {**result, "payment_status": raw_intent.get("status", "UNKNOWN"),
                    "next_action": "Wait for an authoritative REQUIRES_CAPTURE state; do not dispatch a job"}
        body = {"session_id": session_id, "hold": api_usd(hold), "currency": "USD", "merchant_order_id": scope}
        _, cached = self.journal.begin(scope, "hosted_authorization", f"{CHECKOUT_SESSIONS_PATH}/{session_id}", body)
        if cached is None:
            self.journal.observe(scope, "hosted_authorization", raw_intent)
        elif cached.get("id") != intent_id:
            raise ValueError("Hosted authorization changed after being recorded")
        return {**result, "payment_status": raw_intent.get("status"), "authorization_ready": True,
                "intent": intent, "approved_micro_usd": hold}
