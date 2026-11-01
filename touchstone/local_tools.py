"""Small, explicitly bounded tools. No models, payments, or benchmark truth."""
import re

from .workload import Task

TOOL_VERSION = "bounded-tools-v2"
MAX_CENTS = 10**12
INVOICE = re.compile(
    r"Invoice (INV-[A-Za-z0-9-]{1,64})\. Currency USD\. Quantity ([0-9]{1,6})\. "
    r"Unit price ([0-9]{1,12}) cents\. Tax ([0-9]{1,12}) cents\."
)
USD_MONEY = re.compile(r"(?:USD\s*|\$\s*)?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.([0-9]{2})")
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
    if task.kind == "invoice_exception":
        return _solve_invoice_exception(source)
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


def _citation(text, value):
    if type(value) is not dict or set(value) != {"value", "start", "end"}:
        return None
    cited_value, start, end = value["value"], value["start"], value["end"]
    if (type(cited_value) is not str or type(start) is not int or type(end) is not int
            or start < 0 or end <= start or end > len(text) or text[start:end] != cited_value):
        return None
    return cited_value


def _usd_cents(value):
    if type(value) is not str or len(value) > 32:
        return None
    match = USD_MONEY.fullmatch(value.strip())
    if not match:
        return None
    whole, fraction = match.groups()
    cents = int(whole.replace(",", "")) * 100 + int(fraction)
    return cents if cents <= MAX_CENTS else None


def _identifier(value):
    return (type(value) is str and 1 <= len(value) <= 256 and value == value.strip()
            and not any(ord(character) < 32 for character in value))


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= MAX_CENTS


def _solve_invoice_exception(source):
    if type(source) is not dict or set(source) != {"invoice", "purchase_order", "payments"}:
        return None
    invoice, purchase_order, payments = source["invoice"], source["purchase_order"], source["payments"]
    if (type(invoice) is not dict or set(invoice) != {"text", "fields", "items"}
            or type(invoice["text"]) is not str or not 1 <= len(invoice["text"]) <= 1_000_000
            or type(invoice["fields"]) is not dict
            or set(invoice["fields"]) != {"invoice_id", "supplier_name", "purchase_order_id", "currency",
                                         "subtotal_cents", "tax_cents", "total_cents"}
            or type(invoice["items"]) is not list or not 1 <= len(invoice["items"]) <= 1000):
        return None

    text = invoice["text"]
    field_citations = invoice["fields"]
    values = {}
    for field in ("invoice_id", "supplier_name", "purchase_order_id", "currency"):
        value = _citation(text, field_citations[field])
        if value is None or not _identifier(value):
            return None
        values[field] = value
    if values["currency"] != "USD":
        return None
    for field in ("subtotal_cents", "tax_cents", "total_cents"):
        value = _citation(text, field_citations[field])
        cents = _usd_cents(value) if value is not None else None
        if cents is None:
            return None
        values[field] = cents

    line_totals = []
    for item in invoice["items"]:
        if type(item) is not dict or set(item) != {"quantity", "unit_price_cents", "line_total_cents"}:
            return None
        quantity_text = _citation(text, item["quantity"])
        unit_text = _citation(text, item["unit_price_cents"])
        total_text = _citation(text, item["line_total_cents"])
        if (quantity_text is None or not re.fullmatch(r"[1-9][0-9]{0,5}", quantity_text)
                or unit_text is None or total_text is None):
            return None
        quantity, unit_cents = int(quantity_text), _usd_cents(unit_text)
        line_cents = _usd_cents(total_text)
        if (unit_cents is None or line_cents is None
                or quantity * unit_cents > MAX_CENTS):
            return None
        line_totals.append((quantity * unit_cents, line_cents))

    if (type(purchase_order) is not dict
            or set(purchase_order) != {"purchase_order_id", "supplier_name", "currency", "authorized_cents"}
            or not _identifier(purchase_order["purchase_order_id"])
            or not _identifier(purchase_order["supplier_name"])
            or purchase_order["currency"] != "USD"
            or not _integer(purchase_order["authorized_cents"], 1)):
        return None
    if type(payments) is not list or len(payments) > 1000:
        return None

    active_payments = 0
    issues = []
    for payment in payments:
        if (type(payment) is not dict
                or set(payment) != {"payment_id", "invoice_id", "purchase_order_id", "supplier_name",
                                    "currency", "amount_cents", "status"}
                or any(not _identifier(payment[field]) for field in
                       ("payment_id", "invoice_id", "purchase_order_id", "supplier_name"))
                or payment["currency"] != "USD"
                or not _integer(payment["amount_cents"], 1)
                or type(payment["status"]) is not str
                or payment["status"] not in {"in_progress", "settled", "failed"}):
            return None
        if payment["purchase_order_id"] == purchase_order["purchase_order_id"]:
            if payment["supplier_name"].casefold() != purchase_order["supplier_name"].casefold():
                issues.append("PO_PAYMENT_SUPPLIER_MISMATCH")
            if payment["status"] in {"in_progress", "settled"}:
                active_payments += payment["amount_cents"]
        if (payment["invoice_id"] == values["invoice_id"]
                and payment["status"] in {"in_progress", "settled"}):
            issues.append("DUPLICATE_OR_IN_PROGRESS_PAYMENT")

    line_subtotal = sum(expected for expected, _ in line_totals)
    if line_subtotal > MAX_CENTS or values["subtotal_cents"] + values["tax_cents"] > MAX_CENTS:
        return None
    if any(expected != cited for expected, cited in line_totals):
        issues.append("LINE_TOTAL_MISMATCH")
    if line_subtotal != values["subtotal_cents"]:
        issues.append("SUBTOTAL_MISMATCH")
    if values["subtotal_cents"] + values["tax_cents"] != values["total_cents"]:
        issues.append("INVOICE_TOTAL_MISMATCH")
    if values["purchase_order_id"] != purchase_order["purchase_order_id"]:
        issues.append("PURCHASE_ORDER_MISMATCH")
    if values["supplier_name"].casefold() != purchase_order["supplier_name"].casefold():
        issues.append("SUPPLIER_MISMATCH")
    remaining = max(0, purchase_order["authorized_cents"] - active_payments)
    if active_payments > purchase_order["authorized_cents"] or values["total_cents"] > remaining:
        issues.append("PURCHASE_ORDER_LIMIT_EXCEEDED")

    unique_issues = list(dict.fromkeys(issues))
    evidence_spans = {
        "fields": {field: [citation["start"], citation["end"]]
                   for field, citation in field_citations.items()},
        "items": [{field: [citation["start"], citation["end"]] for field, citation in item.items()}
                  for item in invoice["items"]],
    }
    return {
        "finding": "EXCEPTION_REQUIRES_HUMAN_REVIEW" if unique_issues else "MATCHED_REQUIRES_HUMAN_APPROVAL",
        "issues": unique_issues,
        "invoice_id": values["invoice_id"],
        "purchase_order_id": purchase_order["purchase_order_id"],
        "invoice_total_cents": values["total_cents"],
        "purchase_order_remaining_cents": remaining,
        "evidence_spans": evidence_spans,
        "payments_sent": 0,
        "live_purchase_authorized": False,
    }


def plan(task: Task):
    """Executable preflight only; model purchasing requires a future live bridge."""
    output = solve(task)
    if task.kind == "invoice_exception" and output is not None:
        decision = "REVIEW_REQUIRED"
        reason = "Deterministic invoice, purchase-order and payment checks completed; human review is still required and no payment was initiated."
    else:
        decision = "LOCAL_TOOL" if output is not None else "REVIEW_REQUIRED"
        reason = ("Source matches the bounded tool contract; inference is unnecessary."
                  if output is not None else
                  "Source is outside the bounded tool contract; no validated paid provider is connected for this source.")
    return {
        "task_id": task.id, "kind": task.kind, "mode": "LOCAL_PREFLIGHT",
        "decision": decision,
        "reason": reason,
        "tool_version": TOOL_VERSION, "output": output,
        "inference_calls": 0, "provider_spend_micro_usd": 0,
        "payments_sent": 0, "live_purchase_authorized": False,
    }
