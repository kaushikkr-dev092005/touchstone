"""Read-only validation gates. Reports configuration presence, never credential values."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def provider_status(reader):
    services = {'dashboard': bool(reader(8088, '/api/state').get('jobs') is not None),
                'model': reader(8080, '/health').get('status') == 'ok'}
    for name, port, mode in [('local-gpu', 8092, 'model'), ('hosted-premium', 8093, 'anthropic')]:
        raw = reader(port, '/health')
        checks = {'health_available': bool(raw), 'identity_matches': raw.get('provider_id') == name,
                  'provider_type_matches': raw.get('provider_type') == mode,
                  'testnet_63825': raw.get('chain') == 63825,
                  'inference_ready': raw.get('inference_ready') is True}
        if name == 'hosted-premium':
            checks['partner_credits_declared'] = raw.get('upstream_funding') == 'PARTNER_CREDITS_OPERATOR_DECLARED'
        services[name] = {'label': 'MEASURED' if all(checks.values()) else 'BLOCKED', 'checks': checks}
    return services


def profile_status(directory):
    from touchstone.invoice_dataset import build
    from touchstone.invoice_study import code_hashes, evaluate_profile, metrics, score
    records, truth = build()
    current = code_hashes()
    profiles = []
    for path in sorted(Path(directory).glob('*.json')):
        row = {'file': path.name, 'eligible': False}
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
            changed = [name for name, value in current.items() if raw.get('code_sha256', {}).get(name) != value]
            row.update(saved_calls=len(raw.get('rows', [])), changed_code=changed,
                       measurement_scope='HISTORICAL_SAVED_OUTPUTS_NO_NEW_MODEL_CALLS')
            rescored = metrics(score(records, truth, raw['rows']))
            row['offline_rescore'] = {k: rescored[k] for k in ('sources_scored', 'strict_correct', 'accepted', 'false_accepts', 'correct_beyond_tools')}
            if changed:
                row.update(label='BLOCKED', reason='STALE_PROFILE_REQUIRES_REMEASUREMENT')
            else:
                evaluated = evaluate_profile(records, truth, raw)
                row.update(label='MEASURED', eligible=evaluated['eligible'],
                           reason='QUALIFIED' if evaluated['eligible'] else 'QUALITY_GATE_NOT_PASSED')
        except (ValueError, KeyError, TypeError, OSError):
            row.update(label='BLOCKED', reason='PROFILE_INVALID_OR_INCOMPATIBLE')
        profiles.append(row)
    return profiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rpc', action='store_true', help='Also perform a redacted read-only testnet RPC check')
    parser.add_argument('--output', default='bench/results/validation/readiness.json')
    args = parser.parse_args()
    from tools.run_project import environment, health
    env = environment()
    services = provider_status(health)
    profiles = profile_status(ROOT / 'bench/results/m3/profiles')
    rpc = {'label': 'BLOCKED', 'reason': 'NOT_PROBED', 'transactions_sent': 0}
    if args.rpc:
        from touchstone.rpc import inspect_rpc
        try:
            observed = inspect_rpc()
            rpc = {'label': 'MEASURED', 'connected': observed['connected'], 'chain_id': observed['chain_id'],
                   'transactions_sent': 0}
        except (ValueError, RuntimeError):
            rpc = {'label': 'BLOCKED', 'reason': 'RPC_UNAVAILABLE_OR_WRONG_CHAIN', 'transactions_sent': 0}
    report = {'label': 'MEASURED', 'observed_at': time.time(), 'scope': 'READ_ONLY_VALIDATION_GATE_CHECK',
        'services': services, 'profiles': profiles, 'eligible_models': sum(p['eligible'] for p in profiles),
        'configuration_presence': {'hosted_key': bool(env.get('ANTHROPIC_API_KEY')),
            'hosted_model': bool(env.get('ANTHROPIC_MODEL')), 'metal_rpc': bool(env.get('METAL_RPC_URL'))},
        'rpc': rpc, 'fresh_written_spend_approval': False, 'paid_validation_authorized': False,
        'financial_transactions': 0, 'model_inference_calls': 0,
        'notice': 'Health and configuration presence do not prove working hosted credentials, credits, model quality or settlement.'}
    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
