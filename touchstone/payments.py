"""Independent durable mock rail. NOT a cryptographic x402 implementation."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from .ledger import ClosingConnection, PolicyError, canonical
from .metal import MetalRail, PaymentPending, task_resource_url


class MockRail:
    mode = "SIMULATED"

    def __init__(self, path="data/rail.sqlite"):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS receipts(key TEXT PRIMARY KEY, id TEXT UNIQUE NOT NULL,
              amount INTEGER NOT NULL, provider TEXT NOT NULL, quote_id TEXT NOT NULL,
              output TEXT NOT NULL, latency_ms INTEGER NOT NULL);""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        return db

    def lookup(self, key, quote=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM receipts WHERE key=?", (key,)).fetchone()
            return ({**dict(row), "output": json.loads(row["output"]), "state": "PAID"}
                    if row else {"state": "NOT_DISPATCHED", "authoritative": True})

    def pay(self, key, quote, output_factory):
        # A real adapter MUST query settlements and recover the same request before rerouting.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM receipts WHERE key=?", (key,)).fetchone()
            if row:
                if row["amount"] != quote.price or row["quote_id"] != quote.id or row["provider"] != quote.provider:
                    raise PolicyError("Rail idempotency conflict")
                return {**dict(row), "output": json.loads(row["output"]), "state": "PAID"}
            if time.time() >= quote.expires_at:
                raise PolicyError("Payment challenge expired")
            output = output_factory()
            receipt_id = "mock_" + hashlib.sha256(key.encode()).hexdigest()[:24]
            db.execute("INSERT INTO receipts VALUES(?,?,?,?,?,?,?)",
                       (key, receipt_id, quote.price, quote.provider, quote.id, canonical(output), quote.latency_ms))
        return self.lookup(key)

    def receipts(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT key,id,amount,provider,quote_id,latency_ms FROM receipts ORDER BY rowid")]


    def recover(self, key, quote=None):
        return self.lookup(key)


class MetalEngineRail:
    """Metal adapter implementing the engine's quote/pay/lookup/recover contract."""
    mode = "TESTNET"

    def __init__(self, job, provider_url=None, price_cap=50000, budget=500000, client=None, expected_provider_ids=None):
        if isinstance(provider_url, str):
            provider_urls = [provider_url]
        else:
            provider_urls = list(provider_url or [])
        if not provider_urls:
            provider_urls = [None]
        self.provider_urls = provider_urls
        self.expected_provider_ids = list(expected_provider_ids) if expected_provider_ids else None
        if self.expected_provider_ids and len(self.expected_provider_ids) != len(provider_urls):
            raise ValueError("Expected provider identities must match the configured provider origins")
        self.provider_url = provider_urls[0]
        self.last_quote_errors = []
        self.client = client or MetalRail(job, self.provider_url, price_cap, budget)

    def quote_for_task(self, task):
        """Return every usable live quote; an unusable origin is skipped, never paid.

        An expired, over-cap, malformed or identity-mismatched quote makes only
        that provider unavailable. No payment is dispatched on any of these
        paths, so they must not abort the other tier or the whole engine run.
        The reasons are kept (class name and message only) for operator review.
        """
        offers = []
        self.last_quote_errors = []
        for index, provider_url in enumerate(self.provider_urls):
            origin = provider_url or self.client.provider_url
            try:
                offer = self.client.quote(task_resource_url(origin, task))
                if self.expected_provider_ids and offer.provider != self.expected_provider_ids[index]:
                    raise PolicyError("Provider identity does not match its configured origin")
                offers.append(offer)
            except (RuntimeError, ValueError, KeyError, TypeError, PolicyError) as error:
                self.last_quote_errors.append({"origin_index": index, "error": type(error).__name__,
                                               "detail": str(error)[:200]})
        return offers

    def pay(self, key, quote, output_factory=None):
        result = self.client.pay(key, quote)
        normalized = self._normalize(result, key, quote)
        if normalized.get("state") != "PAID":
            raise PaymentPending("Metal payment or delivery remains unresolved; preserve the reservation and recover")
        return normalized

    def lookup(self, key, quote=None):
        result = self.client.lookup(key)
        if result.get("state") == "NOT_DISPATCHED":
            return {"state": "NOT_DISPATCHED", "authoritative": True}
        return self._normalize(result.get("result") or {}, key, quote, result.get("state"))

    def recover(self, key, quote=None):
        result = self.client.recover(key)
        return self._normalize(result or {}, key, quote)

    def receipts(self):
        rows = self.client.invoke("receipts")
        result = []
        for row in rows:
            receipt = row.get("receipt")
            if not receipt:
                continue
            amount = int(receipt["invoice"]["amount"])
            if amount <= 0 or amount % 10**12:
                raise PolicyError("Metal receipt is not exact micro-USD")
            quote_id = hashlib.sha256(json.dumps(row["terms"], sort_keys=True).encode()).hexdigest()
            result.append({"key": row["key"], "id": receipt["id"], "amount": amount // 10**12,
                           "provider": row["terms"].get("provider_id", "metal-provider"), "quote_id": quote_id})
        return result

    @staticmethod
    def _normalize(result, key, quote=None, prior_state=None):
        state = prior_state or result.get("state")
        if state == "UNPAID_CONFIRMED":
            return {"state": state, "authoritative": True}
        if state == "NOT_DISPATCHED":
            return {"state": state, "authoritative": True}
        if state not in {"DELIVERED", "PAID_OUTPUT_MISSING"}:
            return {"state": "UNKNOWN", "authoritative": False}
        receipt = result.get("receipt")
        if not isinstance(receipt, dict) or not isinstance(receipt.get("invoice"), dict):
            return {"state": "UNKNOWN", "authoritative": False}
        try:
            base_amount = int(receipt["invoice"]["amount"])
            if base_amount <= 0 or base_amount % 10**12:
                raise ValueError
            amount = base_amount // 10**12
        except (KeyError, TypeError, ValueError):
            raise PolicyError("Metal receipt amount cannot be normalized") from None
        quote_id = quote.get("id") if isinstance(quote, dict) else getattr(quote, "id", None)
        expected_price = quote.get("price") if isinstance(quote, dict) else getattr(quote, "price", None)
        if quote_id is None or expected_price != amount:
            raise PolicyError("Metal receipt differs from the reserved quote")
        output = None
        body = (result.get("output") or {}).get("body")
        if isinstance(body, dict):
            output = body.get("output")
        provider = quote.get("provider") if isinstance(quote, dict) else getattr(quote, "provider", None)
        if provider not in {"metal-provider", "local-gpu", "hosted-premium"}:
            raise PolicyError("Metal receipt has no approved provider identity")
        metadata = body.get("provider_metadata") if isinstance(body, dict) else None
        return {"state": "PAID" if state == "DELIVERED" and output is not None else "PAID_OUTPUT_MISSING",
                "key": key, "id": receipt["id"], "amount": amount, "provider": provider,
                "quote_id": quote_id, "output": output, "provider_metadata": metadata, "mode": "TESTNET"}


class CompositeRail:
    """One engine rail contract over the simulated rail and an optional live tier."""
    mode = "MIXED"

    def __init__(self, simulated, metal=None):
        self.simulated, self.metal = simulated, metal

    def quote_for_task(self, task):
        return self.metal.quote_for_task(task) if self.metal else None

    def _rail(self, quote):
        provider = quote.get("provider") if isinstance(quote, dict) else getattr(quote, "provider", None)
        if provider in {"metal-provider", "local-gpu", "hosted-premium"}:
            if not self.metal:
                raise PolicyError("Metal provider is not enabled")
            return self.metal
        return self.simulated

    def pay(self, key, quote, output_factory=None):
        return self._rail(quote).pay(key, quote, output_factory)

    def lookup(self, key, quote=None):
        return self._rail(quote).lookup(key, quote)

    def recover(self, key, quote=None):
        return self._rail(quote).recover(key, quote)

    def receipts(self):
        return self.simulated.receipts() + (self.metal.receipts() if self.metal else [])
