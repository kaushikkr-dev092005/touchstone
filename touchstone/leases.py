"""Local process-owned leases. OS locks survive stalls and release on process death."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3


class LeaseBusy(RuntimeError):
    pass


@contextmanager
def exclusive(path):
    """No time-based stealing: an in-flight network call may outlive any timeout.

    The lock file is retained; deleting a live lock file would defeat ownership.
    This is local SQLite locking, not a multi-host distributed lease.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=.1, isolation_level=None)
    try:
        try:
            db.execute('PRAGMA locking_mode=EXCLUSIVE')
            db.execute('BEGIN EXCLUSIVE')
            db.execute('CREATE TABLE IF NOT EXISTS owner(id INTEGER)')
        except sqlite3.OperationalError:
            raise LeaseBusy('Another worker owns this scope; retry after it exits') from None
        yield
    finally:
        db.rollback()
        db.close()
