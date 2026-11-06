"""A conservative observed-quality router; no uncalibrated bandit claims."""
from collections import defaultdict
import hashlib
import random
from .providers import CATALOG

RANKS = {"economy": 0, "local-gpu": 0, "balanced": 1,
         "premium": 2, "hosted-premium": 2, "metal-provider": 3}
PRIORS = {"metal-provider": .5, "local-gpu": .5, "hosted-premium": .5}


class Router:
    @staticmethod
    def select_fx(offers, rates, **limits):
        from .fx_router import compare
        return compare(offers, rates, **limits)

    def __init__(self, seed=0):
        self.seed = seed
        self.stats = defaultdict(lambda: [0, 0])

    def observe(self, provider, kind, passed):
        row = self.stats[(provider, kind)]
        row[0] += int(passed)
        row[1] += 1

    def select(self, offers, task, job, attempted):
        allowed = [q for q in offers if q.price <= job["price_cap"]
                   and q.price + 1000 <= job["budget"] - job["spent"]]
        if attempted:
            rank = max(RANKS[p] for p in attempted)
            allowed = [q for q in allowed if RANKS[q.provider] > rank]
        if not allowed:
            return None, "No quote fits the remaining hold, price cap and escalation policy"
        if job["policy"] == "metal-probe":
            allowed = [q for q in allowed if q.provider == "metal-provider"]
            return (allowed[0], "Explicit real Metal testnet tier; no simulator fallback") if allowed else (None, "Metal testnet quote unavailable")
        if job["policy"] == "real-cheapest":
            allowed = [q for q in allowed if q.provider == "local-gpu"]
            return (min(allowed, key=lambda q: (q.price, q.latency_ms)), "Measured local GPU only; no simulator fallback") if allowed else (None, "Local GPU quote unavailable")
        if job["policy"] == "real-premium":
            allowed = [q for q in allowed if q.provider == "hosted-premium"]
            return (allowed[0], "Hosted premium only; no simulator fallback") if allowed else (None, "Hosted premium quote unavailable")
        if job["policy"] == "real-touchstone":
            allowed = [q for q in allowed if q.provider in {"local-gpu", "hosted-premium"}]
            if not allowed:
                return None, "No real inference quote is available; simulator fallback is disabled"
            selected = min(allowed, key=lambda q: (RANKS[q.provider], q.price, q.latency_ms))
            return selected, "Measured local GPU first; escalate to hosted premium only after a paid verifier rejection"
        if job["policy"] == "always-premium":
            allowed = [q for q in allowed if q.provider == "premium"]
            return (allowed[0], "Fixed premium baseline") if allowed else (None, "Premium exceeds policy")
        if job["policy"] == "always-cheapest":
            return min(allowed, key=lambda q: (q.price, q.provider)), "Lowest eligible price; one attempt baseline"
        if job["policy"] == "thompson":
            candidates = []
            for quote in allowed:
                successes, attempts = self.stats[(quote.provider, task.kind)]
                prior = CATALOG.get(quote.provider, {}).get("prior", PRIORS.get(quote.provider, .5))
                alpha = 4 * prior + successes
                beta = 4 * (1 - prior) + attempts - successes
                seed = int(hashlib.sha256(f"{self.seed}:{task.id}:{len(attempted)}:{quote.provider}".encode()).hexdigest()[:16], 16)
                sample = random.Random(seed).betavariate(max(.01, alpha), max(.01, beta))
                utility = sample / max(.01, quote.price / 10000 + quote.latency_ms / 10000)
                candidates.append((utility, quote, sample))
            _, chosen, sample = max(candidates, key=lambda item: (item[0], item[1].provider))
            return chosen, f"Thompson sample {sample:.1%}; price and latency weighted within hard caps"
        candidates = []
        for q in allowed:
            ok, n = self.stats[(q.provider, task.kind)]
            # Priors are simulator settings, not measured GPU quality or confidence bounds.
            prior = CATALOG.get(q.provider, {}).get("prior", PRIORS.get(q.provider, .5))
            estimate = (ok + 4 * prior) / (n + 4)
            utility = q.price / max(.05, estimate) + q.latency_ms * 20 + (1 - estimate) * 90000
            candidates.append((utility, q, estimate))
        _, chosen, estimate = min(candidates, key=lambda x: (x[0], x[1].provider))
        return chosen, f"Observed-check estimate {estimate:.0%}; price, latency and retry-risk tradeoff within hard caps"
