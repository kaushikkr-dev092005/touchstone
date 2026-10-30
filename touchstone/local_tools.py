"""Small, explicitly bounded tools. No models, payments, or benchmark truth."""
import re

from .workload import Task

TOOL_VERSION = "bounded-tools-v1"
MAX_CENTS = 10**12
INVOICE = re.compile(
    r"Invoice (INV-[A-Za-z0-9-]{1,64})\. Currency USD\. Quantity ([0-9]{1,6})\. "
    r"Unit price ([0-9]{1,12}) cents\. Tax ([0-9]{1,12}) cents\."
)
# Exact supported messages only. Substring matches would accept negation or
# instructions appended to otherwise familiar text.
TICKETS = {
    "I was charged twice on my latest invoice.": "billing",
    "The application crashes when I try to sign in.": "technical",
    "My parcel has not arrived and tracking is delayed.": "shipping",
}


def solve(task: Task):
    """Return an answer only for a validated input contract; otherwise abstain."""
    if type(task.min_quality) not in {int, float} or not 0 <= task.min_quality <= 1:
        return None
    if type(task.source) is not dict:
        return None
    source = task.source
    if task.kind == "arithmetic":
        if set(source) != {"amounts_cents", "discount_cents"}:
            return None
        amounts, discount = source["amounts_cents"], source["discount_cents"]
        if type(amounts) is not list or not 1 <= len(amounts) <= 1000:
            return None
        if any(type(n) is not int or not 0 <= n <= MAX_CENTS for n in amounts):
            return None
        if type(discount) is not int or not 0 <= discount <= sum(amounts) <= MAX_CENTS:
            return None
        return {"total_cents": sum(amounts) - discount}
    if set(source) != {"text"} or type(source["text"]) is not str:
        return None
    if task.kind == "invoice":
        match = INVOICE.fullmatch(source["text"])
        if not match:
            return None
        invoice_id, qty, unit, tax = match.groups()
        qty, unit, tax = int(qty), int(unit), int(tax)
        total = qty * unit + tax
        if qty < 1 or total > MAX_CENTS:
            return None
        return {"invoice_id": invoice_id, "currency": "USD", "total_cents": total}
    if task.kind == "classification" and source["text"] in TICKETS:
        return {"label": TICKETS[source["text"]]}
    return None


def plan(task: Task):
    """Executable preflight only; model purchasing requires a future live bridge."""
    output = solve(task)
    return {
        "task_id": task.id, "kind": task.kind, "mode": "LOCAL_PREFLIGHT",
        "decision": "LOCAL_TOOL" if output is not None else "REVIEW_REQUIRED",
        "reason": ("Source matches the bounded tool contract; inference is unnecessary."
                   if output is not None else
                   "Source is outside the bounded tool contract; no validated paid provider is connected for this source."),
        "tool_version": TOOL_VERSION, "output": output,
        "inference_calls": 0, "provider_spend_micro_usd": 0,
        "payments_sent": 0, "live_purchase_authorized": False,
    }
