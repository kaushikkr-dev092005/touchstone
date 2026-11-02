"""Environment-only sandbox readiness. Never loads private data or prints values."""
import os
import re
import time

from .treasury import AirwallexSandbox, AirwallexHTTPError, BASE_URL


def inspect(probe_reads=False, client_factory=AirwallexSandbox):
    flags = {name: bool(os.environ.get(name)) for name in
             ("AIRWALLEX_CLIENT_ID", "AIRWALLEX_API_KEY", "AIRWALLEX_ACCOUNT_ID")}
    account_valid = bool(re.fullmatch(r"acct_[A-Za-z0-9]+", os.environ.get("AIRWALLEX_ACCOUNT_ID", "")))
    report = {"label": "BLOCKED", "observed_at": time.time(), "host": BASE_URL,
              "configuration_source": "PROCESS_ENVIRONMENT_ONLY", "configured": flags,
              "account_context_valid": account_valid, "authenticated": False,
              "reads": {}, "writes_performed": False, "money_moved": False,
              "conversion_write": {"label": "BLOCKED", "status": "UNVERIFIED",
                  "reason": "Read access cannot prove write scope; an approved quote/conversion is required"},
              "required_scopes": ["Core Resources / Balances / Read", "Transactional FX / Conversion / Write"],
              "scope_reference": "https://www.airwallex.com/docs/developer-tools/api/api-key-scopes"}
    missing = [name for name, present in flags.items() if not present]
    report["blockers"] = missing + ([] if account_valid else ["VALID_ACCOUNT_CONTEXT_REQUIRED"])
    if not probe_reads or report["blockers"]:
        report["read_probe"] = "NOT_REQUESTED" if not probe_reads else "BLOCKED_CONFIGURATION"
        return report
    try:
        client = client_factory()
        # Read only public response shape, never persist account balances or tokens.
        for name, path, shape in (
            ("balances", "/api/v1/balances/current", list),
            ("balance_history", "/api/v1/balances/history?page_size=10", dict),
            ("conversions", "/api/v1/fx/conversions?page_size=10", dict),
        ):
            try:
                raw = client.request("GET", path)
                valid = isinstance(raw, shape) and (shape is list or isinstance(raw.get("items"), list))
                report["reads"][name] = {"label": "MEASURED", "allowed": valid,
                                          "status": "PASS" if valid else "INVALID_RESPONSE"}
                report["authenticated"] = True
            except AirwallexHTTPError as error:
                report["reads"][name] = {"label": "MEASURED", "allowed": False,
                                          "http_status": error.status, "code": error.code}
            except (RuntimeError, ValueError, KeyError, TypeError):
                report["reads"][name] = {"label": "BLOCKED", "allowed": False, "status": "UNAVAILABLE"}
        report["read_probe"] = "PASS" if all(r["allowed"] for r in report["reads"].values()) else "BLOCKED"
        report["label"] = "MEASURED" if report["read_probe"] == "PASS" else "BLOCKED"
        report["blockers"] += [name + "_READ_UNVERIFIED" for name, r in report["reads"].items() if not r["allowed"]]
    except ValueError:
        report["blockers"].append("INVALID_SANDBOX_CONFIGURATION")
        report["read_probe"] = "BLOCKED_CONFIGURATION"
    return report
