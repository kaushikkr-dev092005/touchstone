"""Provider-reported tokens × published API prices, separate from USDZ and billing reconciliation."""

SOURCE='https://platform.claude.com/docs/en/about-claude/pricing'
CHECKED_DATE='2026-11-10'


def estimate_usage(model,usage):
    fields=('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')
    if model!='claude-haiku-5-5':
        return {'status':'UNMEASURED_MODEL_PRICE','estimated_credit_micro_usd':None,'billing_reconciled':False}
    counts={name:0 if usage.get(name) is None else usage[name] for name in fields}
    if any(type(value) is not int or value<0 for value in counts.values()):raise ValueError('Invalid API token counts')
    long_prompt=sum(counts[name] for name in fields if name!='output_tokens')>100000
    # Micro-USD per million tokens: standard input/output, 5m cache creation, cache read.
    rates=(500000,2500000,625000,50000) if long_prompt else (100000,500000,125000,10000)
    cost=(sum(counts[name]*rate for name,rate in zip(fields,rates))+999999)//1000000
    return {'status':'PROVIDER_USAGE_AT_PUBLISHED_PRICES','estimated_credit_micro_usd':cost,
        'billing_reconciled':False,'price_reference':SOURCE,'price_checked_date':CHECKED_DATE,
        'long_prompt_pricing':long_prompt,'additional_hosted_cash_spend_measured':False}
