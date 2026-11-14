"""Offline operational-database backup/restore. Never reads payer wallets or bank keys."""
import argparse
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def backup_or_restore(action,data_dir,archive):
    from touchstone.leases import exclusive
    from touchstone.ledger import Ledger
    directory=Path(data_dir).resolve()
    database=directory/'ledger.sqlite'
    archive=Path(archive).resolve()
    if archive==database or archive.is_relative_to(directory):
        raise ValueError('Backup must be outside the operational data directory')
    if action=='backup' and archive.exists():raise ValueError('Refusing to overwrite an existing backup')
    with exclusive(directory/'operator-owner.sqlite'):
        if action=='backup':
            if not database.is_file():raise ValueError('Operational database missing')
            archive.parent.mkdir(parents=True,exist_ok=True)
            with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as source:
                with closing(sqlite3.connect(archive)) as target:source.backup(target)
            archive.chmod(0o600)
        else:
            if database.exists():raise ValueError('Restore only into a new empty data directory')
            if not archive.is_file():raise ValueError('Backup missing')
            with closing(sqlite3.connect(archive.as_uri()+'?mode=ro',uri=True)) as source:
                if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid backup')
                if not source.execute("SELECT 1 FROM sqlite_master WHERE name='operational_jobs'").fetchone():raise ValueError('Not an operational backup')
                directory.mkdir(parents=True,exist_ok=True)
                with closing(sqlite3.connect(database)) as target:
                    source.backup(target)
                    target.execute('DELETE FROM operator_sessions')
                    target.commit()
            database.chmod(0o600)
            ledger=Ledger(database)
            if not ledger.audit()['valid']:raise ValueError('Audit chain invalid; do not start restored service')
            ledger.event('OPERATOR_RESTORED',{'backup_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                'sessions_revoked':True,'financial_dispatch_enabled':False})
    return {'action':action,'financial_operations':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['backup','restore'])
    parser.add_argument('--data-dir',required=True)
    parser.add_argument('--archive',required=True)
    args=parser.parse_args()
    import json
    print(json.dumps(backup_or_restore(args.action,args.data_dir,args.archive)))


if __name__=='__main__':main()
