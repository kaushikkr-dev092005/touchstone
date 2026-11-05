"""Sandbox-only Airwallex transport; writes are owned by the durable hold workflow."""
import json
import os
import urllib.error
import urllib.request
import time
import re
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation

BASE_URL = "https://api.sandbox.airwallex.com"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Refusing to forward sandbox credentials through a redirect")


class AirwallexSandbox:
    evidence_label = "MEASURED"
    def __init__(self):
        if os.environ.get("AIRWALLEX_BASE_URL", BASE_URL).rstrip("/") != BASE_URL:
            raise ValueError("Only the documented Airwallex sandbox host is supported")
        self.client_id = os.environ.get("AIRWALLEX_CLIENT_ID")
        self.api_key = os.environ.get("AIRWALLEX_API_KEY")
        self.account_id = os.environ.get("AIRWALLEX_ACCOUNT_ID")
        if not self.client_id or not self.api_key:
            raise ValueError("Set AIRWALLEX_CLIENT_ID and AIRWALLEX_API_KEY in your shell; never paste secrets into chat")
        self.opener = urllib.request.build_opener(NoRedirect())
        self.token = None
        self.token_until = 0

    def _request(self, path, method="GET", headers=None, body=None):
        if not path.startswith("/api/v1/") or ".." in path or "#" in path:
            raise ValueError("Invalid Airwallex API path")
        request = urllib.request.Request(BASE_URL + path, method=method, headers={"Content-Type": "application/json", **(headers or {})},
                                         data=json.dumps(body, allow_nan=False).encode() if body is not None else None)
        try:
            with self.opener.open(request, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            try:
                code = json.loads(e.read(20000)).get('code')
                code = code if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_]{1,80}', code) else None
            except (ValueError, AttributeError):
                code = None
            raise AirwallexHTTPError(e.code, code) from None
        except urllib.error.URLError:
            raise RuntimeError("Airwallex sandbox could not be reached") from None

    def authenticate(self):
        if not self.token or time.monotonic() >= self.token_until:
            login = self._request("/api/v1/authentication/login", "POST", self.login_headers())
            self.token = login["token"]
            if not isinstance(self.token, str) or not self.token:
                raise ValueError('Airwallex authentication returned no usable token')
            self.token_until = time.monotonic() + 25 * 60
        return True

    def request(self, method, path, body=None, api_version=None):
        self.authenticate()
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}
        if api_version is not None:
            if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", api_version):
                raise ValueError("Invalid Airwallex API version")
            headers["x-api-version"] = api_version
        return self._request(path, method, headers, body)

    def login_headers(self):
        headers = {"x-client-id": self.client_id, "x-api-key": self.api_key}
        if self.account_id:
            headers['x-login-as'] = self.account_id
        return headers

    def smoke(self):
        self.authenticate()
        headers = {"Authorization": "Bearer " + self.token}
        reads, errors = {}, {}
        for name, path in (("balance_read", '/api/v1/balances/current'), ("global_accounts_read", '/api/v1/global_accounts')):
            try:
                reads[name] = isinstance(self._request(path, headers=headers), (list, dict))
            except AirwallexHTTPError as error:
                reads[name] = False
                errors[name] = {"http_status": error.status, "reason": "Check account selection and scoped key permissions"}
        if self.account_id:
            checkout_headers = {**headers, "x-api-version": "2026-05-29"}
            checkout_path = "/api/v1/checkout/checkout_sessions?" + urlencode({"account_id": self.account_id, "page_size": 10})
            try:
                result = self._request(checkout_path, headers=checkout_headers)
                reads["checkout_sessions_read"] = isinstance(result, dict) and isinstance(result.get("items"), list)
            except AirwallexHTTPError as error:
                reads["checkout_sessions_read"] = False
                errors["checkout_sessions_read"] = {"http_status": error.status,
                    "reason": "Check Checkout Sessions read permission and API availability"}
            try:
                result = self.request("GET", "/api/v1/fx/conversions?" + urlencode({"page_size": 10}))
                reads["fx_conversions_read"] = isinstance(result, dict) and isinstance(result.get("items"), list)
            except AirwallexHTTPError as error:
                reads["fx_conversions_read"] = False
                errors["fx_conversions_read"] = {"http_status": error.status,
                    "reason": "Check Transactional FX Conversion read permission"}
        else:
            reads["checkout_sessions_read"] = False
            errors["checkout_sessions_read"] = {"reason": "Set AIRWALLEX_ACCOUNT_ID to check Checkout Sessions access"}
            reads["fx_conversions_read"] = False
            errors["fx_conversions_read"] = {"reason": "Set AIRWALLEX_ACCOUNT_ID to check Transactional FX access"}
        # Do not print credentials, tokens, bank account details, or raw responses.
        return {"mode": "SANDBOX", "host": BASE_URL, "authenticated": True,
                **reads, "read_errors": errors, "account_context_configured": bool(self.account_id),
                "checkout_sessions_write_verified": False, "writes_performed": False, "dashboard_mode_changed": False}

    def current_balances(self):
        self._require_account_context()
        result = self.request("GET", "/api/v1/balances/current")
        if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
            raise ValueError("Airwallex returned an invalid balances response")
        return result

    def create_fx_quote(self, sell_currency, buy_currency, sell_amount, validity="MIN_15"):
        self._require_account_context()
        sell_currency, buy_currency = _currency(sell_currency), _currency(buy_currency)
        amount = _amount(sell_amount)
        if sell_currency == buy_currency:
            raise ValueError("FX currencies must differ")
        numeric_amount = float(amount)
        if Decimal(str(numeric_amount)) != amount:
            raise ValueError("Sell amount cannot be represented exactly as an Airwallex JSON number")
        if validity not in {"MIN_1", "MIN_15", "MIN_30", "HR_1", "HR_4", "HR_8", "HR_24"}:
            raise ValueError("Unsupported Airwallex quote validity")
        result = self.request("POST", "/api/v1/fx/quotes/create", {
            "sell_currency": sell_currency, "buy_currency": buy_currency,
            "sell_amount": numeric_amount, "validity": validity,
        })
        if not isinstance(result, dict) or not isinstance(result.get("quote_id"), str):
            raise ValueError("Airwallex returned an invalid FX quote")
        if result.get("sell_currency") != sell_currency or result.get("buy_currency") != buy_currency:
            raise ValueError("Airwallex quote currencies differ from the request")
        try:
            quoted_sell = Decimal(str(result.get("sell_amount")))
        except InvalidOperation:
            raise ValueError("Airwallex quote has no valid sell amount") from None
        if quoted_sell != amount:
            raise ValueError("Airwallex quote sell amount differs from the request")
        return result

    def create_conversion(self, quote, request_id):
        return self.request("POST", "/api/v1/fx/conversions/create", self._conversion_payload(quote, request_id))

    def validate_conversion(self, quote, request_id):
        """Run every local check create_conversion would, without any network call."""
        self._conversion_payload(quote, request_id)

    def _conversion_payload(self, quote, request_id):
        self._require_account_context()
        if not isinstance(quote, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id or ""):
            raise ValueError("Conversion requires a valid quote and unique request_id")
        quote_id = quote.get("quote_id")
        sell_currency, buy_currency = _currency(quote.get("sell_currency")), _currency(quote.get("buy_currency"))
        if not isinstance(quote_id, str) or not quote_id or sell_currency == buy_currency:
            raise ValueError("Invalid FX quote")
        dealt_currency = quote.get("dealt_currency")
        if dealt_currency == sell_currency:
            amount_field, amount = "sell_amount", quote.get("sell_amount")
        elif dealt_currency == buy_currency:
            amount_field, amount = "buy_amount", quote.get("buy_amount")
        else:
            raise ValueError("FX quote has no supported dealt currency")
        payload = {"request_id": request_id, "quote_id": quote_id,
                   "sell_currency": sell_currency, "buy_currency": buy_currency,
                   amount_field: format(_amount(amount), "f")}
        if quote.get("conversion_date"):
            payload["conversion_date"] = quote["conversion_date"]
        return payload

    def conversions_by_request_id(self, request_id):
        self._require_account_context()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id or ""):
            raise ValueError("Invalid conversion request_id")
        result = self.request("GET", "/api/v1/fx/conversions?" + urlencode({"request_id": request_id, "page_size": 10}))
        return [item for item in result.get("items", []) if item.get("request_id") == request_id]

    def conversion_balance_history(self, request_id):
        self._require_account_context()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id or ""):
            raise ValueError("Invalid conversion request_id")
        try:
            result = self.request("GET", "/api/v1/balances/history?" + urlencode({"request_id": request_id, "page_size": 200}))
        except AirwallexHTTPError as error:
            if error.status != 404 or error.code != 'not_found':
                raise
            # Sandbox can omit the request-ID index while posting actual wallet entries.
            conversions = self.conversions_by_request_id(request_id)
            if len(conversions) != 1 or not conversions[0].get('conversion_id'):
                raise ValueError('Cannot reconcile wallet history without one known conversion') from None
            source = conversions[0]['conversion_id']
            rows = []
            for page in range(10):
                result = self.request('GET', '/api/v1/balances/history?' + urlencode({'page_size': 200, 'page_num': page}))
                if not isinstance(result, dict) or not isinstance(result.get('items'), list):
                    raise ValueError('Airwallex returned invalid paginated wallet history')
                rows.extend(row for row in result['items'] if isinstance(row, dict)
                            and row.get('source_type') == 'CONVERSION' and row.get('source') == source)
                if not result.get('has_more') and not result.get('page_after'):
                    self.balance_history_lookup = 'SOURCE_MATCH_FROM_PAGINATED_HISTORY_AFTER_REQUEST_ID_404'
                    return rows
            raise ValueError('Wallet history exceeds the safe reconciliation page limit')
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise ValueError("Airwallex returned an invalid balance-history response")
        self.balance_history_lookup = 'REQUEST_ID'
        return result["items"]

    def _require_account_context(self):
        if not self.account_id:
            raise ValueError("Set AIRWALLEX_ACCOUNT_ID before accessing account-specific Treasury APIs")


def _currency(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError("Use an uppercase three-letter currency code")
    return value


def _amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Amount must be a positive decimal") from None
    if not amount.is_finite() or amount <= 0 or amount > Decimal("5000000"):
        raise ValueError("Amount must be positive and within Airwallex conversion limits")
    return amount


class AirwallexHTTPError(RuntimeError):
    def __init__(self, status, code=None):
        self.status = status
        self.code = code
        super().__init__(f"Airwallex sandbox HTTP {status}" + (f" ({code})" if code else '') + "; inspect the sandbox portal for details")
