"""Sandbox-only Airwallex transport; writes are owned by the durable hold workflow."""
import json
import os
import urllib.error
import urllib.request
import time
import re
from urllib.parse import urlencode

BASE_URL = "https://api.sandbox.airwallex.com"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Refusing to forward sandbox credentials through a redirect")


class AirwallexSandbox:
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

    def request(self, method, path, body=None, api_version=None):
        if not self.token or time.monotonic() >= self.token_until:
            login = self._request("/api/v1/authentication/login", "POST", self.login_headers())
            self.token = login["token"]
            self.token_until = time.monotonic() + 25 * 60
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
        login = self._request("/api/v1/authentication/login", "POST", self.login_headers())
        token = login["token"]
        headers = {"Authorization": "Bearer " + token}
        reads, errors = {}, {}
        for name, path in (("balance_read", '/api/v1/balances/current'), ("global_accounts_read", '/api/v1/global_accounts')):
            try:
                reads[name] = isinstance(self._request(path, headers=headers), (list, dict))
            except AirwallexHTTPError as error:
                reads[name] = False
                errors[name] = {"http_status": error.status, "reason": "Check account selection and scoped key permissions"}
        if self.account_id:
            checkout_headers = {**headers, "x-api-version": "2026-05-29"}
            checkout_path = "/api/v1/checkout/checkout_sessions?" + urlencode({"account_id": self.account_id, "page_size": 1})
            try:
                result = self._request(checkout_path, headers=checkout_headers)
                reads["checkout_sessions_read"] = isinstance(result, dict) and isinstance(result.get("items"), list)
            except AirwallexHTTPError as error:
                reads["checkout_sessions_read"] = False
                errors["checkout_sessions_read"] = {"http_status": error.status,
                    "reason": "Check Checkout Sessions read permission and API availability"}
        else:
            reads["checkout_sessions_read"] = False
            errors["checkout_sessions_read"] = {"reason": "Set AIRWALLEX_ACCOUNT_ID to check Checkout Sessions access"}
        # Do not print credentials, tokens, bank account details, or raw responses.
        return {"mode": "SANDBOX", "host": BASE_URL, "authenticated": True,
                **reads, "read_errors": errors, "account_context_configured": bool(self.account_id),
                "checkout_sessions_write_verified": False, "writes_performed": False, "dashboard_mode_changed": False}


class AirwallexHTTPError(RuntimeError):
    def __init__(self, status, code=None):
        self.status = status
        self.code = code
        super().__init__(f"Airwallex sandbox HTTP {status}" + (f" ({code})" if code else '') + "; inspect the sandbox portal for details")
