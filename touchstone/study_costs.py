"""Conservative study credit accounting from reported usage, separate from USDZ."""
from .hosted_cost import estimate_usage

RESERVATIONS={'claude-haiku-5-5':11200,'claude-sonnet-5-5':224000}


def published_cost(metadata):
    metadata=metadata or {};model=metadata.get('provider_model');usage=metadata.get('usage')
    if model not in RESERVATIONS or not isinstance(usage,dict):return None
    fields=('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')
    counts=[0 if usage.get(k) is None else usage[k] for k in fields]
    if (any(type(v) is not int or v<0 for v in counts) or not counts[0] or not counts[1]):return None
    if model=='claude-haiku-5-5':return estimate_usage(model,usage)
    cost=(sum(v*rate for v,rate in zip(counts,(2000000,10000000,2500000,100000)))+999999)//1000000
    return {'status':'PROVIDER_USAGE_AT_PUBLISHED_PRICES','estimated_credit_micro_usd':cost,
        'billing_reconciled':False,'price_reference':'https://platform.claude.com/docs/en/about-claude/pricing',
        'price_checked_date':'2026-11-10'}
