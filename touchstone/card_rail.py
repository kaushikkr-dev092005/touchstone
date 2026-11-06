"""Sandbox issuing is a separate rail; issuing a card is not a merchant payment."""
import hashlib
import json
from datetime import datetime, timezone
import re

from .holds import OperationJournal, OutcomeUnknown, api_usd
from .ledger import PolicyError, canonical
from .treasury import AirwallexHTTPError


class CardRail:
    mode = 'AIRWALLEX_SANDBOX_CARD'

    def __init__(self, client, journal: OperationJournal):
        self.client, self.journal = client, journal

    def doctor(self):
        try:
            result=self.client.request('GET','/api/v1/issuing/cards?page_size=10')
            readable=isinstance(result,dict) and isinstance(result.get('items'),list)
            return {'label':getattr(self.client,'evidence_label','MOCK') if readable else 'BLOCKED','issuing_read':readable,
                    'issuing_write_verified':False,'merchant_payment_supported':False,
                    'cards_created':0,'transactions_sent':0,'visa_tap_identity':'NOT_VERIFIED'}
        except AirwallexHTTPError as error:
            return {'label':'BLOCKED','issuing_read':False,'http_status':error.status,
                    'reason':'Issuing access/scope not enabled or unavailable','cards_created':0,'transactions_sent':0}

    @staticmethod
    def body(scope, cardholder_id, created_by, cap_micro, currency, expires_at, *, read_only=False):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',scope) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',cardholder_id):
            raise ValueError('Valid issuing scope and existing cardholder ID required')
        if not isinstance(created_by,str) or not created_by.strip() or len(created_by)>100:
            raise ValueError('Issuer requires the requesting user name')
        if type(cap_micro) is not int or not 0<cap_micro<=1000000 or currency not in {'USD','EUR','SGD'}:
            raise ValueError('Sandbox card cap must be positive, at most one currency unit and whole cents')
        amount=api_usd(cap_micro)
        expiry=datetime.fromisoformat(expires_at.replace('Z','+00:00'))
        if expiry.tzinfo is None or (not read_only and not 0<(expiry-datetime.now(timezone.utc)).total_seconds()<=3600):
            raise ValueError('Card controls must expire within one hour')
        return {'cardholder_id':cardholder_id,'created_by':created_by,'form_factor':'VIRTUAL',
                'is_personalized':True,'program':{'purpose':'COMMERCIAL'},'client_data':scope,
                'authorization_controls':{'allowed_transaction_count':'SINGLE','allowed_currencies':[currency],
                    'active_to':expires_at,'blocked_transaction_usages':[{'transaction_scope':'CASH_WITHDRAWAL','usage_scope':'ALL'}],
                    'transaction_limits':{'currency':currency,'limits':[{'interval':'PER_TRANSACTION','amount':amount},
                                                                        {'interval':'ALL_TIME','amount':amount}]}}}

    def issue(self, scope, cardholder_id, created_by, cap_micro, currency, expires_at, *, execute=False):
        if not execute:
            raise ValueError('Issuing requires --execute and separate written approval with a stated card cap')
        body=self.body(scope,cardholder_id,created_by,cap_micro,currency,expires_at)
        account=getattr(self.client,'account_id',None)
        if not account:raise ValueError('An explicit sandbox account context is required')
        digest_body={**body,'account_context_sha256':hashlib.sha256(account.encode()).hexdigest()}
        request_id,prior=self.journal.begin(scope,'issue','/api/v1/issuing/cards/create',digest_body)
        if prior:
            return self._read_and_validate(prior['id'],body)
        try:
            raw=self.client.request('POST','/api/v1/issuing/cards/create',{**body,'request_id':request_id})
            if not isinstance(raw,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',raw.get('id','')):
                raise ValueError('Issuing response has no safe object ID')
            self.journal.observe(scope,'issue',{'id':raw['id'],'status':raw.get('status')})
            return self._read_and_validate(raw['id'],body)
        except Exception:
            self.journal.uncertain(scope,'issue')
            raise OutcomeUnknown('Card creation outcome needs read-only reconciliation; never create another card') from None

    def _read_and_validate(self, card_id, expected):
        raw=self.client.request('GET','/api/v1/issuing/cards/'+card_id)
        actual=raw.get('authorization_controls',{})
        controls=expected['authorization_controls']
        if (raw.get('id')!=card_id or raw.get('form_factor')!='VIRTUAL' or raw.get('client_data')!=expected['client_data']
                or actual.get('allowed_transaction_count')!='SINGLE' or actual.get('transaction_limits')!=controls['transaction_limits']
                or actual.get('allowed_currencies')!=controls['allowed_currencies']
                or raw.get('cardholder_id')!=expected['cardholder_id']
                or actual.get('blocked_transaction_usages')!=controls['blocked_transaction_usages']
                or datetime.fromisoformat(actual.get('active_to','').replace('Z','+00:00'))!=datetime.fromisoformat(controls['active_to'].replace('Z','+00:00'))):
            raise ValueError('Issued card controls do not match the immutable approved cap, currency or expiry')
        return {'label':getattr(self.client,'evidence_label','MOCK'),'mode':self.mode,'card_id':card_id,
                'status':raw.get('status'),'controls_verified':True,'sensitive_card_details_requested':False,
                'authorization_controls':controls,'merchant_payment_completed':False,'visa_approved_agent':False}

    def reconcile(self, scope, cardholder_id, created_by, cap_micro, currency, expires_at):
        expected=self.body(scope,cardholder_id,created_by,cap_micro,currency,expires_at,read_only=True)
        row=self.journal.get(scope,'issue')
        if not row:raise ValueError('No original issuing operation to reconcile')
        bound={**expected,'account_context_sha256':hashlib.sha256(self.client.account_id.encode()).hexdigest()}
        if row['digest']!=hashlib.sha256(canonical(bound).encode()).hexdigest():
            raise ValueError('Reconciliation terms differ from the original issuing mandate')
        prior=json.loads(row['response']) if row['response'] else {}
        card_id=prior.get('id')
        if not card_id:
            found=[]
            for page in range(10):
                result=self.client.request('GET',f'/api/v1/issuing/cards?page_size=100&page_num={page}')
                if not isinstance(result,dict) or not isinstance(result.get('items'),list):raise ValueError('Incomplete issuing read-back')
                found.extend(item for item in result['items'] if item.get('client_data')==scope and item.get('cardholder_id')==cardholder_id)
                if not result.get('has_more'):break
            else:raise OutcomeUnknown('Issuing read-back exceeds the bounded page limit')
            if len(found)!=1:raise OutcomeUnknown('No unique issued card found; retain the original request and do not recreate')
            card_id=found[0]['id']
        result=self._read_and_validate(card_id,expected)
        self.journal.observe(scope,'issue',{'id':card_id,'status':result['status']})
        return result

    def pay(self, *args, **kwargs):
        raise PolicyError('Issuing is not merchant acquiring. Configure an independently verified merchant adapter; no automatic fallback or charge')
