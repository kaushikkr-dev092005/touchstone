import json
from pathlib import Path
import unittest

from touchstone.comparison import POLICIES
from touchstone.policy_study import comparison_progress, live_progress

ROOT = Path(__file__).resolve().parent.parent
UNITS = [(f't{i}', 7) for i in range(16)]


def outcome(policy, unit, status='completed', reason=None):
    return {'policy': policy, 'task_id': unit[0], 'seed': unit[1], 'status': status, 'reason': reason}


class ProgressDenominators(unittest.TestCase):
    def test_denominator_is_policies_times_units_times_seeds(self):
        units = UNITS + [(t, 8) for t, _ in UNITS]
        p = comparison_progress(POLICIES, units, [])
        self.assertEqual((p['N'], p['n'], p['not_started'], p['state']), (128, 0, 128, 'INCOMPLETE'))
        self.assertEqual({v['N'] for v in p['per_policy'].values()}, {32})

    def test_failed_outcomes_count_toward_n_censored_do_not(self):
        rows = [outcome(p, u) for p in POLICIES for u in UNITS[:10]]
        rows += [outcome('always-cheapest', UNITS[10], 'failed', 'timeout')]
        rows += [outcome('always-premium', UNITS[10], 'censored_by_policy', 'budget')]
        p = comparison_progress(POLICIES, UNITS, rows)
        self.assertEqual((p['n'], p['failed'], p['censored'], p['resolved']), (41, 1, 1, 42))
        self.assertEqual(p['per_policy']['always-cheapest']['n'], 11)
        self.assertEqual(p['per_policy']['always-premium']['n'], 10)
        self.assertEqual(p['complete_pairs'], 10)

    def test_live_twelve_of_sixty_four_shape(self):
        rows = [outcome(p, u) for p in POLICIES for u in UNITS[:3]]
        p = comparison_progress(POLICIES, UNITS, rows)
        self.assertEqual((p['n'], p['N'], p['complete'], p['state']), (12, 64, False, 'INCOMPLETE'))
        self.assertIsNone(p['winner'])
        self.assertIn('incomplete', p['winner_note'])

    def test_complete_only_at_n_equals_n_or_explicit_censoring(self):
        rows = [outcome(p, u) for p in POLICIES for u in UNITS]
        self.assertEqual(comparison_progress(POLICIES, UNITS, rows)['state'], 'COMPLETE')
        rows[-1] = outcome(rows[-1]['policy'], UNITS[-1], 'censored_by_policy', 'mandate expired')
        p = comparison_progress(POLICIES, UNITS, rows)
        self.assertEqual((p['state'], p['complete'], p['n']), ('COMPLETE_WITH_CENSORING', True, 63))
        self.assertEqual(p['censored_reasons'], {'mandate expired': 1})

    def test_censoring_requires_reason(self):
        for reason in (None, '', '   '):
            with self.assertRaises(ValueError):
                comparison_progress(POLICIES, UNITS, [outcome('tools-only', UNITS[0], 'censored_by_policy', reason)])

    def test_rejects_double_counting_and_foreign_outcomes(self):
        with self.assertRaises(ValueError):
            comparison_progress(POLICIES, UNITS, [outcome('tools-only', UNITS[0])]*2)
        with self.assertRaises(ValueError):
            comparison_progress(POLICIES, UNITS, [outcome('tools-only', ('other', 7))])
        with self.assertRaises(ValueError):
            comparison_progress(POLICIES, UNITS, [outcome('unknown-policy', UNITS[0])])
        with self.assertRaises(ValueError):
            comparison_progress(POLICIES, UNITS, [outcome('tools-only', UNITS[0], 'verified')])
        with self.assertRaises(ValueError):
            comparison_progress(POLICIES, UNITS + UNITS[:1], [])

    def test_saved_live_report_is_twelve_finished_fifty_two_censored(self):
        plan = json.loads((ROOT/'bench/results/m4-v2/final-plan.json').read_text(encoding='utf-8'))
        report = json.loads((ROOT/'bench/results/m4-v2/live-report.json').read_text(encoding='utf-8'))
        p = live_progress(plan, report)
        self.assertEqual((p['n'], p['N'], p['censored'], p['complete_pairs']), (12, 64, 52, 3))
        self.assertEqual(sum(p['censored_reasons'].values()), 52)
        self.assertTrue(any('INFERRED_FROM_LEDGER' in r for r in p['censored_reasons']))

    def test_live_non_policy_stop_stays_incomplete(self):
        plan = json.loads((ROOT/'bench/results/m4-v2/final-plan.json').read_text(encoding='utf-8'))
        report = json.loads((ROOT/'bench/results/m4-v2/live-report.json').read_text(encoding='utf-8'))
        p = live_progress(plan, {**report, 'stop_reason': 'RuntimeError'})
        self.assertEqual((p['n'], p['censored'], p['not_started'], p['state']), (12, 0, 52, 'INCOMPLETE'))


# ---------------------------------------------------------------- harness tests (fake models, no GPU)
import hashlib
import sqlite3
import subprocess
import sys
import tempfile

from touchstone.invoice_corpus import load as load_corpus
from touchstone.policy_study import (HealthError, ProviderFailure, Study, check_health, markdown, prepare, report)

SOURCE_PLAN = json.loads((ROOT/'bench/results/m4-v2/final-plan.json').read_text(encoding='utf-8'))
_, _, TRUTH = load_corpus(ROOT/SOURCE_PLAN['corpus'], include_truth=True)
SOURCE_BY_TEXT = {r['task']['source']['text']: r['source_id'] for r in SOURCE_PLAN['tasks']}
FAKE_MODELS = {t: {'model': 'FAKE-' + t, 'model_file': t + '.gguf', 'model_sha256': '0'*64, 'quantization': 'none',
                   'runtime_release': 'none', 'backend': 'none', 'runtime_archive_sha256': '0', 'model_revision': 'none',
                   'hash_verified_on_disk': False} for t in ('economy', 'balanced')}


def HEALTHY():
    return {'ready': True, 'problems': []}


def make_plan(budget=672000, retries=1):
    return prepare(SOURCE_PLAN, {'economy': 'http://127.0.0.1:18081', 'balanced': 'http://127.0.0.1:18082'}, budget,
                   retries=retries, models=FAKE_MODELS)


def fake_infer(tier, task):
    """Deterministic fake: balanced returns truth; economy returns truth for about half of the sources."""
    source_id = SOURCE_BY_TEXT[task.source['text']]
    if tier == 'balanced' or int(hashlib.sha256(source_id.encode()).hexdigest(), 16) % 2:
        return TRUTH[source_id]['output']
    return {'invalid_json': 'truncated'}


class Counting:
    def __init__(self):
        self.calls = []

    def __call__(self, tier, task):
        self.calls.append((tier, task.id))
        return fake_infer(tier, task)


class Stop(Exception):
    pass


def stop_after(count, holder):
    def hook(**_):
        if len(holder[0].outcomes()) == count:
            raise Stop()
    return hook


def comparable(study):
    return {(o['policy'], o['task_id']): (o['status'], o['record']['decision'],
                                          json.dumps(o['record']['output'], sort_keys=True),
                                          sum(c['charged_micro_usd'] for c in o['record']['calls']))
            for o in study.outcomes()}


KILL_SCRIPT = '''
import os, sys
sys.path[:0] = [sys.argv[1], os.path.join(sys.argv[1], 'tests')]
from test_policy_study import make_plan, fake_infer, HEALTHY
from touchstone.policy_study import Study
hook, target = sys.argv[3], int(sys.argv[4])
seen = []
def kill(**_):
    seen.append(1)
    if len(seen) == target:
        os._exit(9)  # hard kill: no finally blocks, no session close
Study(sys.argv[2], make_plan(), infer=fake_infer, health=HEALTHY, hooks={hook: kill}).run()
'''


class StudyHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='touchstone-study-test-')
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def baseline(self):
        study = Study(self.root/'baseline', make_plan(), infer=fake_infer, health=HEALTHY)
        if not study.sessions():
            study.run()
        return study

    def test_uninterrupted_run_completes_with_matching_money(self):
        study = self.baseline()
        p = study.progress()
        self.assertEqual((p['n'], p['N'], p['state'], p['complete_pairs']), (64, 64, 'COMPLETE', 16))
        attempts = study.ledger.attempts()
        self.assertEqual(len(study.rail.receipts()), sum(bool(a['receipt']) for a in attempts))
        self.assertFalse(any(a['state'] in {'RESERVED', 'DISPATCHING', 'PAID'} for a in attempts))
        self.assertTrue(study.ledger.audit()['valid'])

    def test_resume_dispatches_only_missing_outcomes(self):
        counter, holder = Counting(), [None]
        study = holder[0] = Study(self.root/'s', make_plan(), infer=counter, health=HEALTHY,
                                  hooks={'before_outcome': stop_after(20, holder)})
        with self.assertRaises(Stop):
            study.run()
        self.assertEqual(study.progress()['n'], 20)
        done_before = {o['record']['step_id'] for o in study.outcomes()}
        first_calls = len(counter.calls)
        with self.assertRaises(ValueError):  # a started study never restarts silently
            Study(self.root/'s', infer=counter, health=HEALTHY).run()
        resumed = Study(self.root/'s', infer=counter, health=HEALTHY)
        self.assertEqual(resumed.run(resume=True)['n'], 64)
        self.assertFalse(done_before & {task for _, task in counter.calls[first_calls:]})
        calls_after = len(counter.calls)
        resumed.run(resume=True)  # idempotent: nothing left to dispatch
        self.assertEqual(len(counter.calls), calls_after)
        self.assertEqual(comparable(resumed), comparable(self.baseline()))
        self.assertEqual([s['end_state'] for s in resumed.sessions()], ['STOPPED', 'COMPLETE', 'COMPLETE'])

    def kill_and_resume(self, hook, target):
        directory = self.root/'killed'
        result = subprocess.run([sys.executable, '-c', KILL_SCRIPT, str(ROOT), str(directory), hook, str(target)],
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 9, result.stderr[-2000:])
        study = Study(directory, infer=fake_infer, health=HEALTHY)
        self.assertLess(study.progress()['n'], 64)
        progress = study.run(resume=True)
        self.assertEqual((progress['n'], progress['state']), (64, 'COMPLETE'))
        self.assertEqual([s['end_state'] for s in study.sessions()], ['INTERRUPTED', 'COMPLETE'])
        attempts = study.ledger.attempts()
        receipts = study.rail.receipts()
        self.assertEqual(len(receipts), sum(bool(a['receipt']) for a in attempts))
        self.assertEqual(len({r['key'] for r in receipts}), len(receipts))
        self.assertFalse(any(a['state'] in {'RESERVED', 'DISPATCHING', 'PAID'} for a in attempts))
        self.assertTrue(study.ledger.audit()['valid'])
        self.assertEqual(report(study)['interruptions'], 1)
        return study

    def test_kill_mid_model_call_then_resume(self):
        study = self.kill_and_resume('during_call', 7)
        voided = [a for a in study.ledger.attempts() if a['state'] == 'VOID']
        self.assertEqual(len(voided), 1)  # the killed call: unpaid, voided on recovery, retried with a new key
        self.assertIn('no receipt', voided[0]['reason'])
        baseline = comparable(self.baseline())
        self.assertEqual({k: v[:3] for k, v in comparable(study).items()}, {k: v[:3] for k, v in baseline.items()})

    def test_kill_after_payment_before_ledger_charges_once(self):
        study = self.kill_and_resume('after_pay', 7)
        reused = [c for o in study.outcomes() for c in o['record']['calls'] if c['status'] == 'PAID_EARLIER_SESSION']
        self.assertEqual(len(reused), 1)
        self.assertIsNone(reused[0]['latency_ms'])  # timing lost with the process stays null, never invented
        self.assertEqual(comparable(study), comparable(self.baseline()))  # same outputs, same total charge

    def test_policy_budget_censors_with_reason_and_stays_paired(self):
        study = Study(self.root/'tight', make_plan(budget=21000), infer=fake_infer, health=HEALTHY)
        p = study.run()
        self.assertEqual(p['state'], 'COMPLETE_WITH_CENSORING')
        self.assertEqual(p['per_policy']['tools-only']['censored'], 0)
        self.assertGreater(p['per_policy']['always-premium']['censored'], 0)
        self.assertTrue(all(r.startswith('PolicyError') for r in p['censored_reasons']))
        self.assertTrue(any('budget' in r for r in p['censored_reasons']))
        self.assertTrue(all(j['spent'] <= j['budget'] == 21000 for j in study.ledger.jobs()))  # limit held, never raised
        r = report(study)
        self.assertTrue(all(s['pairs'] == p['complete_pairs'] for s in r['summary']))

    def test_provider_failures_are_bounded_recorded_and_unpaid(self):
        def broken_economy(tier, task):
            if tier == 'economy':
                raise ProviderFailure('TimeoutError: timed out')
            return fake_infer(tier, task)
        study = Study(self.root/'fail', make_plan(retries=1), infer=broken_economy, health=HEALTHY)
        p = study.run()
        self.assertEqual(p['per_policy']['always-cheapest']['failed'], 16)
        cheap = [o['record'] for o in study.outcomes() if o['policy'] == 'always-cheapest']
        self.assertTrue(all(len(r['calls']) == 2 and all(c['status'] == 'FAILED_UNPAID' and c['charged_micro_usd'] == 0
                                                         for c in r['calls']) for r in cheap))
        ladder = [o['record'] for o in study.outcomes() if o['policy'] == 'touchstone-ladder' and not o['record']['tool_used']]
        self.assertTrue(ladder and all(r['status'] == 'completed' and r['tiers_called'] == ['economy', 'balanced']
                                       for r in ladder))
        self.assertFalse([r for r in study.rail.receipts() if r['provider'] == 'economy'])

    def test_unhealthy_server_stops_without_recording_outcomes(self):
        def down(tier, task):
            raise ProviderFailure('URLError: connection refused')
        checks = []
        def health():
            checks.append(1)
            return {'ready': len(checks) == 1, 'problems': [] if len(checks) == 1 else ['economy: unreachable']}
        study = Study(self.root/'down', make_plan(), infer=down, health=health)
        with self.assertRaises(HealthError):
            study.run()
        p = study.progress()
        self.assertEqual(p['failed'], 0)
        self.assertEqual(p['state'], 'INCOMPLETE')
        self.assertEqual(study.sessions()[-1]['end_state'], 'STOPPED')

    def test_health_check_reports_unreachable_servers_and_vram(self):
        plan = {'urls': {'economy': 'http://127.0.0.1:9', 'balanced': 'http://127.0.0.1:9'}, 'models': FAKE_MODELS}
        result = check_health(plan, telemetry=lambda: {'label': 'MEASURED', 'vram_used_mib': 4000, 'vram_total_mib': 4096})
        self.assertFalse(result['ready'])
        self.assertTrue(any('unreachable' in p and 'run_local.py --tier economy' in p for p in result['problems']))
        self.assertTrue(any('VRAM headroom 96 MiB' in p for p in result['problems']))
        result = check_health(plan, telemetry=lambda: {'label': 'BLOCKED'})
        self.assertTrue(any('GPU telemetry unavailable' in p for p in result['problems']))

    def test_failed_health_check_dispatches_nothing(self):
        counter = Counting()
        study = Study(self.root/'h', make_plan(), infer=counter, health=lambda: {'ready': False, 'problems': ['x']})
        with self.assertRaises(HealthError):
            study.run()
        self.assertEqual((counter.calls, study.ledger.attempts()), ([], []))

    def test_incomplete_stays_incomplete_in_report(self):
        holder = [None]
        study = holder[0] = Study(self.root/'i', make_plan(), infer=fake_infer, health=HEALTHY,
                                  hooks={'before_outcome': stop_after(5, holder)})
        with self.assertRaises(Stop):
            study.run()
        r = report(study)
        self.assertEqual((r['progress']['state'], r['progress']['complete'], r['progress']['winner']),
                         ('INCOMPLETE', False, None))
        self.assertIn('No winner: comparison incomplete.', markdown(r))
        self.assertIn('5/64 finished', markdown(r))

    def test_outcomes_are_write_once_and_plan_bound(self):
        study = self.baseline()
        db = sqlite3.connect(study.db_path)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute("UPDATE outcomes SET status='failed'")
            with self.assertRaises(sqlite3.DatabaseError):
                db.execute('DELETE FROM outcomes')
        finally:
            db.close()
        with self.assertRaises(ValueError):
            Study(self.root/'baseline', make_plan(budget=700000))


if __name__ == '__main__':
    unittest.main()
