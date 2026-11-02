"""Online checks receive only source evidence and untrusted provider data."""
import re
from .local_tools import solve
from .workload import Task

VERIFY_COST = 1000  # millionths of a demo USD; explicit internal checking charge
VERIFIER_VERSION = "source-rules-v4-source-gating"

# Deliberately bounded source rules, not a general-purpose semantic classifier.
CLASS_EVIDENCE = {
    "billing": (r"\bcharged twice\b", r"\bduplicate charge\b", r"\bincorrect invoice amount\b", r"\brefund (?:has not arrived|is missing)\b"),
    "technical": (r"\b(?:app|application) crashes\b", r"\b(?:cannot|can't|unable to) (?:log|sign) in\b", r"\bserver error\b"),
    "shipping": (r"\bparcel has not arrived\b", r"\btracking is delayed\b", r"\bdelivery is late\b", r"\bpackage is missing\b"),
}


def classification_evidence(text):
    if not isinstance(text, str):
        return {}
    # Negation, quotation and adversarial instruction contexts require human/reference review.
    if re.search(r"\b(?:not|never|no longer)\s+(?:being\s+)?(?:charged|a duplicate|a server|crash)"
                 r"|n['’]t\s+(?:been\s+|being\s+)?(?:charged|a duplicate|a server|crash)"
                 r"|\b(?:ignore|pretend|classify this as)\b|[\"“”]", text, re.I):
        return {}
    return {label: [m.group() for pattern in patterns for m in re.finditer(pattern, text, re.I)]
            for label, patterns in CLASS_EVIDENCE.items()
            if any(re.search(pattern, text, re.I) for pattern in patterns)}


def source_rejected(reason="Source is outside the supported contract; no provider can satisfy it. Human review required"):
    """A defect in the source cannot be fixed by paying another provider."""
    return {"score": 0.0, "passed": False, "retryable": False, "decision": "review",
            "method": VERIFIER_VERSION, "reason": reason}


def source_supported(task: Task):
    """Pre-purchase gate: (supported, reason). Uses only the public task source."""
    if task.kind in {"invoice", "arithmetic"}:
        return (solve(task) is not None,
                "Source is outside the bounded invoice/arithmetic contract; review before any purchase")
    if task.kind == "classification":
        text = task.source.get("text") if isinstance(task.source, dict) else None
        return (len(classification_evidence(text)) == 1,
                "Ticket text has no single supported evidence label; review before any purchase")
    if task.kind == "invoice_consistency":
        from .invoice_consistency import source_supported as consistency_supported
        return (consistency_supported(task),
                "Invoice text lacks parseable ITEM rows and exactly one stated total; review before any purchase")
    return False, f"Unsupported task type {task.kind!r}; review before any purchase"


def check(task: Task, output):
    if type(task.min_quality) not in {int, float} or not 0 <= task.min_quality <= 1:
        return {"score": 0.0, "passed": False, "retryable": False, "reason": "Invalid quality threshold"}
    if not isinstance(output, dict):
        return {"score": 0.0, "passed": False, "reason": "Response is not a JSON object"}
    try:
        if task.kind == "invoice_consistency":
            from .invoice_consistency import check_invoice_consistency
            return check_invoice_consistency(task, output)
        if task.kind in {"invoice", "arithmetic"}:
            # Same strict contract as the offline tool: a loose regex here would accept
            # (and bill for) sources the tool abstains on, e.g. a non-USD invoice.
            expected = solve(task)
            if expected is None:
                return source_rejected()
        elif task.kind == "classification":
            valid = set(output) == {"label"} and output["label"] in {"billing", "technical", "shipping"}
            if not valid:
                return {"score": 0.0, "passed": False, "reason": "Invalid label schema"}
            evidence = classification_evidence(task.source.get("text"))
            if len(evidence) != 1:
                return {"score": 0.0, "passed": False, "retryable": False, "decision": "review",
                        "method": VERIFIER_VERSION, "reason": "Ambiguous or unsupported source evidence; human/reference review required"}
            expected = next(iter(evidence))
            passed = output["label"] == expected
            return {"score": float(passed), "passed": passed, "retryable": True,
                    "method": VERIFIER_VERSION, "evidence": evidence[expected],
                    "reason": "Label agrees with supported source evidence" if passed else "Label contradicts source evidence"}
        else:
            return source_rejected("Unsupported task type; no provider can satisfy it")
        passed = (set(output) == set(expected) and output == expected
                  and ("total_cents" not in output or type(output["total_cents"]) is int))
        return {"score": float(passed), "passed": passed,
                "reason": "Source evidence and numeric checks passed" if passed else "Source evidence or numeric checks failed"}
    except (KeyError, TypeError, ValueError, AttributeError):
        return {"score": 0.0, "passed": False, "reason": "Malformed source or response"}
