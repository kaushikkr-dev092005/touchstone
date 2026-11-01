"""Integer-money accounting, serializable reservations, and durable audit events."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid


class PolicyError(Exception):
    pass


class ClosingConnection(sqlite3.Connection):
    """sqlite's native context manager commits but does not close its handle."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def payment_key(job_id, step_id, attempt):
    return hashlib.sha256(f"{job_id}:{step_id}:{attempt}".encode()).hexdigest()


class Ledger:
    def __init__(self, path="data/ledger.sqlite"):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY CHECK(id=1), halted INTEGER NOT NULL);
            INSERT OR IGNORE INTO control VALUES(1,0);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, float_total INTEGER NOT NULL CHECK(float_total>=0));
            CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id), seed INTEGER NOT NULL,
              policy TEXT NOT NULL, status TEXT NOT NULL, budget INTEGER NOT NULL, hold INTEGER NOT NULL,
              price_cap INTEGER NOT NULL, allocation INTEGER NOT NULL, rail_spent INTEGER NOT NULL DEFAULT 0,
              spent INTEGER NOT NULL DEFAULT 0, captured INTEGER NOT NULL DEFAULT 0,
              released INTEGER NOT NULL DEFAULT 0, expires_at REAL NOT NULL, tasks TEXT NOT NULL,
              mandate_version INTEGER NOT NULL DEFAULT 1,
              CHECK(spent>=0 AND spent<=budget AND budget<=hold), CHECK(captured<=hold));
            CREATE TABLE IF NOT EXISTS attempts(
              key TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), step_id TEXT NOT NULL,
              attempt INTEGER NOT NULL, state TEXT NOT NULL, quote TEXT NOT NULL,
              provider TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>0), verify_cost INTEGER NOT NULL,
              output TEXT, score REAL, passed INTEGER, reason TEXT, receipt TEXT,
              UNIQUE(job_id,step_id,attempt));
            CREATE TABLE IF NOT EXISTS payments(
              key TEXT PRIMARY KEY REFERENCES attempts(key), receipt TEXT UNIQUE NOT NULL,
              amount INTEGER NOT NULL CHECK(amount>0));
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, kind TEXT NOT NULL,
              payload TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT UNIQUE NOT NULL);
            CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
              BEGIN SELECT RAISE(ABORT,'audit events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
              BEGIN SELECT RAISE(ABORT,'audit events are append-only'); END;
            """)
            columns = {r["name"] for r in db.execute("PRAGMA table_info(attempts)")}
            if "verdict" not in columns:
                db.execute("ALTER TABLE attempts ADD COLUMN verdict TEXT")
            job_columns = {r["name"] for r in db.execute("PRAGMA table_info(jobs)")}
            if "mandate_version" not in job_columns:
                db.execute("ALTER TABLE jobs ADD COLUMN mandate_version INTEGER NOT NULL DEFAULT 1")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def tx(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _event(self, db, kind, payload):
        ts = time.time()
        previous = db.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
        previous = previous[0] if previous else "0" * 64
        data = canonical(payload)
        digest = hashlib.sha256(canonical([ts, kind, data, previous]).encode()).hexdigest()
        db.execute("INSERT INTO events(ts,kind,payload,previous_hash,hash) VALUES(?,?,?,?,?)", (ts, kind, data, previous, digest))

    def event(self, kind, payload):
        with self.tx() as db:
            self._event(db, kind, payload)

    def create_run(self, specs, float_total=1500000):
        if type(float_total) is not int or float_total <= 0:
            raise ValueError("Float must be a positive integer in micro-USD")
        run_id = uuid.uuid4().hex[:12]
        if not specs or sum(s["allocation"] for s in specs) > float_total:
            raise PolicyError("Initial allocations exceed the run's float")
        with self.tx() as db:
            db.execute("INSERT INTO runs VALUES(?,?)", (run_id, float_total))
            for i, s in enumerate(specs):
                hold, cap, allocation = s["hold"], s["price_cap"], s["allocation"]
                if any(type(v) is not int or v <= 0 for v in (hold, cap, allocation)) or allocation > hold:
                    raise ValueError("Invalid hold, cap or allocation")
                job_id = f"{run_id}-{i+1}"
                db.execute("""INSERT INTO jobs(id,run_id,seed,policy,status,budget,hold,price_cap,allocation,expires_at,tasks)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                           (job_id, run_id, s["seed"], s["policy"], "RUNNING", hold, hold, cap, allocation,
                            time.time() + 86400, canonical(s["tasks"])))
                self._event(db, "HOLD_AUTHORIZED", {"job_id": job_id, "hold": hold, "allocation": allocation,
                    "mandate_version": 1, "mode": "SIMULATED"})
        return run_id

    def get_job(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def jobs(self, run_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM jobs WHERE run_id=? ORDER BY id", (run_id,)) if run_id else db.execute("SELECT * FROM jobs ORDER BY rowid DESC")
            return [dict(r) for r in rows]

    def approve_mandate_increase(self, job_id, expected_version, hold, budget, price_cap, allocation, approver, reason):
        values = (hold, budget, price_cap, allocation)
        if any(type(value) is not int or value <= 0 for value in values):
            raise ValueError("Approved mandate limits must be positive integer micro-USD")
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("Expected mandate version must be a positive integer")
        if not isinstance(approver, str) or not approver.strip() or len(approver.strip()) > 100:
            raise ValueError("Approver name is required and limited to 100 characters")
        if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 300:
            raise ValueError("Approval reason is required and limited to 300 characters")
        with self.tx() as db:
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise PolicyError("Unknown job")
            if job["status"] != "PAUSED_POLICY":
                raise PolicyError("A mandate increase can be approved only while the job is policy-paused")
            if expected_version != job["mandate_version"]:
                raise PolicyError("Mandate version changed; refresh before approving")
            if db.execute("SELECT 1 FROM attempts WHERE job_id=? AND state IN ('RESERVED','PAID')", (job_id,)).fetchone():
                raise PolicyError("Cannot revise a mandate while a purchase outcome is unresolved")
            if hold <= job["hold"] or budget <= job["budget"]:
                raise PolicyError("A new version must increase both the hold and job budget")
            if budget > hold or allocation > hold or price_cap > budget:
                raise PolicyError("New mandate limits are inconsistent")
            if hold > 10_000_000:
                raise PolicyError("Simulated hold cannot exceed USD 10")
            if allocation < job["rail_spent"]:
                raise PolicyError("Allocation cannot be below provider spend")
            run = db.execute("SELECT float_total FROM runs WHERE id=?", (job["run_id"],)).fetchone()
            allocated = db.execute("SELECT COALESCE(SUM(allocation),0) FROM jobs WHERE run_id=?", (job["run_id"],)).fetchone()[0]
            if allocated - job["allocation"] + allocation > run["float_total"]:
                raise PolicyError("Approved allocation exceeds the run's existing operator float")
            old = {name: job[name] for name in ("hold", "budget", "price_cap", "allocation")}
            new_version = job["mandate_version"] + 1
            db.execute("UPDATE jobs SET hold=?,budget=?,price_cap=?,allocation=?,mandate_version=? WHERE id=?",
                       (hold, budget, price_cap, allocation, new_version, job_id))
            self._event(db, "MANDATE_INCREASE_APPROVED", {
                "job_id": job_id, "previous_version": job["mandate_version"], "mandate_version": new_version,
                "previous_limits": old,
                "approved_limits": {"hold": hold, "budget": budget, "price_cap": price_cap, "allocation": allocation},
                "approver": approver.strip(), "reason": reason.strip(), "mode": "SIMULATED"})
            return {"job_id": job_id, "mandate_version": new_version, "status": job["status"],
                    "hold": hold, "budget": budget, "price_cap": price_cap, "allocation": allocation,
                    "mode": "SIMULATED"}

    def attempts(self, job_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM attempts WHERE job_id=? ORDER BY rowid", (job_id,)) if job_id else db.execute("SELECT * FROM attempts ORDER BY rowid")
            return [dict(r) for r in rows]

    def reserve(self, job_id, task, attempt, quote, verify_cost):
        key = payment_key(job_id, task.id, attempt)
        with self.tx() as db:
            previous = db.execute("SELECT * FROM attempts WHERE key=?", (key,)).fetchone()
            if previous:
                if canonical(quote.public()) != previous["quote"] or verify_cost != previous["verify_cost"]:
                    raise PolicyError("Idempotency key cannot change purchase terms")
                return key
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job or job["status"] != "RUNNING" or db.execute("SELECT halted FROM control").fetchone()[0]:
                raise PolicyError("Payments are halted or job is not running")
            if time.time() >= job["expires_at"] or time.time() >= quote.expires_at:
                raise PolicyError("Mandate or quote expired")
            if quote.provider not in {"economy", "balanced", "premium", "metal-provider"} or not 0 <= attempt < 3:
                raise PolicyError("Provider or attempt is outside mandate")
            if type(quote.price) is not int or type(verify_cost) is not int or quote.price <= 0 or verify_cost < 0:
                raise PolicyError("Money must be integer micro-USD")
            if quote.price > job["price_cap"]:
                raise PolicyError("Per-call price cap exceeded")
            public_tasks = json.loads(job["tasks"])
            if task.public() not in public_tasks:
                raise PolicyError("Task is outside the approved job")
            if db.execute("SELECT 1 FROM attempts WHERE job_id=? AND step_id=? AND (passed=1 OR state IN ('RESERVED','PAID'))", (job_id, task.id)).fetchone():
                raise PolicyError("Step is accepted or has an unresolved purchase")
            reserved = db.execute("SELECT COALESCE(SUM(price+verify_cost),0) FROM attempts WHERE job_id=? AND state IN ('RESERVED','PAID')", (job_id,)).fetchone()[0]
            total = quote.price + verify_cost
            if job["spent"] + reserved + total > min(job["hold"], job["budget"]):
                raise PolicyError("Customer hold or budget would be exceeded")
            rail_reserved = db.execute("SELECT COALESCE(SUM(price),0) FROM attempts WHERE job_id=? AND state='RESERVED'", (job_id,)).fetchone()[0]
            shortfall = job["rail_spent"] + rail_reserved + quote.price - job["allocation"]
            if shortfall > 0:
                run = db.execute("SELECT float_total FROM runs WHERE id=?", (job["run_id"],)).fetchone()[0]
                allocated = db.execute("SELECT SUM(allocation) FROM jobs WHERE run_id=?", (job["run_id"],)).fetchone()[0]
                topup = min(max(shortfall, 100000), run - allocated, job["hold"] - job["allocation"])
                if topup < shortfall:
                    raise PolicyError("Operator float exhausted; approval or new float required")
                db.execute("UPDATE jobs SET allocation=allocation+? WHERE id=?", (topup, job_id))
                self._event(db, "FLOAT_TOPUP", {"job_id": job_id, "amount": topup, "mode": "SIMULATED"})
            db.execute("INSERT INTO attempts(key,job_id,step_id,attempt,state,quote,provider,price,verify_cost) VALUES(?,?,?,?,?,?,?,?,?)",
                       (key, job_id, task.id, attempt, "RESERVED", canonical(quote.public()), quote.provider, quote.price, verify_cost))
            self._event(db, "RESERVED", {"job_id": job_id, "step_id": task.id, "key": key, "quote_id": quote.id, "amount": total})
        return key

    def assert_can_pay(self, key):
        with self.connect() as db:
            row = db.execute("SELECT a.*,j.status,j.expires_at FROM attempts a JOIN jobs j ON a.job_id=j.id WHERE key=?", (key,)).fetchone()
            if not row or row["state"] != "RESERVED" or row["status"] != "RUNNING" or db.execute("SELECT halted FROM control").fetchone()[0]:
                raise PolicyError("Payment dispatch is stopped")
            if time.time() >= row["expires_at"] or time.time() >= json.loads(row["quote"])["expires_at"]:
                raise PolicyError("Mandate or quote expired before dispatch")

    def record_paid(self, key, receipt):
        with self.tx() as db:
            row = db.execute("SELECT * FROM attempts WHERE key=?", (key,)).fetchone()
            if not row or receipt["key"] != key or receipt["amount"] != row["price"] or receipt["quote_id"] != json.loads(row["quote"])["id"] or receipt["provider"] != row["provider"]:
                raise PolicyError("Receipt does not match reserved purchase")
            existing = db.execute("SELECT receipt FROM payments WHERE key=?", (key,)).fetchone()
            if existing:
                if existing[0] != receipt["id"]:
                    raise PolicyError("Conflicting receipt")
                return
            if row["state"] != "RESERVED":
                raise PolicyError("No active reservation")
            db.execute("INSERT INTO payments VALUES(?,?,?)", (key, receipt["id"], receipt["amount"]))
            db.execute("UPDATE attempts SET state='PAID',receipt=? WHERE key=?", (receipt["id"], key))
            db.execute("UPDATE jobs SET rail_spent=rail_spent+? WHERE id=?", (receipt["amount"], row["job_id"]))
            self._event(db, "PAID", {"job_id": row["job_id"], "key": key, "receipt": receipt["id"], "amount": receipt["amount"], "mode": "SIMULATED"})

    def finish_attempt(self, key, output, verdict):
        with self.tx() as db:
            row = db.execute("SELECT * FROM attempts WHERE key=?", (key,)).fetchone()
            if not row or row["state"] != "PAID":
                return
            state = "VERIFIED_OK" if verdict["passed"] else "VERIFIED_FAIL"
            db.execute("UPDATE attempts SET state=?,output=?,score=?,passed=?,reason=?,verdict=? WHERE key=?",
                       (state, canonical(output), verdict["score"], int(verdict["passed"]), verdict["reason"], canonical(verdict), key))
            db.execute("UPDATE jobs SET spent=spent+? WHERE id=?", (row["price"] + row["verify_cost"], row["job_id"]))
            self._event(db, state, {"job_id": row["job_id"], "step_id": row["step_id"], "key": key, "provider": row["provider"], "score": verdict["score"], "reason": verdict["reason"], "method": verdict.get("method", "source-numeric"), "retryable": verdict.get("retryable", True)})

    def void(self, key, reason):
        with self.tx() as db:
            row = db.execute("SELECT job_id FROM attempts WHERE key=? AND state='RESERVED'", (key,)).fetchone()
            if row:
                db.execute("UPDATE attempts SET state='VOID',reason=? WHERE key=?", (reason, key))
                self._event(db, "RESERVATION_VOIDED", {"key": key, "reason": reason})

    def status(self, job_id, state, reason=""):
        with self.tx() as db:
            db.execute("UPDATE jobs SET status=? WHERE id=?", (state, job_id))
            self._event(db, state, {"job_id": job_id, "reason": reason})

    def settle_job(self, job_id):
        with self.tx() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row["status"] == "COMPLETED":
                return
            if db.execute("SELECT 1 FROM attempts WHERE job_id=? AND state IN ('RESERVED','PAID')", (job_id,)).fetchone():
                raise PolicyError("Cannot capture while payment outcome is unresolved")
            db.execute("UPDATE jobs SET status='COMPLETED',captured=spent,released=hold-spent,allocation=rail_spent WHERE id=?", (job_id,))
            self._event(db, "HOLD_CAPTURED", {"job_id": job_id, "captured": row["spent"], "released": row["hold"] - row["spent"], "unused_float_returned": row["allocation"] - row["rail_spent"], "mode": "SIMULATED"})

    def halt(self, reason="Operator halted new payment dispatches; in-flight charges require reconciliation"):
        with self.tx() as db:
            db.execute("UPDATE control SET halted=1")
            db.execute("UPDATE jobs SET status='PAUSED_KILL' WHERE status='RUNNING'")
            self._event(db, "KILL_SWITCH", {"reason": reason})

    def resume(self):
        with self.tx() as db:
            db.execute("UPDATE control SET halted=0")
            db.execute("UPDATE jobs SET status='RUNNING' WHERE status IN ('PAUSED_KILL','PAUSED_POLICY','PAUSED_RECOVERY')")
            self._event(db, "OPERATOR_RESUME", {"policy_changed": False})

    def audit(self):
        with self.connect() as db:
            previous = "0" * 64
            rows = db.execute("SELECT * FROM events ORDER BY id").fetchall()
            for r in rows:
                digest = hashlib.sha256(canonical([r["ts"], r["kind"], r["payload"], previous]).encode()).hexdigest()
                if r["previous_hash"] != previous or r["hash"] != digest:
                    return {"valid": False, "events": len(rows), "broken_at": r["id"]}
                previous = digest
            return {"valid": True, "events": len(rows), "head": previous}

    def events(self, after=0, limit=100):
        with self.connect() as db:
            return [{**dict(r), "payload": json.loads(r["payload"])} for r in db.execute("SELECT * FROM events WHERE id>? ORDER BY id LIMIT ?", (after, limit))]
