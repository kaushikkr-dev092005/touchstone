"""Matched M4 experiment. Dispatch sees sources; truth is used only in scoring."""
import hashlib
from contextlib import ExitStack
import json
import math
from pathlib import Path
import platform
import random
import re
import sqlite3
import subprocess
import time
import urllib.request
import urllib.error

from .config import ROOT
from .engine import Engine
from .invoice_dataset import build, DATASET_VERSION
from .invoice_extraction import deterministic, duplicate_reference, verify, VERSION
from .invoice_profile import save
from .invoice_study import evaluate_profile
from .ledger import Ledger, PolicyError, canonical
from .leases import exclusive
from .metal import MetalRail, PaymentPending, task_resource_url
from .payments import MetalEngineRail
from .treasury import NoRedirect
from .verifier import VERIFY_COST
from .workload import Task

POLICIES = ('tools-only', 'always-cheapest', 'always-premium', 'touchstone-ladder')
TIERS = ('local-gpu', 'hosted-premium')
PENDING = {'RESERVED', 'DISPATCHING', 'PAID'}


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def implementation():
    paths = ['touchstone/comparison.py', 'touchstone/invoice_dataset.py',
             'touchstone/invoice_extraction.py', 'touchstone/ledger.py',
             'touchstone/invoice_study.py', 'touchstone/eligibility.py', 'touchstone/providers.py',
             'touchstone/payments.py', 'touchstone/metal.py',
             'integrations/metal/provider.mjs', 'integrations/metal/provider-core.mjs', 'integrations/metal/m4-chaos.mjs',
             'integrations/metal/package-lock.json']
    return {p: hashlib.sha256((ROOT/p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in paths}


def prepare(scope, origins, budget, price_cap, max_purchases=40, steps=12,
            seeds=(20261120,), outage_index=3, quality_index=7, profiles=None):
    if not isinstance(scope, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,36}', scope):
        raise ValueError('Use a dedicated existing-wallet scope of 1–36 safe characters')
    if (any(type(n) is not int for n in (budget, price_cap, max_purchases, steps, outage_index, quality_index))
            or not 3 <= steps <= 50 or not 1 <= max_purchases <= 250
            or not 0 <= outage_index < steps or not 0 <= quality_index < steps
            or outage_index == quality_index or not 0 < price_cap + VERIFY_COST <= budget):
        raise ValueError('Invalid budget, call count, step count or fault indices')
    if not seeds or len(set(seeds)) != len(seeds) or len(seeds) > 5 or any(type(s) is not int or not 0 <= s < 2**31 for s in seeds):
        raise ValueError('Use one to five distinct nonnegative integer seeds')
    if set(origins) != set(TIERS) or len(set(origins.values())) != 2:
        raise ValueError('Two distinct named provider origins are required')
    origins = {tier: origins[tier].rstrip('/') for tier in TIERS}
    dummy = Task('origin-check', 'arithmetic', {'amounts_cents': [1], 'discount_cents': 0})
    for origin in origins.values():
        task_resource_url(origin, dummy)
    qualifications = {}
    records, truth = build()
    for tier, path in (profiles or {}).items():
        if tier not in TIERS:
            raise ValueError('Unknown qualification tier')
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
        result = evaluate_profile(records, truth, raw)
        if tier == 'local-gpu' and raw['tier'] not in {'economy', 'balanced'} or tier == 'hosted-premium' and raw['tier'] != tier:
            raise ValueError('Qualification profile belongs to another tier')
        qualifications[tier] = {'eligible': result['eligible'], 'model_id': raw['model_id'],
                                'profile_sha256': fingerprint(raw), 'model_sha256': raw.get('model_sha256')}
    tasks = []
    for seed in seeds:
        records, _ = build(seed)
        rng = random.Random(seed)
        candidates = records[1:]
        rng.shuffle(candidates)
        selected = [records[0], *candidates[:steps-1]]
        for index, row in enumerate(selected):
            tasks.append({'seed': seed, 'index': index, 'source_id': row['task']['id'],
                          'template_id': row['template_id'], 'partition': row['partition'],
                          'task': row['task']})
    faults = {}
    for row in tasks:
        fault = 'outage' if row['index'] == outage_index else 'quality-drop' if row['index'] == quality_index else None
        if fault:
            for policy in POLICIES:
                faults[task_id(row, policy)] = {'local-gpu': fault}
    schedule = {'version': 1, 'faults': faults}
    plan = {'version': 1, 'label': 'SIMULATED', 'execution_status': 'BLOCKED_PENDING_APPROVAL_AND_PREFLIGHT',
            'scope': scope, 'origins': origins, 'aggregate_cap_micro_usdz': budget,
            'per_call_cap_micro_usdz': price_cap, 'max_purchases': max_purchases,
            'steps_per_policy_per_seed': steps, 'seeds': list(seeds), 'policies': list(POLICIES),
            'outage_index': outage_index, 'quality_index': quality_index, 'fault_target': 'local-gpu',
            'tasks': tasks, 'task_digest': fingerprint(tasks), 'schedule': schedule,
            'schedule_sha256': fingerprint(schedule), 'qualifications': qualifications,
            'code_sha256': implementation(), 'dataset_version': DATASET_VERSION, 'verifier_version': VERSION,
            'verification_fee_micro_usd': VERIFY_COST, 'verification_fee_label': 'SIMULATED',
            'upstream_dollars': 'UNMEASURED_PARTNER_CREDITS_SEPARATE_FROM_USDZ'}
    return {**plan, 'plan_sha256': fingerprint(plan)}


def task_id(row, policy):
    return f"M4-{row['seed']}-{row['index']}-{POLICIES.index(policy)}"


def validate(plan):
    if fingerprint({k: v for k, v in plan.items() if k != 'plan_sha256'}) != plan.get('plan_sha256'):
        raise ValueError('Plan hash mismatch')
    if plan.get('code_sha256') != implementation():
        raise ValueError('Implementation changed; prepare a new plan and approval')
    if plan.get('policies') != list(POLICIES) or fingerprint(plan['tasks']) != plan['task_digest']:
        raise ValueError('Comparison plan is not a matched four-policy workload')


def read_health(origin):
    with urllib.request.build_opener(NoRedirect()).open(origin+'/health', timeout=5) as response:
        return json.loads(response.read(50000))


def observe_outage(url, schedule_hash):
    try:
        with urllib.request.build_opener(NoRedirect()).open(url, timeout=5):
            return False
    except urllib.error.HTTPError as error:
        return (error.code == 503 and error.headers.get('X-Touchstone-Fault') == 'outage'
                and error.headers.get('X-Touchstone-Scenario-SHA256') == schedule_hash)
    except OSError:
        return False


def environment(plan, health, label):
    node, gpu = 'UNMEASURED', 'UNMEASURED'
    if label == 'MEASURED':
        from .metal import node_executable
        try:
            node = subprocess.check_output([node_executable(), '--version'], text=True, timeout=5).strip()
        except (OSError, RuntimeError, subprocess.SubprocessError):
            pass
        try:
            gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                '--format=csv,noheader'], text=True, timeout=5).strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return {'label': label, 'python': platform.python_version(), 'os': platform.system(),
            'architecture': platform.machine(), 'sqlite': sqlite3.sqlite_version, 'node': node,
            'buyer_gpu_and_driver': gpu, 'provider_gpu': 'UNMEASURED',
            'provider_identity': 'SELLER_REPORTED', 'providers': health, 'chain_id': 63825,
            'plan_sha256': plan['plan_sha256'], 'code_sha256': plan['code_sha256'],
            'seeds': plan['seeds'], 'task_digest': plan['task_digest'], 'discarded_warmups': 0,
            'decoding': 'temperature 0; invoice output max_tokens 2400; see hashed providers.py',
            'node_lock_sha256': plan['code_sha256']['integrations/metal/package-lock.json']}


class Comparison:
    def __init__(self, plan, directory, client_factory=MetalRail, health_reader=read_health, rpc_reader=None, fault_reader=observe_outage):
        validate(plan)
        self.plan, self.directory = plan, Path(directory)
        self.factory, self.health_reader, self.rpc_reader = client_factory, health_reader, rpc_reader
        self.fault_reader = fault_reader
        self.live = client_factory is MetalRail
        self.label = 'MEASURED' if self.live else 'MOCK'
        self.wallet_owner = (ROOT/'data/metal'/plan['scope']/'m4-owner.sqlite' if self.live else
                             Path(getattr(client_factory, 'directory', self.directory))/(plan['scope']+'-m4-owner.sqlite'))

    def client(self, execute=False):
        p = self.plan
        args = (p['scope'], p['origins']['local-gpu'], p['per_call_cap_micro_usdz'], p['aggregate_cap_micro_usdz'])
        return self.factory(*args, execute=execute) if self.live else self.factory(*args)

    def preflight(self, spent=0, paid_count=0):
        p = self.plan
        checks, health, client = {}, {}, None
        for tier in TIERS:
            try:
                raw = self.health_reader(p['origins'][tier])
                keep = ('chain', 'provider_id', 'provider_type', 'provider_model', 'provider_model_sha256',
                        'inference_ready', 'upstream_funding', 'chaos', 'chaos_schedule_sha256')
                health[tier] = {k: raw.get(k) for k in keep}
                checks[tier] = (raw.get('chain') == 63825 and raw.get('provider_id') == tier
                    and raw.get('inference_ready') is True and raw.get('chaos') == 'none'
                    and raw.get('chaos_schedule_sha256') == p['schedule_sha256']
                    and raw.get('provider_type') == ('model' if tier == 'local-gpu' else 'anthropic')
                    and isinstance(raw.get('provider_model'), str) and bool(raw['provider_model'])
                    and (tier != 'hosted-premium' or raw.get('upstream_funding') == 'PARTNER_CREDITS_OPERATOR_DECLARED'))
            except Exception:
                checks[tier] = False
        checks['existing_wallet'] = not self.live or (ROOT/'data/metal'/p['scope']/'wallet.sqlite').is_file()
        checks['rpc_chain_63825'] = False
        if all(checks[k] for k in (*TIERS, 'existing_wallet')):
            try:
                from .rpc import inspect_rpc
                rpc = (self.rpc_reader or inspect_rpc)()
                checks['rpc_chain_63825'] = rpc.get('chain_id') == 63825 and rpc.get('connected') is True
                if checks['rpc_chain_63825']:
                    client = self.client()
                    balance = client.balance()
                    checks['clearing_balance'] = (balance.get('pending_invoice') is False
                        and int(balance['spendable_base_units']) >= (p['aggregate_cap_micro_usdz']-spent)*10**12
                        and balance.get('historical_payments') == paid_count)
                    rail = MetalEngineRail(p['scope'], [p['origins'][t] for t in TIERS], client=client,
                                           expected_provider_ids=list(TIERS))
                    row = next(r for r in p['tasks'] if r['index'] not in (p['outage_index'], p['quality_index']))
                    offers = rail.quote_for_task(Task(task_id(row, POLICIES[1]), 'invoice_extraction', row['task']['source']))
                    checks['both_valid_quotes'] = {q.provider for q in offers} == set(TIERS)
            except Exception:
                checks['wallet_or_quote_read'] = False
        return {'label': 'MEASURED' if all(checks.values()) and self.live else 'MOCK' if all(checks.values()) else 'BLOCKED',
                'ready': all(checks.values()), 'checks': checks, 'health': health, 'payments_sent': 0,
                'required_chain_id': 63825, 'verified_chain_id': 63825 if checks['rpc_chain_63825'] else None,
                'plan_sha256': p['plan_sha256'],
                'wallet_balance_assurance': 'OPERATOR_ESTIMATE_NOT_FINALITY',
                'qualification_status': {t: p['qualifications'].get(t, {}).get('eligible', False) for t in TIERS}}

    def run(self, execute=False, approved_cap=None, approved_calls=None, allow_baselines=False):
        p = self.plan
        if (not execute or approved_cap != p['aggregate_cap_micro_usdz'] or approved_calls != p['max_purchases']
                or not allow_baselines):
            raise ValueError('Require --execute, matching approved aggregate/call caps and --allow-unqualified-baselines')
        self.directory.mkdir(parents=True, exist_ok=True)
        with ExitStack() as owners:
            owners.enter_context(exclusive(self.directory/'owner.sqlite'))
            if not self.live or (ROOT/'data/metal'/p['scope']/'wallet.sqlite').is_file():
                owners.enter_context(exclusive(self.wallet_owner))
            journal = self.directory/'journal.json'
            state = json.loads(journal.read_text()) if journal.exists() else None
            if state and (state['plan_sha256'] != p['plan_sha256'] or state['label'] != self.label):
                raise ValueError('Scope already belongs to a different plan or evidence mode')
            ledger = Ledger(self.directory/'ledger.sqlite')
            if any(a['state'] in PENDING for a in ledger.attempts()):
                raise PaymentPending('Original purchase is unresolved; no retry, replacement or new purchase permitted')
            if state and state.get('complete'):
                return self.report()
            readiness = self.preflight(sum(j['rail_spent'] for j in ledger.jobs()), sum(bool(a['receipt']) for a in ledger.attempts()))
            save(self.directory/'preflight.json', readiness)
            if not readiness['ready']:
                raise RuntimeError('M4 preflight blocked; inspect redacted preflight.json; zero new purchases')
            if state is None:
                tasks = [Task(task_id(r, policy), 'invoice_extraction', r['task']['source']).public()
                         for r in p['tasks'] for policy in POLICIES]
                run = ledger.create_run([dict(seed=0, policy='m4-comparison', hold=approved_cap,
                    allocation=approved_cap, price_cap=p['per_call_cap_micro_usdz'], tasks=tasks)], approved_cap, 'TESTNET')
                state = {'label': self.label, 'plan_sha256': p['plan_sha256'], 'run_id': run,
                         'rows': [], 'calls': {}, 'complete': False, 'stop_reason': None}
                save(journal, state)
            job = ledger.jobs(state['run_id'])[0]
            client = self.client(execute=True)
            rail = MetalEngineRail(p['scope'], [p['origins'][t] for t in TIERS], client=client,
                                   expected_provider_ids=list(TIERS))
            save(self.directory/'environment.json', environment(p, readiness['health'], self.label))
            failed = False
            with ledger.worker(job['id']) as owner:
                done = {r['task']['id'] for r in state['rows']}
                try:
                    for row in p['tasks']:
                        order = list(POLICIES)
                        random.Random(row['seed']).shuffle(order)
                        for policy in order:
                            task = Task(task_id(row, policy), 'invoice_extraction', row['task']['source'])
                            if task.id in done:
                                continue
                            result = self.step(row, policy, task, ledger, job, owner, rail, state, journal, readiness)
                            state['rows'].append(result)
                            save(journal, state)
                    state['complete'] = True
                except Exception as error:
                    state['stop_reason'] = type(error).__name__
                    save(journal, state)
                    failed = True
            if failed:
                self.write_report(state, ledger, rail)
                raise RuntimeError('M4 stopped safely; inspect report.json; do not retry an uncertain purchase')
            state['stop_reason'] = None
            save(journal, state)
            return self.write_report(state, ledger, rail)

    def step(self, row, policy, task, ledger, job, owner, rail, state, journal, readiness):
        started = time.perf_counter()
        base = {k: row[k] for k in ('seed', 'index', 'source_id', 'template_id', 'partition')}
        result = {**base, 'task': task.public(), 'policy': policy, 'output': None, 'accepted': False,
                  'decision': 'review', 'calls': [], 'fault': self.plan['schedule']['faults'].get(task.id, {})}
        if policy != 'tools-only' and row['index'] == self.plan['outage_index']:
            result['observed_outage'] = self.fault_reader(task_resource_url(self.plan['origins']['local-gpu'], task), self.plan['schedule_sha256'])
            result['experiment_probe_ms'] = round((time.perf_counter()-started)*1000)
            started = time.perf_counter()
        if policy in ('tools-only', 'touchstone-ladder'):
            result['output'] = deterministic(task)
            verdict = verify(task, result['output'])
            if result['output'] is not None or policy == 'tools-only' or duplicate_reference(task):
                result.update(accepted=verdict['passed'] and verdict['decision'] == 'candidate', decision=verdict['decision'],
                              tool_used=True, verifier=verdict)
                result['latency_ms'] = round((time.perf_counter()-started)*1000)
                return result
        tiers = ['cheapest'] if policy == 'always-cheapest' else ['hosted-premium'] if policy == 'always-premium' else list(TIERS)
        for tier in tiers:
            if policy == 'touchstone-ladder':
                q = self.plan['qualifications'].get(tier, {})
                h = readiness['health'][tier]
                if not (q.get('eligible') and q['model_id'] == h['provider_model']
                        and (tier != 'local-gpu' or q.get('model_sha256') and q['model_sha256'] == h.get('provider_model_sha256'))):
                    continue
            old = next((a for a in ledger.attempts(job['id']) if a['step_id'] == task.id and (tier == 'cheapest' or a['provider'] == tier)), None)
            if old is None:
                if len(ledger.attempts(job['id'])) >= self.plan['max_purchases']:
                    raise PolicyError('Aggregate purchase count exhausted')
                before = time.perf_counter()
                offers = rail.quote_for_task(task)
                result.setdefault('quote_failures', []).extend({k: e[k] for k in ('origin_index', 'error')} for e in rail.last_quote_errors)
                offer = min(offers, key=lambda q: (q.price, q.provider)) if tier == 'cheapest' and offers else next((q for q in offers if q.provider == tier), None)
                if offer is None:
                    continue
                key = ledger.reserve(job['id'], task, len(result['calls']), offer, VERIFY_COST, expected_version=job['mandate_version'])
                state['calls'][key] = {'label': self.label, 'reservation_key': key, 'provider': offer.provider, 'status': 'RESERVED',
                                        'policy': policy, 'task_id': task.id, 'seed': row['seed'], 'index': row['index'],
                                        'price_micro_usdz': offer.price, 'latency_ms': None}
                save(journal, state)
                ledger.assert_can_pay(key, owner)
                try:
                    receipt = rail.pay(key, offer)
                    ledger.record_paid(key, receipt)
                    metadata = receipt.get('provider_metadata') or {}
                    expected = readiness['health'][offer.provider]
                    if metadata.get('provider_model') != expected['provider_model'] or metadata.get('provider_type') != ('LOCAL_MODEL' if offer.provider == 'local-gpu' else 'ANTHROPIC_API'):
                        raise RuntimeError('Delivery model identity differs; retain charge and stop')
                    verdict = verify(task, receipt['output'])
                    ledger.finish_attempt(key, receipt['output'], verdict)
                except Exception:
                    state['calls'][key]['latency_ms'] = round((time.perf_counter()-before)*1000)
                    save(journal, state)
                    raise
                state['calls'][key].update(status='VERIFIED', receipt_id=receipt['id'],
                    latency_ms=round((time.perf_counter()-before)*1000), provider_metadata=metadata)
                save(journal, state)
                old = next(a for a in ledger.attempts(job['id']) if a['key'] == key)
            result['calls'].append(old['key'])
            result['output'] = json.loads(old['output'])
            verdict = json.loads(old['verdict'])
            result.update(accepted=verdict['passed'] and verdict['decision'] == 'candidate', decision=verdict['decision'], verifier=verdict)
            if result['accepted'] or verdict['passed'] and verdict['decision'] == 'review':
                break
        result['latency_ms'] = round((time.perf_counter()-started)*1000) if not any(
            state['calls'].get(k, {}).get('latency_ms') is None for k in result['calls']) else None
        return result

    def write_report(self, state, ledger, rail=None):
        p = self.plan
        attempts = ledger.attempts()
        jobs = ledger.jobs(state['run_id'])
        pending = sum(a['state'] in PENDING for a in attempts)
        exposure = sum(a['price']+a['verify_cost'] for a in attempts if a['state'] in PENDING)
        violations = []
        for job in jobs:
            if job['spent']+exposure > min(job['budget'], job['hold']) or job['rail_spent'] > job['allocation']:
                violations.append('HOLD_OR_FLOAT_EXCEEDED')
        if len(attempts) > p['max_purchases']:
            violations.append('PURCHASE_COUNT_EXCEEDED')
        if not ledger.audit()['valid']:
            violations.append('AUDIT_CHAIN_INVALID')
        reconciliation = {'matched': None, 'label': 'BLOCKED_READ_BACK_NOT_RUN'}
        if rail:
            try:
                reconciliation = Engine(ledger, rail).reconcile(state['run_id'])
            except Exception as error:
                reconciliation = {'matched': None, 'label': 'BLOCKED', 'error_type': type(error).__name__}
        calls = {}
        for a in attempts:
            calls[a['key']] = {**state['calls'].get(a['key'], {}), 'reservation_key': a['key'],
                'price_micro_usdz': a['price'], 'receipt_id': a['receipt'],
                'status': 'VERIFIED' if a['passed'] is not None else a['state'],
                'provider_metadata': json.loads(a['provider_metadata']) if a['provider_metadata'] else {},
                'check_fee_micro_usd': a['verify_cost'] if a['passed'] is not None else 0}
        report = {'label': self.label, 'mode': 'TESTNET' if self.live else 'MOCK', 'plan_sha256': p['plan_sha256'],
                  'observed_at': time.time(),
                  'complete': state['complete'], 'stop_reason': state['stop_reason'], 'seeds': p['seeds'],
                  'rows': offline_score(p, state['rows']), 'calls': calls,
                  'pending_attempts': pending, 'cost_at_risk_micro_usdz_plus_demo_check_fee': exposure,
                  'confirmed_provider_micro_usdz': sum(a['price'] for a in attempts if a['receipt']),
                  'simulated_check_fee_micro_usd': sum(a['verify_cost'] for a in attempts if a['passed'] is not None),
                  'control_violations': violations, 'reconciliation': reconciliation, 'audit': ledger.audit(),
                  'upstream_api_dollars': 'UNMEASURED_PARTNER_CREDITS_NOT_INCLUDED',
                  'cost_labels': {'provider_micro_usdz': self.label, 'check_micro_usd': 'SIMULATED',
                                  'mixed_cost_per_verified_correct': 'SIMULATED_DEMO_RATE_NOT_SETTLEMENT'},
                  'customer_holds': 'SIMULATED_NO_CAPTURE', 'airwallex': 'SEPARATE_NOT_USED',
                  'raw_receipts': ('Original invoice/signed receipt/delivery retained in the existing scoped SDK store'
                                   if self.live else 'MOCK adapter records only; no Metal invoice or signature exists')}
        report['summary'] = summarize(report)
        report['by_seed'] = {str(seed): summarize(report, seed) for seed in p['seeds']}
        report['latency_scope'] = 'End-to-end policy task, including quote/payment/check and failures; excludes experiment-only outage attestation probe. Missing recovered timing stays null.'
        report['live_gate_passed'] = (self.live and report['complete'] and 30 <= len(attempts) <= 50*len(p['seeds']) and not pending
            and not violations and reconciliation['matched'] and any(
                c.get('provider_metadata', {}).get('chaos_mode') == 'quality-drop' for c in state['calls'].values())
            and any(r.get('observed_outage') is True and r['index'] == p['outage_index'] for r in report['rows']))
        save(self.directory/'report.json', report)
        (self.directory/'comparison.md').write_text(table(report), encoding='utf-8')
        return report

    def report(self):
        state = json.loads((self.directory/'journal.json').read_text())
        if state['plan_sha256'] != self.plan['plan_sha256']:
            raise ValueError('Report plan differs from journal')
        saved = self.directory/'report.json'
        if saved.exists():
            report = json.loads(saved.read_text())
            if report['plan_sha256'] == self.plan['plan_sha256']:
                return report
        return self.write_report(state, Ledger(self.directory/'ledger.sqlite'))


def offline_score(plan, rows):
    """Called after dispatch. Never supplies labels to the rail or policy."""
    truths = {seed: build(seed)[1] for seed in plan['seeds']}
    return [{**r, 'strict_correct': r['output'] == truths[r['seed']][r['source_id']]['output'],
             'false_accept': r['accepted'] and r['output'] != truths[r['seed']][r['source_id']]['output']}
            for r in rows]


def summarize(report, seed=None):
    summary = []
    for policy in POLICIES:
        rows = [r for r in report['rows'] if r['policy'] == policy and (seed is None or r['seed'] == seed)]
        calls = [c for c in report['calls'].values() if c.get('policy') == policy and (seed is None or c['seed'] == seed)]
        # Unfinished calls remain outside a successful row but must still be charged.
        known = {k for r in report['rows'] for k in r['calls']}
        orphan = [c for k, c in report['calls'].items() if k not in known and c.get('policy') == policy]
        latencies = sorted([r['latency_ms'] for r in rows if r['latency_ms'] is not None] +
                           [c['latency_ms'] for c in orphan if c.get('latency_ms') is not None])
        accepted = sum(r['accepted'] for r in rows)
        correct = sum(r['accepted'] and r['strict_correct'] for r in rows)
        cost = sum(c['price_micro_usdz'] for c in calls if c.get('receipt_id'))
        checks = sum(c['check_fee_micro_usd'] for c in calls)
        unresolved = any(c['status'] in PENDING for c in calls)
        summary.append({'policy': policy, 'completed_steps': len(rows), 'n_seeds': len({r['seed'] for r in rows}),
            'accepted': accepted, 'verified_correct': correct, 'refusals': sum(not r['accepted'] for r in rows),
            'false_accepts': sum(r['false_accept'] for r in rows),
            'false_accept_rate': sum(r['false_accept'] for r in rows)/accepted if accepted else None,
            'provider_micro_usdz': cost, 'simulated_check_micro_usd': checks,
            'mixed_cost_per_verified_correct': (cost+checks)/correct if correct and not unresolved else None,
            'provider_micro_usdz_per_verified_correct': cost/correct if correct and not unresolved else None,
            'cost_status': 'LOWER_BOUND_PENDING' if unresolved else 'CONFIRMED_INVOICE_AMOUNTS',
            'latency_samples': len(latencies), 'latency_p50_ms': latencies[(len(latencies)-1)//2] if latencies else None,
            'latency_p95_ms': latencies[math.ceil(len(latencies)*.95)-1] if latencies else None,
            'unfinished_latency_samples': sum(c.get('latency_ms') is not None for c in orphan),
            'unfinished_calls_in_report': len(orphan)})
    return summary


def table(report):
    lines = ['# M4 policy comparison', '', f"**{report['label']}** · complete={report['complete']} · n={len(report['seeds'])} seeds",
        '', 'USDZ service spend and SIMULATED micro-USD check fees are separate. Upstream API dollars, CPU and human review are unpriced.', '',
        '| Policy | Steps | Verified correct | Refusals | False accepts / accepted | Provider USDZ | USDZ / verified correct | Demo check USD | p50 / p95 ms |',
        '|---|---:|---:|---:|---|---:|---|---:|---|']
    for r in report['summary']:
        unit = f"{r['provider_micro_usdz_per_verified_correct']/1e6:.6f}" if r['provider_micro_usdz_per_verified_correct'] is not None else 'NOT MEASURED'
        lines.append(f"| {r['policy']} | {r['completed_steps']} | {r['verified_correct']} | {r['refusals']} | {r['false_accepts']} / {r['accepted']} | {r['provider_micro_usdz']/1e6:.6f} | {unit} | {r['simulated_check_micro_usd']/1e6:.6f} | {r['latency_p50_ms']} / {r['latency_p95_ms']} |")
    lines += ['', f"Pending: {report['pending_attempts']}; control violations: {report['control_violations']}; audit head: `{report['audit']['head']}`.", '',
              'Raw failures and unresolved exposure remain in report.json and the ledger. No null metric is a measured zero.', '']
    return '\n'.join(lines)


def main(argv=None):
    import argparse
    from .holds import micro_usd
    parser = argparse.ArgumentParser(description='M4 matched policies; no funding or automatic payment recovery')
    sub = parser.add_subparsers(dest='action', required=True)
    prep = sub.add_parser('prepare', help='Write public plan and deterministic seller schedule; zero network or payments')
    prep.add_argument('--scope', required=True)
    prep.add_argument('--local-origin', default='http://127.0.0.1:8092')
    prep.add_argument('--premium-origin', default='http://127.0.0.1:8095')
    prep.add_argument('--aggregate-cap-usdz', required=True)
    prep.add_argument('--price-cap-usdz', default='0.05')
    prep.add_argument('--max-purchases', type=int, default=40)
    prep.add_argument('--steps', type=int, default=16)
    prep.add_argument('--seeds', type=int, nargs='+', default=[20261120])
    prep.add_argument('--outage-index', type=int, default=3)
    prep.add_argument('--quality-index', type=int, default=7)
    prep.add_argument('--local-profile')
    prep.add_argument('--premium-profile')
    prep.add_argument('--output', required=True)
    for name in ('preflight', 'run', 'report'):
        stage = sub.add_parser(name)
        stage.add_argument('--plan', required=True)
        stage.add_argument('--state-dir', default='data/m4')
        stage.add_argument('--output', help='Write redacted output copy')
        if name == 'run':
            stage.add_argument('--execute', action='store_true')
            stage.add_argument('--aggregate-cap-usdz', required=True)
            stage.add_argument('--max-purchases', type=int, required=True)
            stage.add_argument('--allow-unqualified-baselines', action='store_true', help='Explicit experiment acknowledgement; ladder gates remain enforced')
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare':
            profiles = {tier: path for tier, path in zip(TIERS, (args.local_profile, args.premium_profile)) if path}
            result = prepare(args.scope, dict(zip(TIERS, (args.local_origin, args.premium_origin))),
                micro_usd(args.aggregate_cap_usdz), micro_usd(args.price_cap_usdz), args.max_purchases,
                args.steps, args.seeds, args.outage_index, args.quality_index, profiles)
            target = Path(args.output)
            schedule_path = target.with_name(target.stem+'-seller-schedule.json')
            if target.exists() or schedule_path.exists():
                raise ValueError('Preserve the existing plan; use a fresh output')
            save(target, result)
            save(schedule_path, result['schedule'])
            print(json.dumps({'label': 'BLOCKED', 'plan': str(target), 'plan_sha256': result['plan_sha256'],
                'seller_schedule': str(schedule_path),
                'payments_sent': 0, 'approval_required': True, 'total_policy_steps': len(result['tasks'])*4,
                'eligible_tiers': [t for t, q in result['qualifications'].items() if q['eligible']]}, indent=2))
            return 0
        plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
        runner = Comparison(plan, Path(args.state_dir)/plan['scope'])
        if args.action == 'preflight':
            result = runner.preflight()
        elif args.action == 'run':
            result = runner.run(args.execute, micro_usd(args.aggregate_cap_usdz), args.max_purchases, args.allow_unqualified_baselines)
        else:
            result = runner.report()
        if args.output:
            save(args.output, result)
        print(json.dumps(result if args.action == 'preflight' else {k: result[k] for k in
            ('label', 'complete', 'live_gate_passed', 'pending_attempts', 'control_violations', 'audit')}, indent=2))
        return 0 if args.action != 'preflight' or result['ready'] else 2
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'label': 'BLOCKED', 'error_type': type(error).__name__,
                          'message': 'Comparison stopped; inspect the redacted local report. No automatic retry.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
