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
    mode: str = "TESTNET"

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
            process = subprocess.run([node_executable(), str(ROOT / 'integrations/metal/bridge.mjs')],
                                     input=json.dumps(request), text=True, capture_output=True, timeout=95,
                                     cwd=ROOT, env=os.environ.copy())
            result = json.loads(process.stdout)
            if process.returncode or not result.get("ok"):
                raise ValueError("Sidecar refused operation")
            return result["result"]
        except (OSError, ValueError, subprocess.SubprocessError):
            raise PaymentPending("Metal operation is unresolved; preserve the job and recover before sending another purchase") from None

    def invoke(self, command, **fields):
        return self.transport({"command": command, "job": self.job, "provider_url": self.provider_url,
                               "max_price": dollars(self.price_cap), "budget": dollars(self.budget), **fields})

    def quote(self):
        raw = self.invoke("quote")
        base = int(raw["offer"]["amount"])
        if base <= 0 or base % 10**12:
            raise ValueError("Metal quote is not exact micro-USD")
        price = base // 10**12
        if price > self.price_cap or raw["url"] != self.provider_url or raw["expires_at"] <= time.time()*1000:
            raise ValueError("Metal quote exceeds the mandate or is expired")
        identity = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        return MetalQuote(identity, "metal-provider", price, raw["expires_at"]/1000, raw)

    def pay(self, key, quote):
        if quote.price > self.price_cap or quote.terms["url"] != self.provider_url:
            raise ValueError("Reserved quote differs from the mandate")
        return self.invoke("pay", id=key, quote=quote.terms)

    def lookup(self, key):
        return self.invoke("lookup", id=key)

    def recover(self, key):
        return self.invoke("recover", id=key)

    def balance(self):
        return self.invoke("balance")

    def deposit(self, micros):
        return self.invoke("deposit", dollars=dollars(micros))

    def withdraw(self):
        return self.invoke("withdraw")
