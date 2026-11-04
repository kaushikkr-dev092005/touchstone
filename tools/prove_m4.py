"""Opt-in controlled M4 evidence. No provider, wallet, environment or network."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]

from test_m4 import ComparisonFactory, ORIGINS
from touchstone.comparison import Comparison, prepare
from touchstone.invoice_profile import save


def main():
    output = ROOT/'bench/results/m4/mock'
    plan = prepare('controlled-m4', ORIGINS, 2040000, 50000, steps=16)
    with tempfile.TemporaryDirectory(prefix='touchstone-m4-proof-') as temporary:
        root = Path(temporary)
        factory = ComparisonFactory(root/'remote', plan)
        study = Comparison(plan, root/'study', factory, factory.health,
                           lambda: {'connected': True, 'chain_id': 63825}, lambda *_: True)
        result = study.run(True, 2040000, 40, True)
        count = sum(e[0] == 'pay' for e in factory.events)
        assert result['label'] == 'MOCK' and not result['live_gate_passed']
        assert study.run(True, 2040000, 40, True) == result
        assert sum(e[0] == 'pay' for e in factory.events) == count
        output.mkdir(parents=True, exist_ok=True)
        for name in ('report.json', 'comparison.md', 'environment.json', 'preflight.json'):
            (output/name).write_bytes((root/'study'/name).read_bytes())
        save(output/'proof.json', {'label': 'MOCK', 'real_payments': 0, 'controlled_calls': count,
            'completed_policy_steps': len(result['rows']), 'restart_duplicate_calls': 0,
            'control_violations': result['control_violations'], 'audit': result['audit'],
            'qualification': 'NO_QUALIFIED_MODELS; ladder buys nothing',
            'plan_sha256': plan['plan_sha256']})
        print(json.dumps({'label': 'MOCK', 'real_payments': 0, 'controlled_calls': count,
                          'control_violations': result['control_violations'], 'audit': result['audit']}, indent=2))


if __name__ == '__main__':
    main()
