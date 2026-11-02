"""Python/SDK process bridge. Financial uncertainty never becomes non-payment."""
from dataclasses import dataclass, asdict
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import base64
from urllib.parse import urlparse

from .config import ROOT, load_local


class PaymentPending(RuntimeError):
    pass


def dollars(micros):
    if type(micros) is not int or micros < 0:
        raise ValueError("Money must be nonnegative integer micro-USD")
    return format(Decimal(micros) / 1000000, '.6f')


def node_executable():
    manifest = ROOT / ".tools/node/manifest.json"
    node = json.loads(manifest.read_text())["executable"] if manifest.exists() else shutil.which("node")
    if not node:
        raise RuntimeError("Install portable Node: python tools/setup_node.py")
    return node


@dataclass(frozen=True)
class MetalQuote:
    id: str
    provider: str
    price: int
    expires_at: float
    terms: dict
    latency_ms: int = 0
    mode: str = "TESTNET"
    queue_depth: int = 0
    latency_samples: int = 0

    def public(self):
        return asdict(self)


class MetalRail:
    mode = "TESTNET"

    def __init__(self, job, provider_url=None, price_cap=50000, budget=500000, transport=None):
        load_local()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", job):
            raise ValueError("Invalid wallet job ID")
        self.job = job
        self.provider_url = provider_url or os.environ.get("METAL_PROVIDER_URL")
        if not self.provider_url or not os.environ.get("METAL_RPC_URL"):
            raise RuntimeError("Metal RPC/provider not configured; use local settings or environment")
        self.price_cap, self.budget = price_cap, budget
        if not 0 < price_cap <= budget:
            raise ValueError("Price cap must fit the payment budget")
        self.transport = transport or self._process

    def _process(self, request):
        try:
            child_env = os.environ.copy()
            for name in list(child_env):
                if name.startswith(("AIRWALLEX_", "ANTHROPIC_")):
                    child_env.pop(name)
            process = subprocess.run([node_executable(), str(ROOT / 'integrations/metal/bridge.mjs')],
                                     input=json.dumps(request), text=True, capture_output=True, timeout=95,
                                     cwd=ROOT, env=child_env)
            result = json.loads(process.stdout)
            if process.returncode or not result.get("ok"):
                raise ValueError("Sidecar refused operation")
            return result["result"]
        except (OSError, ValueError, subprocess.SubprocessError):
            if request.get("command") == "quote":
                raise RuntimeError("Metal quote unavailable; no purchase was dispatched") from None
            raise PaymentPending("Metal operation is unresolved; preserve the job and recover before sending another purchase") from None

    def invoke(self, command, **fields):
        return self.transport({"command": command, "job": self.job, "provider_url": self.provider_url,
                               "max_price": dollars(self.price_cap), "budget": dollars(self.budget), **fields})

    def quote(self, provider_url=None):
        provider_url = provider_url or self.provider_url
        raw = self.invoke("quote", provider_url=provider_url)
        base = int(raw["offer"]["amount"])
        if base <= 0 or base % 10**12:
            raise ValueError("Metal quote is not exact micro-USD")
        price = base // 10**12
        if price > self.price_cap or raw["url"] != provider_url or raw["expires_at"] <= time.time()*1000:
            raise ValueError("Metal quote exceeds the mandate or is expired")
        identity = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        latency_ms, queue_depth = raw.get("latency_ms", 0), raw.get("queue_depth", 0)
        latency_samples = raw.get("latency_samples", 0)
        if (type(latency_ms) is not int or latency_ms < 0 or type(queue_depth) is not int or queue_depth < 0
                or type(latency_samples) is not int or latency_samples < 0):
            raise ValueError("Metal provider load metadata is invalid")
        provider_id = raw.get("provider_id", "metal-provider")
        if provider_id not in {"metal-provider", "local-gpu", "hosted-premium"}:
            raise ValueError("Metal provider identifier is not approved")
        return MetalQuote(identity, provider_id, price, raw["expires_at"]/1000, raw,
                          latency_ms=latency_ms, queue_depth=queue_depth, latency_samples=latency_samples)

    def pay(self, key, quote):
        if quote.price > self.price_cap or not quote.terms.get("url"):
            raise ValueError("Reserved quote differs from the mandate")
        return self.invoke("pay", id=key, quote=quote.terms, provider_url=quote.terms["url"])

    def lookup(self, key):
        return self.invoke("lookup", id=key)

    def recover(self, key, quote=None):
        terms = quote.get("terms") if isinstance(quote, dict) else getattr(quote, "terms", None)
        provider_url = terms.get("url") if isinstance(terms, dict) else self.provider_url
        return self.invoke("recover", id=key, provider_url=provider_url)

    def balance(self):
        return self.invoke("balance")

    def deposit(self, micros):
        return self.invoke("deposit", dollars=dollars(micros))

    def withdraw(self):
        return self.invoke("withdraw")


def task_resource_url(origin, task):
    parsed = urlparse(origin)
    if (parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}
            or (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}))):
        raise ValueError("Provider origin must be HTTPS or loopback HTTP without a path or credentials")
    public = json.dumps(task.public(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if len(public) > 12000:
        raise ValueError("Provider task is too large")
    digest = hashlib.sha256(public).hexdigest()
    encoded = base64.urlsafe_b64encode(public).decode().rstrip("=")
    return origin.rstrip("/") + "/inference/" + digest + "?task=" + encoded
