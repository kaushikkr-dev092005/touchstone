"""Independent durable mock rail. NOT a cryptographic x402 implementation."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from .ledger import ClosingConnection, PolicyError, canonical


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

    def lookup(self, key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM receipts WHERE key=?", (key,)).fetchone()
            return {**dict(row), "output": json.loads(row["output"])} if row else None

    def pay(self, key, quote, output_factory):
        # A real adapter MUST query settlements and recover the same request before rerouting.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM receipts WHERE key=?", (key,)).fetchone()
            if row:
                if row["amount"] != quote.price or row["quote_id"] != quote.id or row["provider"] != quote.provider:
                    raise PolicyError("Rail idempotency conflict")
                return {**dict(row), "output": json.loads(row["output"])}
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


# Export the real bridge here for callers that previously imported the placeholder.
from .metal import MetalRail
