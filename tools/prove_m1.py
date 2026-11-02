"""Save MOCK M1 adapter evidence in a temporary workspace; no network or credentials."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_fx import FakeAirwallex, QUOTE
from test_m1 import RejectedClient
from touchstone.banked import BankedStore
from touchstone.fx import FxJournal
from touchstone.holds import CreateRejected, OperationJournal, SandboxHoldWorkflow
from touchstone.treasury_job import TreasuryFunding


def main():
    with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('MOCK proof must not access the network')):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, client = BankedStore(root / 'ledger.sqlite'), FakeAirwallex()
            funding = TreasuryFunding(store, client, FxJournal(root / 'fx.sqlite'))
            quoted = funding.prepare('mock-m1', 'mock-fx-001', QUOTE, 'USD', '1.00', '1')
            completed = funding.execute('mock-m1', True, 'USD', '1.00')
            funding.execute('mock-m1', True, 'USD', '1.00')
            rejected, journal = RejectedClient(), OperationJournal(root / 'holds.sqlite')
            try:
                SandboxHoldWorkflow(rejected, journal).run('mock-old')
            except CreateRejected:
                pass
            operation = journal.get('mock-old', 'create')
            retirement = journal.retire('mock-old', 'mock-fresh', {
                'scope': 'mock-old', 'request_id': operation['request_id'],
                'kind': 'RECORDED_CONFIGURATION_ERROR', 'reference': 'mock-rejection', 'no_object_created': True,
            }, rejected)
            retirement['label'] = 'MOCK'
            report = {'label': 'MOCK', 'remote_requests': 0, 'money_moved': False,
                      'phases': [quoted['phase'], completed['phase']],
                      'mock_conversion_creates_after_repeat': client.create_count,
                      'treasury': completed, 'retirement': retirement,
                      'audit_chain_head': store.ledger.audit(),
                      'claim': 'Controlled adapter execution only; no live Airwallex conversion or retirement'}
    target = ROOT / 'bench/results/m1/controlled-treasury.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'label': 'MOCK', 'evidence': 'bench/results/m1/controlled-treasury.json',
                      'money_moved': False, 'audit': report['audit_chain_head']}))


if __name__ == '__main__':
    main()
