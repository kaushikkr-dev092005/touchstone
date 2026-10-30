"""Public tasks and private benchmark truth live in separate objects."""
from dataclasses import dataclass, asdict
import random


@dataclass(frozen=True)
class Task:
    id: str
    kind: str
    source: dict
    min_quality: float = 1.0

    def public(self):
        return asdict(self)


def generate(seed=42, count=200):
    rng = random.Random(seed)
    tasks, truth = [], {}
    for i in range(count):
        task_id = f"step-{i:04d}"
        kind = ("invoice", "arithmetic", "classification")[i % 3]
        if kind == "invoice":
            qty, unit = rng.randint(1, 25), rng.randint(150, 15000)
            source = {"text": f"Invoice INV-{seed}-{i}. Currency USD. Quantity {qty}. Unit price {unit} cents. Tax 0 cents."}
            answer = {"invoice_id": f"INV-{seed}-{i}", "currency": "USD", "total_cents": qty * unit}
        elif kind == "arithmetic":
            items = [rng.randint(100, 50000) for _ in range(3)]
            source = {"amounts_cents": items, "discount_cents": rng.randint(1, 99)}
            answer = {"total_cents": sum(items) - source["discount_cents"]}
        else:
            label = rng.choice(["billing", "technical", "shipping"])
            texts = {"billing": "I was charged twice on my latest invoice.", "technical": "The application crashes when I try to sign in.", "shipping": "My parcel has not arrived and tracking is delayed."}
            source = {"text": texts[label]}
            answer = {"label": label}
        tasks.append(Task(task_id, kind, source))
        truth[task_id] = answer
    return tasks, truth


def score_truth(tasks, truth, accepted):
    """Offline only; never called by routing or verification."""
    return sum(accepted.get(t.id) == truth[t.id] for t in tasks)
