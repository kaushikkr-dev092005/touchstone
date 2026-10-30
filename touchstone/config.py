"""Ignored local configuration, with process environment taking precedence."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
LOCAL_CONFIG = ROOT / "data/local-config.json"
FUNDING_WALLET = ROOT / "data/metal/funding-wallet.json"
KEYS = {"METAL_RPC_URL", "METAL_PROVIDER_URL", "AGENT_PRIVATE_KEY", "AIRWALLEX_CLIENT_ID",
        "AIRWALLEX_API_KEY", "AIRWALLEX_ACCOUNT_ID", "AIRWALLEX_CHECKOUT_SUCCESS_URL",
        "METAL_MAX_PRICE_USD", "METAL_JOB_BUDGET_USD", "LOCAL_INFERENCE_URL", "LOCAL_MODEL"}


def load_local():
    if LOCAL_CONFIG.exists():
        raw = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or any(k not in KEYS or not isinstance(v, str) for k, v in raw.items()):
            raise ValueError("Invalid local configuration; values must be supported string settings")
        for key, value in raw.items():
            if value:
                os.environ.setdefault(key, value)
    if not os.environ.get("AGENT_PRIVATE_KEY") and FUNDING_WALLET.exists():
        wallet = json.loads(FUNDING_WALLET.read_text(encoding="utf-8"))
        os.environ["AGENT_PRIVATE_KEY"] = wallet["private_key"]


def save_rpc(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "rpc-testnet.metalntwx.com" or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Use an HTTPS Metal testnet RPC endpoint without embedded login or fragment")
    raw = json.loads(LOCAL_CONFIG.read_text(encoding="utf-8")) if LOCAL_CONFIG.exists() else {}
    raw["METAL_RPC_URL"] = url
    LOCAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CONFIG.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    LOCAL_CONFIG.chmod(0o600)
