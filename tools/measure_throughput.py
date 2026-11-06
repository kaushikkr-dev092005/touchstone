"""Measure local decode throughput and fit the capacity-pricing calibration. Local only; no payments."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone import throughput
from touchstone.telemetry import sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8080/v1/chat/completions')
    parser.add_argument('--tier', choices=['economy', 'balanced'], default='balanced')
    parser.add_argument('--runs', type=int, default=30)
    parser.add_argument('--max-multiplier', type=float, default=1.25)
    parser.add_argument('--samples-out', default=str(ROOT / 'bench/results/features/throughput-samples.json'))
    parser.add_argument('--calibration-out', default=str(ROOT / 'bench/results/features/capacity-calibration.json'))
    args = parser.parse_args()
    if not 1 <= args.runs <= 200:
        parser.error('--runs must be between 1 and 200')
    manifest = json.loads((ROOT / '.tools/models' / f'{args.tier}-manifest.json').read_text())
    model = manifest.get('model') or Path(manifest['model_path']).name
    try:
        samples = throughput.measure(lambda m, limit: throughput.http_request(args.url, m, limit), sample,
                                     model=model, runs=args.runs)
    except (OSError, ValueError) as error:
        print(json.dumps({'label': 'BLOCKED', 'error': 'Local model endpoint unavailable or unusable', 'detail': str(error)[:120]}))
        return 1
    Path(args.samples_out).write_text(json.dumps({'label': 'MEASURED', 'model': model, 'samples': samples}, indent=2) + '\n')
    try:
        result = throughput.calibrate(samples, model=model, model_sha256=manifest['model_sha256'],
                                      max_multiplier=args.max_multiplier)
    except ValueError as error:
        print(json.dumps({'label': 'BLOCKED', 'samples_saved': len(samples), 'calibration': 'NOT_CREATED', 'reason': str(error)}))
        return 2
    Path(args.calibration_out).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'label': 'MEASURED', 'baseline_tps': result['body']['baseline_tps'],
                      'interval_90': result['body']['baseline_tps_interval_90'], 'samples': result['body']['samples'],
                      'digest': result['digest']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
