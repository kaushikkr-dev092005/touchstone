"""FX-aware comparison is separate from payment dispatch and treasury conversion."""
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import math
import time

PROVIDERS = {'metal-provider', 'local-gpu', 'hosted-premium'}


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('Integer micro-currency amount required')
    return value


def rate_observation(quote, budget_currency='USD', now=None):
    now = time.time() if now is None else now
    sell, buy = quote['sell_currency'], quote['buy_currency']
    provider_currency = buy if sell == budget_currency else sell if buy == budget_currency else None
    pair = quote.get('currency_pair')
    value = Decimal(str(quote['client_rate']))
    if not provider_currency or not value.is_finite() or value <= 0:
        raise ValueError('FX quote has no positive applicable rate')
    if pair == provider_currency + budget_currency:
        rate = Fraction(value)
    elif pair == budget_currency + provider_currency:
        rate = 1/Fraction(value)
    else:
        raise ValueError('Explicit FX pair orientation is required; rounded amounts are not a rate')
    expiry = datetime.fromisoformat(quote['valid_to_at'].replace('Z', '+00:00')).timestamp()
    if expiry <= now:
        raise ValueError('FX quote expired')
    fees = quote.get('application_fees')
    return {'label':'MEASURED', 'source':'AIRWALLEX_SANDBOX_QUOTE', 'quote_id':quote['quote_id'],
            'provider_currency':provider_currency, 'budget_currency':budget_currency,
            'rate_numerator':rate.numerator, 'rate_denominator':rate.denominator,
            'observed_at':now, 'expires_at':expiry,
            'application_fees':fees, 'application_fees_disclosed':isinstance(fees,list),
            'conversion_executed':False, 'metal_funded':False}


def compare(offers, rates, *, budget_currency='USD', budget_micro=1000000,
            maximum_latency_ms=10000, maximum_attempts=1, now=None, allow_simulated=False):
    now = time.time() if now is None else now
    integer(budget_micro,1); integer(maximum_latency_ms,1)
    if type(maximum_attempts) is not int or not 1 <= maximum_attempts <= 3:
        raise ValueError('At most three bounded attempts may be modeled')
    rows=[]
    for offer in offers:
        if offer['provider'] not in PROVIDERS or offer['rail'] not in {'METAL_TESTNET','AIRWALLEX_CARD'}:
            raise ValueError('Unknown provider or rail')
        price=integer(offer['price_micro'],1)
        currency=offer['currency']
        if offer['rail']=='METAL_TESTNET' and currency!='USDZ':
            raise ValueError('Metal quotes remain USDZ; fiat FX cannot normalize or fund them')
        row={'provider':offer['provider'],'currency':currency,'rail':offer['rail'],
             'price_micro':price,'label':offer['label'],'eligible':False,'reason':None}
        if currency=='USDZ':
            row['reason']='SEPARATE_TOKEN_ACCOUNT_NO_FIAT_BRIDGE'; rows.append(row); continue
        rate=None
        if currency!=budget_currency:
            rate=next((r for r in rates if r['provider_currency']==currency and r['budget_currency']==budget_currency),None)
            if not rate or rate['expires_at']<=now:
                row['reason']='FX_QUOTE_MISSING_OR_EXPIRED';rows.append(row);continue
            factor=Fraction(integer(rate['rate_numerator'],1),integer(rate['rate_denominator'],1))
        else: factor=Fraction(1)
        converted=math.ceil(price*factor)
        fx_fee=integer(offer['fx_fee_budget_micro'])
        rail_fee=integer(offer['rail_fee_budget_micro'])
        check_fee=integer(offer.get('check_fee_budget_micro',0))
        quality=Fraction(str(offer['quality_lower_bound']))
        if not 0<=quality<=1:
            raise ValueError('Quality lower bound must be a probability')
        retry=sum((1-quality)**n for n in range(1,maximum_attempts))
        subtotal=converted+fx_fee+rail_fee+check_fee
        expected_retry=math.ceil(subtotal*retry)
        total=subtotal+expected_retry
        executable_label=offer['label']=='MEASURED' and (not rate or rate['label']=='MEASURED')
        row.update(converted_cost_micro=converted,fx_fee_micro=fx_fee,rail_fee_micro=rail_fee,
                   check_fee_micro=check_fee,expected_retry_micro=expected_retry,effective_cost_micro=total,
                   quote_id=rate['quote_id'] if rate else None,
                   cost_label='MEASURED_QUOTE_WITH_EXPLICIT_COST_ASSUMPTIONS' if executable_label else 'SIMULATED',
                   latency_ms=integer(offer['latency_ms']))
        if quality<Fraction(95,100) or offer.get('qualification_current') is not True:
            row['reason']='QUALITY_GATE_NOT_PASSED'
        elif row['latency_ms']>maximum_latency_ms:row['reason']='LATENCY_LIMIT'
        elif total>budget_micro:row['reason']='BUDGET_LIMIT'
        elif rate and rate.get('application_fees_disclosed') is not True:row['reason']='FX_FEES_NOT_DISCLOSED'
        elif not offer.get('fees_bounded'):row['reason']='UNBOUNDED_FEES'
        elif not offer.get('funded_fiat_account'):row['reason']='FIAT_PROVIDER_NOT_FUNDED'
        elif not executable_label and not allow_simulated:row['reason']='SIMULATED_OFFER_CANNOT_AUTHORIZE_SPEND'
        else:row.update(eligible=True,reason='ELIGIBLE_FOR_COMPARISON')
        rows.append(row)
    eligible=[r for r in rows if r['eligible']]
    chosen=min(eligible,key=lambda r:(r['effective_cost_micro'],r['latency_ms'],r['provider'])) if eligible else None
    return {'label':'SIMULATED' if allow_simulated else 'MEASURED', 'budget_currency':budget_currency,
            'offers':rows,'preferred_provider':chosen['provider'] if chosen else None,
            'decision':'COMPARISON_ONLY' if chosen else 'REVIEW_NO_ELIGIBLE_PROVIDER',
            'dispatch_authorized':False,'conversions_created':0,'payments_sent':0,
            'retry_assumption':'Independent fixed-price attempts, truncated to the explicit maximum; not a measured guarantee',
            'fx_fee_assumption':'Explicit allocated treasury fee per call; no per-call conversion is performed'}


def rebalance_plan(*, deficit_micro, threshold_micro, planned_sell_usd_micro, quote_expires_at, now=None):
    now=time.time() if now is None else now
    integer(deficit_micro);integer(threshold_micro,1);integer(planned_sell_usd_micro)
    ready=deficit_micro>=threshold_micro and planned_sell_usd_micro>=1000000 and quote_expires_at>now
    return {'label':'BLOCKED','threshold_met':ready,'minimum_usd_equivalent_micro':1000000,
            'requires_execute':True,'requires_fresh_written_cap':True,'conversion_executed':False,
            'next_action':'Use the existing guarded airwallex-fx workflow after new approval' if ready else 'Do not rebalance'}
