"""Offline provider evidence screening, separate from per-response check scores."""
import hashlib
import json
import math


def source_key(task):
    return hashlib.sha256(json.dumps({"kind": task.kind, "source": task.source},
                                     sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def wilson_lower(successes, total):
    """Lower endpoint of the two-sided 95% Wilson score interval.

    Diagnostic only: repeated templates do not establish independent deployment
    samples. See https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm
    """
    if type(total) is not int or type(successes) is not int or not 0 <= successes <= total:
        raise ValueError("Invalid success counts")
    if not total:
        return 0.0
    z = 1.959963984540054
    p = successes / total
    return max(0.0, (p + z*z/(2*total) - z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))) / (1 + z*z/total))


def screen(observations, required_success_rate=.95, minimum_unique=20):
    """Collapse exact sources; a source succeeds only if every repetition did.

    Each observation is (source fingerprint, strict correctness bool). Callers
    must supply calibration rows only. Holdout results never enter this gate.
    """
    if type(required_success_rate) not in {int, float} or not 0 < required_success_rate <= 1:
        raise ValueError("Success target must be finite and in (0, 1]")
    if type(minimum_unique) is not int or minimum_unique < 1:
        raise ValueError("Minimum unique samples must be positive")
    groups = {}
    count = 0
    for fingerprint, correct in observations:
        if type(correct) is not bool or not isinstance(fingerprint, str) or not fingerprint:
            raise ValueError("Evidence needs a fingerprint and strict boolean correctness")
        groups[fingerprint] = groups.get(fingerprint, True) and correct
        count += 1
    n, successes = len(groups), sum(groups.values())
    bound = wilson_lower(successes, n)
    eligible = n >= minimum_unique and bound >= required_success_rate
    return {
        "observations": count, "unique_sources": n, "consistently_correct_sources": successes,
        "unique_success_rate": successes / n if n else None,
        "wilson_95_lower": bound, "required_success_rate": required_success_rate,
        "minimum_unique": minimum_unique, "passes_statistical_screen": eligible,
        "status": "PASSES_OFFLINE_SCREEN" if eligible else "INSUFFICIENT_UNIQUE_SOURCES" if n < minimum_unique else "BELOW_QUALITY_TARGET",
        # Narrow fixture evidence cannot authorize live spending, even if a bound passes.
        "live_purchase_authorized": False,
    }
