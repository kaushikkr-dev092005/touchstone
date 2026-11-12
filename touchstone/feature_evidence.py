"""Public saved evidence for the four extensions. No payment dispatcher."""
import json
import hashlib
import os
from pathlib import Path
import threading
import time

from .config import ROOT
from .fx_router import compare, rate_observation

_fx_lock=threading.Lock()
_issuing_lock=threading.Lock()


def load(path):
    try:
        if path.stat().st_size>250000:raise ValueError('Evidence too large')
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


def completion_summary():
    latest=load(ROOT/'bench/results/m4-live-20261112/completion-status.json')
    if latest.get('label')=='MEASURED' and latest.get('comparison',{}).get('actual_paid_receipts',0)>=30:
        return latest
    return load(ROOT/'bench/results/completion-20261110/final-proof-status.json')


def preview(rate, now=None):
    offers=[{'provider':'local-gpu','rail':'AIRWALLEX_CARD','price_micro':10000,'currency':'USD'},
            {'provider':'hosted-premium','rail':'AIRWALLEX_CARD','price_micro':7000,'currency':'EUR'}]
    for offer in offers:
        offer.update(label='SIMULATED',fx_fee_budget_micro=0,rail_fee_budget_micro=0,
                     quality_lower_bound='0.98',latency_ms=100,qualification_current=False,
                     fees_bounded=False,funded_fiat_account=False)
    result=compare(offers,[rate] if rate else [],now=now)
    result.update(label='SIMULATED',rates_label=rate.get('label','BLOCKED') if rate else 'BLOCKED',
                  price_source='ILLUSTRATIVE_FIAT_PRICES_NOT_CURRENT_PROVIDER_QUOTES',
                  note='Actual local models are unqualified; fiat merchant funding and fees are unverified. No dispatch.')
    return result


def refresh_fx(client):
    with _fx_lock:
        path=ROOT/'bench/results/features/fx-quote.json'
        previous=load(path)
        now=time.time()
        account=hashlib.sha256(str(getattr(client,'account_id','')).encode()).hexdigest()
        if previous.get('account_fingerprint')==account and previous.get('rate',{}).get('expires_at',0)>now+10 and now-previous.get('observed_at',0)<45:
            return previous
        raw=client.create_fx_quote('USD','EUR','1.00',validity='MIN_1')
        rate=rate_observation(raw,now=now)
        safe={key:raw.get(key) for key in ('quote_id','sell_currency','buy_currency','sell_amount','buy_amount',
              'client_rate','currency_pair','valid_to_at','application_fees')}
        result={'label':'MEASURED','observed_at':now,'account_fingerprint':account,'operation':'NON_SETTLING_FX_QUOTE',
                'quote':safe,'rate':rate,'preview':preview(rate,now),'conversions_created':0,'payments_sent':0,
                'note':'The 1 USD reference quote creates no conversion. Provider prices are illustrative, not funded fiat offers.'}
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.pending');temporary.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');temporary.replace(path)
        return result


def refresh_issuing(client):
    """Refresh only access diagnostics; never issues or charges a card."""
    from .card_rail import CardRail
    from .holds import OperationJournal
    with _issuing_lock:
        result=CardRail(client,OperationJournal(ROOT/'data/issuing.sqlite')).doctor(diagnose=True)
        result.update(observed_at=time.time(),operation='READ_ONLY_ISSUING_DIAGNOSIS',
            account_fingerprint=hashlib.sha256(str(getattr(client,'account_id','')).encode()).hexdigest())
        path=ROOT/'data/issuing-readiness.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.pending')
        temporary.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');temporary.replace(path)
        return result


def capacity_summary(now=None):
    """Saved throughput calibration, re-verified on every read. A stale or altered file is reported, not trusted."""
    from .throughput import verify
    now = time.time() if now is None else now
    saved = load(ROOT/'bench/results/features/capacity-calibration.json')
    try:
        body = saved['body']
        verify(saved, body['model_sha256'], now)
        state = 'MEASURED'
    except (KeyError, TypeError, ValueError) as error:
        if not saved:
            return {'label': 'BLOCKED', 'reason': 'No throughput calibration has been measured', 'markup_enabled': False}
        return {'label': 'BLOCKED', 'reason': str(error)[:120], 'markup_enabled': False}
    return {'label': state, 'markup_enabled': True, 'model': body['model'], 'samples': body['samples'],
            'baseline_tps': body['baseline_tps'], 'baseline_tps_interval_90': body['baseline_tps_interval_90'],
            'max_multiplier': body['max_multiplier'], 'minimum_live_samples': body['minimum_live_samples'],
            'valid_until': body['valid_until'], 'pricing_rule': body['pricing_rule'],
            'temperature_changes_price': False, 'digest': saved['digest']}


def summary():
    folder=ROOT/'bench/results/features'
    current_fault=ROOT/'bench/results/faults/current-paid-fault-20261110.json'
    fault=load(current_fault) if current_fault.exists() else load(ROOT/'bench/results/faults/metal-fault.json')
    fault_summary={'label':'BLOCKED','reason':'No valid saved fault proof'}
    if fault:
        try:
            from .fault_proof import validate
            validate(fault)
            body=fault['body'];obs=fault.get('cryptographic_observation',{})
            saved_ack=load(ROOT/'bench/results/completion-20261110/current-seller-fault-acknowledgement.json') if current_fault.exists() else {}
            ack=saved_ack.get('acknowledgement');ack_verified=False
            if ack and saved_ack.get('root')==fault['commitment']['root']:
                from .fault_pipeline import node_ack_verifier
                try:
                    ack_verified=node_ack_verifier(ack,body['requirements']['payTo'],fault['commitment']['root'],body['payment']['invoice']['id'])
                except (RuntimeError,OSError,ValueError):pass # Pure-Python no-key demo needs no Node installation.
                obs=saved_ack.get('independent_receipt_check',obs)
            fault_summary={'label':'MEASURED','scope':'SAVED_HISTORICAL_EVIDENCE',
                'root':fault['commitment']['root'],'counterexample':body['counterexample'],
                'buyer_signature_on_file':bool(fault.get('fault_signature')),
                'recorded_operator_signature_check':obs.get('operator_signature_verified',False),
                'provider_output_attribution':obs.get('provider_output_attribution','UNVERIFIED'),
                'refund_executed':False,'credit_issued':False,'receipt_status':'preconfirmed',
                'seller_ack_signature_verified':bool(ack_verified),
                'seller_ack_decision':ack.get('decision') if ack_verified else None,
                'seller_credit_status':ack.get('credit_status') if ack_verified else 'UNVERIFIED',
                'final_settlement_verified':False}
        except (ValueError,KeyError,TypeError):pass
    fx=load(folder/'fx-quote.json')
    rate=fx.get('rate')
    card=load(folder/'card-readiness.json') or {'label':'BLOCKED','issuing_read':False}
    account=os.environ.get('AIRWALLEX_ACCOUNT_ID')
    if account:
        observed=load(ROOT/'data/issuing-readiness.json')
        if observed.get('account_fingerprint')==hashlib.sha256(account.encode()).hexdigest():
            card=observed
    if card.get('label')=='MEASURED' and (not account or
            card.get('account_fingerprint')!=hashlib.sha256(account.encode()).hexdigest()):
        card={'label':'BLOCKED','issuing_read':False,'historical_issuing_read':bool(card.get('issuing_read')),
            'reason':'Saved issuing evidence is not bound to the configured account. Recheck access.',
            'cards_created':0,'transactions_sent':0}
    issued=load(ROOT/'bench/results/completion-20261110/issuing-proof.json')
    approved=load(ROOT/'bench/results/completion-20261110/issuing-plan.json')
    if issued.get('label')=='MEASURED' and issued.get('card_controls_verified') is True and approved.get('approved') is True:
        from .ledger import canonical
        plan=approved.get('plan',{})
        digest=hashlib.sha256(canonical(plan).encode()).hexdigest()
        if digest==approved.get('plan_sha256')==issued.get('original_plan_sha256'):
            saved_card=issued.get('card',{})
            card={**card,'saved_creation':{'label':'MEASURED','scope':'SAVED_SANDBOX_ISSUING',
                'controls_verified':True,'card_status_at_readback':saved_card.get('status'),
                'authorization_controls':saved_card.get('authorization_controls',{}),
                'current_account_matches':bool(account and plan.get('account_fingerprint')==hashlib.sha256(account.encode()).hexdigest()),
                'merchant_payment_completed':False,'visa_approved_agent':False}}
    return {'completion':completion_summary(),
            'fault':fault_summary,'fx':{'label':'MEASURED' if rate else 'BLOCKED','rate':rate,
             'quote_current':bool(rate and rate.get('expires_at',0)>time.time()),'preview':preview(rate)},
            'card':card,
            'tap':load(folder/'tap-probe.json') or {'label':'BLOCKED','visa_approved_agent':False},
            'capacity':capacity_summary(),
            'automatic_payments':False,'fiat_token_bridge':False}
