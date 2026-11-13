"""Explicitly authorized live (Metal testnet) mode for the dashboard.

Live mode never starts implicitly. The operator names an exact mandate (scope, step count, total
budget, per-call cap, provider origins) and must repeat the generated authorization phrase on
the command line. The mandate is then bound to its scope on disk: a later start with different
limits is refused. The browser can only start the one pre-authorized run, and only by
re-entering the exact budget. Simulated demo, simulated settlement and simulated limit
increases are disabled so a live ledger cannot be mixed with synthetic state.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from .fault_pipeline import FaultPipeline, metal_record_source
from .holds import micro_usd
from .ledger import Ledger, canonical
from .metal import MetalRail, task_resource_url
from .payments import CompositeRail, MetalEngineRail, MockRail
from .engine import Engine
from .workload import generate

PROVIDER_IDS = ['local-gpu', 'hosted-premium']


@dataclass(frozen=True)
class LiveMandate:
    scope: str
    provider_urls: tuple
    budget: int
    price_cap: int
    steps: int = 30
    seed: int = 42

    def validate(self):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', self.scope):
            raise ValueError('Live scope must be 1-48 letters, digits, underscores or hyphens')
        if type(self.budget) is not int or type(self.price_cap) is not int or not 0 < self.price_cap <= self.budget:
            raise ValueError('Require a positive budget and a per-call cap no greater than the budget')
        if self.budget > 5_000_000:
            raise ValueError('Live testnet mandates are limited to 5.00 USDZ')
        if not 1 <= self.steps <= 50 or type(self.seed) is not int:
            raise ValueError('Use 1 to 50 live steps')
        if not self.provider_urls or len(set(self.provider_urls)) != len(self.provider_urls) or len(self.provider_urls) > 2:
            raise ValueError('Provide one or two distinct approved provider origins')
        for url in self.provider_urls:
            task_resource_url(url, generate(self.seed, 1)[0][0])
        return self

    @property
    def policy(self):
        return 'real-touchstone' if len(self.provider_urls) == 2 else 'metal-probe'

    def terms(self):
        tasks = generate(self.seed, self.steps)[0]
        return {'scope': self.scope, 'provider_urls': list(self.provider_urls), 'budget': self.budget,
                'price_cap': self.price_cap, 'steps': self.steps, 'seed': self.seed, 'policy': self.policy,
                'task_digest': hashlib.sha256(json.dumps([t.public() for t in tasks], sort_keys=True).encode()).hexdigest()}

    def digest(self):
        return hashlib.sha256(canonical(self.terms()).encode()).hexdigest()

    def phrase(self):
        return (f'AUTHORIZE LIVE TESTNET SPEND scope={self.scope} budget={self.budget/1e6:.6f} '
                f'cap={self.price_cap/1e6:.6f} steps={self.steps} terms={self.digest()[:12]}')


def mandate_from_args(scope, provider_urls, budget_usd, price_cap_usd, steps=30, seed=42):
    return LiveMandate(scope, tuple(provider_urls), micro_usd(budget_usd), micro_usd(price_cap_usd), steps, seed).validate()


class LiveSession:
    """A live engine bound to exactly one authorized mandate."""

    def __init__(self, data_dir, mandate, authorization, *, client_factory=MetalRail, record_source=None,
                 signer=None, submitter=None, ack_verifier=None):
        mandate.validate()
        if authorization != mandate.phrase():
            raise ValueError('Live mode needs the exact authorization phrase for this mandate: ' + mandate.phrase())
        self.mandate = mandate
        self.directory = Path(data_dir) / 'metal-engine'
        self.directory.mkdir(parents=True, exist_ok=True)
        scope_file = self.directory / (mandate.scope + '.json')
        terms = mandate.terms()
        self.ledger = Ledger(self.directory / 'ledger.sqlite')
        if scope_file.exists():
            saved = json.loads(scope_file.read_text(encoding='utf-8'))
            if saved['mandate'] != terms:
                raise ValueError('Scope is already bound to different tasks or limits; recover the original scope')
            self.run_id = saved['run_id']
        else:
            tasks = generate(mandate.seed, mandate.steps)[0]
            self.run_id = self.ledger.create_run([{'seed': mandate.seed, 'policy': mandate.policy, 'hold': mandate.budget,
                'price_cap': mandate.price_cap, 'allocation': mandate.budget, 'tasks': [t.public() for t in tasks]}],
                mandate.budget, float_mode='TESTNET')
            scope_file.write_text(json.dumps({'run_id': self.run_id, 'mandate': terms}, indent=2) + '\n', encoding='utf-8')
        urls = list(mandate.provider_urls)
        client = client_factory(mandate.scope, urls[0], mandate.price_cap, mandate.budget, execute=True)
        self.live_rail = MetalEngineRail(mandate.scope, urls, mandate.price_cap, mandate.budget, client=client,
                                         expected_provider_ids=PROVIDER_IDS if len(urls) == 2 else None)
        self.rail = CompositeRail(MockRail(self.directory / mandate.scope / 'simulated-rail.sqlite'), self.live_rail)
        kwargs = {k: v for k, v in (('signer', signer), ('submitter', submitter), ('ack_verifier', ack_verifier)) if v}
        self.faults = FaultPipeline(self.ledger, record_source or metal_record_source(self.live_rail),
                                   wallet_scope=mandate.scope, **kwargs)
        self.engine = Engine(self.ledger, self.rail, fault_pipeline=self.faults)
        # TESTNET runs always enforce per-purchase human signatures in Ledger;
        # the written session phrase does not substitute for that approval.

    def confirm(self, value):
        if not isinstance(value, str) or value != f'{self.mandate.budget/1e6:.6f}':
            raise ValueError(f'Confirm the exact authorized budget ({self.mandate.budget/1e6:.6f} USD) to start live purchases')

    def describe(self):
        job = self.ledger.jobs(self.run_id)[0]
        return {'mode': 'LIVE_TESTNET_AUTHORIZED', 'scope': self.mandate.scope, 'run_id': self.run_id,
                'policy': self.mandate.policy, 'budget_micro_usd': self.mandate.budget,
                'price_cap_micro_usd': self.mandate.price_cap, 'steps': self.mandate.steps,
                'providers': len(self.mandate.provider_urls), 'terms_sha256': self.mandate.digest(),
                'spent_micro_usd': job['spent'], 'rail_spent_micro_usd': job['rail_spent'], 'job_status': job['status'],
                'customer_hold': 'SIMULATED', 'customer_captured_micro_usd': 0,
                'asset': 'testnet USDZ; no fiat movement', 'fault_receipts': self.faults.receipts()}

    def quote_preview(self):
        """Fetch live quotes for the first task. Dispatches nothing."""
        task = generate(self.mandate.seed, 1)[0][0]
        offers = self.live_rail.quote_for_task(task)
        offers = offers if isinstance(offers, list) else [offers]
        return {'mode': 'LIVE_QUOTE_ONLY', 'payments_sent': 0,
                'quotes': [{'provider': q.provider, 'price_micro_usd': q.price, 'latency_ms': q.latency_ms,
                            'queue_depth': q.queue_depth, 'expires_at': q.expires_at} for q in offers if q is not None],
                'errors': getattr(self.live_rail, 'last_quote_errors', [])}
