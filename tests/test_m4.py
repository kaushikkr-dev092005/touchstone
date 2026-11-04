import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from urllib.parse import urlparse, parse_qs
import base64

from m2_fixtures import FixtureClient, FixtureFactory
from touchstone.comparison import Comparison, POLICIES, TIERS, fingerprint, prepare, summarize, validate
from touchstone.invoice_dataset import build
from touchstone.ledger import Ledger
from touchstone.metal import MetalQuote, PaymentPending

ORIGINS = dict(zip(TIERS, ('http://127.0.0.1:8092', 'http://127.0.0.1:8095')))


def public_task(url):
    encoded = parse_qs(urlparse(url).query)['task'][0]
    return json.loads(base64.urlsafe_b64decode(encoded+'='*((-len(encoded))%4)))


class ComparisonClient(FixtureClient):
    def quote(self, url):
        task = public_task(url)
        tier = 'local-gpu' if url.startswith(ORIGINS['local-gpu']) else 'hosted-premium'
        self.factory.events.append(('quote', task['id'], tier))
        fault = self.factory.plan['schedule']['faults'].get(task['id'], {}).get(tier)
        if fault == 'outage':
            raise RuntimeError('MOCK secret text must not leak')
        price = 10000 if tier == 'local-gpu' else 20000
        if self.factory.reverse_prices:
            price = 30000 if tier == 'local-gpu' else 10000
        raw = {'url': url, 'provider_id': tier, 'offer': {'amount': str(price*10**12)},
               'expires_at': (time.time()+120)*1000}
        identity = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
        return MetalQuote(identity, tier, price, raw['expires_at']/1000, raw, mode='MOCK')

    def pay(self, key, quote):
        self.factory.events.append(('pay', key, quote.provider))
        task = public_task(quote.terms['url'])
        output = copy.deepcopy(self.factory.outputs[fingerprint(task['source'])])
        if self.factory.false_accept:
            output['fields']['invoice_id'] = copy.deepcopy(output['fields']['purchase_order_id'])
        if self.factory.plan['schedule']['faults'].get(task['id'], {}).get(quote.provider) == 'quality-drop':
            output = {'quality_drop': True}
        with self.rail.connect() as db:
            db.execute('INSERT OR IGNORE INTO terms VALUES(?,?)', (key, json.dumps(quote.terms)))
        self.rail.pay(key, quote, lambda: output)
        if self.factory.lose:
            raise PaymentPending('MOCK response lost after durable charge')
        result = self._result(key)
        metadata = {'provider_type': 'LOCAL_MODEL' if quote.provider == 'local-gpu' else 'ANTHROPIC_API',
                    'provider_model': 'MOCK-'+quote.provider, 'latency_ms': 3}
        if quote.provider == 'hosted-premium':
            metadata['funding_source'] = 'PARTNER_CREDITS_OPERATOR_DECLARED'
        if self.factory.plan['schedule']['faults'].get(task['id'], {}).get(quote.provider) == 'quality-drop':
            metadata['chaos_mode'] = 'quality-drop'
        result['output']['body']['provider_metadata'] = metadata
        return result


class ComparisonFactory(FixtureFactory):
    def __init__(self, path, plan):
        super().__init__(path)
        self.plan, self.lose, self.reverse_prices, self.false_accept = plan, False, False, False
        self.outputs = {}
        for seed in plan['seeds']:
            records, truth = build(seed)
            self.outputs.update({fingerprint(r['task']['source']): truth[r['task']['id']]['output'] for r in records})

    def __call__(self, wallet, origin, cap, budget):
        client = ComparisonClient(self, wallet, origin)
        with client.rail.connect() as db:
            if not db.execute('SELECT 1 FROM funds').fetchone():
                db.execute('INSERT INTO funds VALUES(?)', (budget,))
        return client

    def health(self, origin):
        tier = next(t for t, url in ORIGINS.items() if url == origin)
        return {'chain': 63825, 'provider_id': tier, 'provider_type': 'model' if tier == 'local-gpu' else 'anthropic',
                'provider_model': 'MOCK-'+tier, 'inference_ready': True, 'chaos': 'none',
                'chaos_schedule_sha256': self.plan['schedule_sha256'], 'upstream_funding': 'PARTNER_CREDITS_OPERATOR_DECLARED'}


class M4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = prepare('m4-fixture', ORIGINS, 2040000, 50000, 40, 12)
        self.factory = ComparisonFactory(self.root/'remote', self.plan)
        self.runner = Comparison(self.plan, self.root/'study', self.factory, self.factory.health,
                                 lambda: {'connected': True, 'chain_id': 63825}, lambda *_: True)

    def run_study(self):
        return self.runner.run(True, self.plan['aggregate_cap_micro_usdz'], self.plan['max_purchases'], True)

    def test_matched_sources_and_faults_are_identical_across_four_policies(self):
        plan = self.plan
        self.assertEqual(len(plan['tasks']), 12)
        for seed in plan['seeds']:
            for index, fault in ((3, 'outage'), (7, 'quality-drop')):
                for number in range(4):
                    self.assertEqual(plan['schedule']['faults'][f'M4-{seed}-{index}-{number}'], {'local-gpu': fault})
        other = prepare('m4-fixture', ORIGINS, 2040000, 50000, 40, 12)
        self.assertEqual(plan['plan_sha256'], other['plan_sha256'])

    def test_no_execute_wrong_approval_or_missing_baseline_ack_dispatches_nothing(self):
        for args in ((False, 2040000, 40, True), (True, 1, 40, True), (True, 2040000, 1, True), (True, 2040000, 40, False)):
            with self.assertRaises(ValueError):
                self.runner.run(*args)
        self.assertEqual(self.factory.events, [])

    def test_bad_health_chain_or_schedule_never_purchases(self):
        for field, value in (('chain', 1), ('inference_ready', False), ('chaos_schedule_sha256', 'wrong'), ('provider_type', 'tool')):
            original = self.factory.health
            self.runner.health_reader = lambda origin: {**original(origin), field: value}
            self.assertFalse(self.runner.preflight()['ready'])
            with self.assertRaises(RuntimeError):
                self.run_study()
        self.assertFalse(any(e[0] == 'pay' for e in self.factory.events))

    def test_four_policy_report_no_unqualified_ladder_spend_and_no_duplicate_on_restart(self):
        result = self.run_study()
        self.assertEqual(result['label'], 'MOCK')
        self.assertFalse(result['live_gate_passed'])
        self.assertTrue(result['complete'])
        self.assertEqual(len(result['rows']), 48)
        self.assertTrue(result['reconciliation']['matched'])
        self.assertEqual(result['control_violations'], [])
        for policy in ('tools-only', 'touchstone-ladder'):
            self.assertTrue(all(not r['calls'] for r in result['rows'] if r['policy'] == policy))
        calls = len([e for e in self.factory.events if e[0] == 'pay'])
        again = self.run_study()
        self.assertEqual(len([e for e in self.factory.events if e[0] == 'pay']), calls)
        self.assertEqual(result, again)
        self.assertNotIn('secret text', json.dumps(result))
        self.assertTrue(any(c['provider_metadata'].get('chaos_mode') == 'quality-drop' for c in result['calls'].values()))
        self.assertEqual(sum(r['provider_micro_usdz'] for r in result['summary']), result['confirmed_provider_micro_usdz'])
        self.assertEqual(sum(r['simulated_check_micro_usd'] for r in result['summary']), result['simulated_check_fee_micro_usd'])

    def test_cheapest_policy_selects_actual_price_not_a_hardcoded_local_tier(self):
        self.factory.reverse_prices = True
        result = self.run_study()
        cheapest = [c for c in result['calls'].values() if c['policy'] == 'always-cheapest']
        self.assertTrue(cheapest)
        self.assertTrue(all(c['provider'] == 'hosted-premium' for c in cheapest))

    def test_uncertain_charge_stops_every_policy_and_restart_cannot_pay_twice(self):
        self.factory.lose = True
        with self.assertRaises(RuntimeError):
            self.run_study()
        report = self.runner.report()
        self.assertEqual(report['pending_attempts'], 1)
        self.assertGreater(report['cost_at_risk_micro_usdz_plus_demo_check_fee'], 0)
        with self.assertRaises(PaymentPending):
            self.run_study()
        self.assertEqual(sum(e[0] == 'pay' for e in self.factory.events), 1)

    def test_aggregate_count_and_cost_caps_include_failed_calls_and_checks(self):
        self.plan = prepare('small', ORIGINS, 21000, 20000, 1, 12)
        self.factory = ComparisonFactory(self.root/'small-remote', self.plan)
        self.runner = Comparison(self.plan, self.root/'small', self.factory, self.factory.health,
                                 lambda: {'connected': True, 'chain_id': 63825}, lambda *_: True)
        with self.assertRaises(RuntimeError):
            self.run_study()
        result = self.runner.report()
        self.assertEqual(sum(e[0] == 'pay' for e in self.factory.events), 1)
        self.assertLessEqual(result['confirmed_provider_micro_usdz']+result['simulated_check_fee_micro_usd'], 21000)
        self.assertFalse(result['complete'])
        self.assertEqual(result['control_violations'], [])

    def test_changed_plan_cannot_reuse_scope_and_tampering_is_rejected(self):
        self.run_study()
        changed = copy.deepcopy(self.plan)
        changed['aggregate_cap_micro_usdz'] += 1
        with self.assertRaises(ValueError):
            validate(changed)
        changed['plan_sha256'] = fingerprint({k: v for k, v in changed.items() if k != 'plan_sha256'})
        runner = Comparison(changed, self.root/'study', self.factory)
        with self.assertRaises(ValueError):
            runner.run(True, changed['aggregate_cap_micro_usdz'], changed['max_purchases'], True)

    def test_wallet_scope_cannot_run_two_studies_from_different_directories(self):
        from touchstone.leases import exclusive, LeaseBusy
        other = Comparison(self.plan, self.root/'other-study', self.factory)
        self.assertEqual(self.runner.wallet_owner, other.wallet_owner)
        with exclusive(self.runner.wallet_owner):
            with self.assertRaises(LeaseBusy):
                self.run_study()
        self.assertFalse(any(e[0] == 'pay' for e in self.factory.events))

    def test_false_accept_and_refusal_denominators_are_explicit(self):
        self.factory.false_accept = True
        result = self.run_study()
        metrics = next(r for r in summarize(result) if r['policy'] == 'always-premium')
        self.assertGreater(metrics['false_accepts'], 0)
        self.assertEqual(metrics['false_accept_rate'], metrics['false_accepts']/metrics['accepted'])
        self.assertEqual(metrics['completed_steps'], metrics['accepted']+metrics['refusals'])

    def test_qualified_ladder_escalates_rejections_and_keeps_both_charges(self):
        self.plan['qualifications'] = {t: {'eligible': True, 'model_id': 'MOCK-'+t, 'model_sha256': 'a'*64} for t in TIERS}
        self.plan['plan_sha256'] = fingerprint({k: v for k, v in self.plan.items() if k != 'plan_sha256'})
        original = self.factory.health
        self.runner = Comparison(self.plan, self.root/'qualified', self.factory,
            lambda origin: {**original(origin), 'provider_model_sha256': 'a'*64},
            lambda: {'connected': True, 'chain_id': 63825}, lambda *_: True)
        result = self.run_study()
        self.assertTrue(any(c['policy'] == 'touchstone-ladder' for c in result['calls'].values()))
        self.assertEqual(result['control_violations'], [])
        self.assertLessEqual(len(result['calls']), 40)
        self.assertTrue(result['reconciliation']['matched'])

    def test_partial_paid_call_not_attached_to_a_result_is_still_in_policy_totals(self):
        from unittest.mock import patch
        from touchstone.invoice_extraction import verify
        def fail_after_payment(task, output):
            if any(e[0] == 'pay' for e in self.factory.events):
                raise RuntimeError('MOCK checker crash after payment')
            return verify(task, output)
        with patch('touchstone.comparison.verify', side_effect=fail_after_payment):
            with self.assertRaises(RuntimeError):
                self.run_study()
        result = self.runner.report()
        self.assertEqual(result['pending_attempts'], 1)
        self.assertGreater(result['confirmed_provider_micro_usdz'], 0)
        self.assertEqual(sum(r['provider_micro_usdz'] for r in result['summary']), result['confirmed_provider_micro_usdz'])
        self.assertTrue(any(r['unfinished_calls_in_report'] for r in result['summary']))
