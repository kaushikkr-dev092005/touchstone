"""Create/verify fault evidence. No payments, refunds or wallet generation."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from touchstone.fault_proof import create, validate, cryptographic_check, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['create', 'verify'])
    parser.add_argument('--input', required=True)
    parser.add_argument('--output')
    parser.add_argument('--check-network', action='store_true', help='Read-only receipt/chain check; no transaction')
    parser.add_argument('--operator-key', help='Public operator key independently trusted by the verifier')
    parser.add_argument('--sign-existing-wallet', help='Create a fault attestation with an existing clearing key; never creates a wallet')
    args = parser.parse_args()
    try:
        path = Path(args.input)
        if path.stat().st_size > 250000:
            raise ValueError('Evidence file is too large')
        source = json.loads(path.read_text(encoding='utf-8'))
        proof = create(source) if args.action == 'create' else source
        validate(proof)
        crypto = cryptographic_check(proof, check_network=args.check_network, operator_key=args.operator_key,
                                      wallet_scope=args.sign_existing_wallet)
        if crypto.get('fault_signature'):
            proof['fault_signature'] = crypto.pop('fault_signature')
        proof['cryptographic_observation'] = crypto
        if args.output:
            save(args.output, proof)
        print(json.dumps({'label': 'MEASURED', 'fault_root': proof['commitment']['root'],
                          'error': proof['body']['counterexample']['error_code'],
                          'deterministic_fault_reproduced': True, **crypto,
                          'refund_executed': False}, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError):
        print(json.dumps({'label': 'BLOCKED', 'error': 'Fault proof unavailable, invalid or unverified', 'transactions_sent': 0}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
