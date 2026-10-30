"""A conservative observed-quality router; no uncalibrated bandit claims."""
from collections import defaultdict
from .providers import CATALOG


class Router:
    def __init__(self):
        self.stats = defaultdict(lambda: [0, 0])

    def observe(self, provider, kind, passed):
        row = self.stats[(provider, kind)]
        row[0] += int(passed)
        row[1] += 1

    def select(self, offers, task, job, attempted):
        allowed = [q for q in offers if q.price <= job["price_cap"]
                   and q.price + 1000 <= job["budget"] - job["spent"]]
        if attempted:
            rank = max(CATALOG[p]["rank"] for p in attempted)
            allowed = [q for q in allowed if CATALOG[q.provider]["rank"] > rank]
        if not allowed:
            return None, "No quote fits the remaining hold, price cap and escalation policy"
        if job["policy"] == "always-premium":
            allowed = [q for q in allowed if q.provider == "premium"]
            return (allowed[0], "Fixed premium baseline") if allowed else (None, "Premium exceeds policy")
        if job["policy"] == "always-cheapest":
            return min(allowed, key=lambda q: (q.price, q.provider)), "Lowest eligible price; one attempt baseline"
        candidates = []
        for q in allowed:
            ok, n = self.stats[(q.provider, task.kind)]
            # Priors are simulator settings, not measured GPU quality or confidence bounds.
            prior = CATALOG[q.provider]["prior"]
            estimate = (ok + 4 * prior) / (n + 4)
            utility = q.price / max(.05, estimate) + q.latency_ms * 20 + (1 - estimate) * 90000
            candidates.append((utility, q, estimate))
        _, chosen, estimate = min(candidates, key=lambda x: (x[0], x[1].provider))
        return chosen, f"Observed-check estimate {estimate:.0%}; price, latency and retry-risk tradeoff within hard caps"
