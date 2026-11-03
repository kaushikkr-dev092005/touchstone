"""Offline M2 evidence: controlled adapters, real process death, no live funds."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from m2_fixtures import FixtureFactory
from test_invariants import RandomizedOperationTests
from touchstone.metal_batch import MetalBatch


def main():
    with tempfile.TemporaryDirectory() as directory, patch('socket.create_connection', side_effect=AssertionError('No network allowed')):
        root = Path(directory)
        factory = FixtureFactory(root/'remote', threading.Barrier(3))
        batch = MetalBatch(root/'batch', factory, root/'funding.sqlite')
        batch.prepare('parallel', 'http://127.0.0.1:8092', 3, 2, 40000, 10000, 120000)
        batch.fund('parallel', execute=True)
        parallel = batch.run('parallel', execute=True)
        assert len(parallel['paid_attempts']) == 6 and parallel['receipts_reconciled']
        assert all(event[0]=='deposit' for event in factory.events[:3])
        factory.barrier = None
        batch.prepare('crash', 'http://127.0.0.1:8092', 1, 1, 30000, 10000, 30000)
        batch.fund('crash', execute=True)
        script = '''import sys
from pathlib import Path
sys.path[:0]=[str(Path.cwd()),str(Path.cwd()/'tests')]
from m2_fixtures import FixtureFactory
from touchstone.metal_batch import MetalBatch
root=Path(sys.argv[1])
MetalBatch(root/'batch',FixtureFactory(root/'remote'),root/'funding.sqlite').run('crash',execute=True,kill_at='after_rail')
'''
        env = {**os.environ, 'TOUCHSTONE_IGNORE_LOCAL_CONFIG': '1'}
        child = subprocess.run([sys.executable, '-c', script, str(root)], cwd=ROOT,
                               env=env, capture_output=True, text=True, timeout=30)
        assert child.returncode == 86, 'Controlled child did not exit at after_rail'
        before = batch.report('crash')
        assert before['pending_attempts'] == 1 and not before['paid_attempts']
        recovered = batch.run('crash', execute=True, recover=True)
        replay = batch.run('crash', execute=True, recover=True)
        assert len(recovered['paid_attempts']) == 1 and recovered['receipts_reconciled']
        assert replay['paid_attempts'] == recovered['paid_attempts']
        fuzz = [RandomizedOperationTests().run_sequence(seed) for seed in range(100,108)]
        report = {'label': 'MOCK', 'network_requests': 0, 'live_money_moved': False,
                  'parallel': parallel, 'funding_and_purchase_order': factory.events,
                  'crash': {'label': 'MOCK', 'process_exit_code': child.returncode,
                            'pending_after_kill': before['pending_attempts'], 'recovery': recovered,
                            'repeat_recovery_receipts_unchanged': True, 'duplicate_charges_observed': 0},
                  'fuzz': fuzz, 'audit': batch.ledger.audit(),
                  'live_exit_gate': 'BLOCKED: the authorized single live call has not executed; live kill/restart remains unproven'}
        target = ROOT/'bench/results/m2/controlled-proof.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'label': 'MOCK', 'evidence': str(target.relative_to(ROOT)),
            'concurrent_jobs': 3, 'parallel_receipts': 6, 'crash_receipts': 1,
            'fuzz_operations': sum(x['operations'] for x in fuzz), 'audit': report['audit']}))


if __name__ == '__main__':
    main()
