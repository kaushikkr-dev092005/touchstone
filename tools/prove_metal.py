"""A capped real testnet protocol probe with durable, resumable evidence.

This does not authorize autonomous model procurement or claim an Airwallex hold.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.banked import BankedStore, resource_url
from touchstone.config import load_local
from touchstone.metal import MetalRail, MetalQuote, PaymentPending
from touchstone.verifier import check
from touchstone.workload import Task


def save(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.pending')
    with temporary.open('w', encoding='utf-8') as file:
        json.dump(report, file, indent=2)
        file.write('\n')
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scope', default='funded-proof-001')
    parser.add_argument('--recover', action='store_true')
    parser.add_argument('--withdraw', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,48}', args.scope):
        parser.error('Invalid scope')
    load_local()
    task = Task('protocol-probe', 'arithmetic', {'amounts_cents': [1250,275,499], 'discount_cents': 24})
    url = resource_url('http://127.0.0.1:8092', task)
    terms = {'job': args.scope, 'provider_url': url, 'price_cap_micro_usd': 10000,
             'allocation_micro_usd': 100000, 'purpose': 'INTEGRATION_PROBE', 'task': task.public()}
    path = ROOT / 'data/metal-proofs' / (args.scope + '.json')
    report = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'mode': 'REAL_TESTNET_PROTOCOL_PROBE', 'terms': terms, 'phase': 'CREATED',
        'airwallex': 'NOT_CONNECTED', 'model_eligibility': 'NOT_AUTHORIZED_FOR_AUTONOMOUS_PROCUREMENT'}
    if report['terms'] != terms:
        raise ValueError('Existing proof has different terms; preserve it')
    rail = MetalRail(args.scope, url, 10000, 100000)
    owner = BankedStore(ROOT / 'data/metal-proofs/owner-ledger.sqlite', ROOT / 'data/metal/funding-owner.sqlite')
    with owner.owner():
        save(path, report)
        if 'result' not in report:
            if 'quote' not in report:
                balance = rail.balance()
                if balance['historical_payments'] or balance['pending_invoice']:
                    raise PaymentPending('Wallet has unrelated history; preserve it')
                if int(balance['spendable_base_units']) < 100000*10**12:
                    if report['phase'] in {'DEPOSIT_DISPATCHING', 'DEPOSIT_BROADCAST'}:
                        raise PaymentPending('Deposit not yet spendable; no second deposit sent')
                    funding = rail.invoke('funding-status')
                    if int(funding['usdz_balance_base_units']) < 100000*10**12 or not int(funding['native_balance_base_units']):
                        raise PaymentPending('Fund the dedicated testnet address using the console faucet')
                    report.update(phase='DEPOSIT_DISPATCHING', funding_address=funding['address'])
                    save(path, report)
                    print('Depositing exactly 0.10 testnet USDZ into the dedicated job wallet.', flush=True)
                    report.update(phase='DEPOSIT_BROADCAST', deposit=rail.deposit(100000))
                    save(path, report)
                    balance = rail.balance()
                    if int(balance['spendable_base_units']) < 100000*10**12:
                        raise PaymentPending('Deposit not yet spendable; rerun this same proof later')
                report['quote'] = rail.quote().public()
                report['reservation'] = hashlib.sha256((args.scope + ':one-paid-call').encode()).hexdigest()
                report['phase'] = 'RESERVED'
                save(path, report)
            original = rail.lookup(report['reservation'])
            if original['state'] in {'UNKNOWN','RESERVED'} and args.recover:
                recovered = rail.recover(report['reservation'])
                original = {'state': recovered['state'], 'result': recovered}
            if original['state'] == 'UNPAID_CONFIRMED' and args.recover:
                refreshed = rail.quote()
                old = report['quote']['terms']
                if refreshed.terms['offer'] != old['offer'] or refreshed.terms['url'] != old['url']:
                    raise PaymentPending('Offer changed; original reservation cannot change seller or price')
                report['quote'] = refreshed.public()
                report['phase'] = 'RESERVED'
                save(path, report)
                original = {'state': 'NOT_DISPATCHED', 'result': None}
            if original['state'] in {'DELIVERED','PAID_OUTPUT_MISSING'}:
                result = original['result']
            elif original['state'] == 'NOT_DISPATCHED':
                quote = MetalQuote(**report['quote'])
                if quote.expires_at <= time.time():
                    raise PaymentPending('Stored quote expired before payment; no replacement purchase sent')
                print('Buying one inference call, capped at 0.01 testnet USDZ.', flush=True)
                result = rail.pay(report['reservation'], quote)
            elif args.recover:
                result = rail.recover(report['reservation'])
            else:
                raise PaymentPending('Original purchase needs --recover; no new payment sent')
            if result['state'] != 'DELIVERED' and args.recover:
                result = rail.recover(report['reservation'])
            if result['state'] == 'UNPAID_CONFIRMED':
                raise PaymentPending('SDK confirms no charge; retry the identical reservation with --recover')
            report['result'] = result
            report['phase'] = result['state']
            save(path, report)
        if report['result']['state'] != 'DELIVERED' and args.recover:
            report['result'] = rail.recover(report['reservation'])
            report['phase'] = report['result']['state']
            save(path, report)
        if report['result']['state'] == 'DELIVERED':
            response = report['result']['output']['body']
            report['verdict'] = check(task, response.get('output'))
            # A cached retry is independent evidence of no replacement payment.
            replay = rail.pay(report['reservation'], MetalQuote(**report['quote']))
            report['cached_retry_identical'] = replay == report['result']
            delivered_again = rail.invoke('replay-delivery', id=report['reservation'])
            report['provider_receipt_replay_identical'] = delivered_again == report['result']['output']
            report['wallet_status'] = rail.balance()
            report['paid_calls_recorded'] = report['wallet_status']['historical_payments']
            report['real_receipt_verified_by_provider'] = True
        if args.withdraw:
            report['withdrawal'] = rail.withdraw()
        report['observed_at'] = time.time()
        save(path, report)
        public = {**report, 'terms': {k:v for k,v in terms.items() if k != 'provider_url'}}
        save(ROOT / 'bench/results/metal-paid-proof.json', public)
        print(json.dumps({'mode':report['mode'], 'phase':report['phase'],
            'verdict':report.get('verdict'), 'cached_retry_identical':report.get('cached_retry_identical'),
            'paid_calls_recorded':report.get('paid_calls_recorded'),
            'provider_receipt_replay_identical':report.get('provider_receipt_replay_identical'),
            'withdrawal':report.get('withdrawal'), 'airwallex':report['airwallex']}, indent=2))
    return 0 if report['phase'] == 'DELIVERED' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (PaymentPending, ValueError, OSError) as error:
        print('Proof paused: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
