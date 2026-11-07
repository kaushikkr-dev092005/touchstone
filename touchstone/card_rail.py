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
        with journal.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS card_mandates(scope TEXT PRIMARY KEY, body TEXT NOT NULL)')

    def _bind_mandate(self, scope, body):
        encoded = canonical(body)
        with self.journal.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM card_mandates WHERE scope=?', (scope,)).fetchone()
            if row and row['body'] != encoded:
                raise ValueError('Card scope is bound to a different approved mandate')
            db.execute('INSERT OR IGNORE INTO card_mandates VALUES(?,?)', (scope, encoded))

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
        self._bind_mandate(scope, digest_body)
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
        self._bind_mandate(scope, bound)
        self.journal.observe(scope,'issue',{'id':card_id,'status':result['status']})
        return result

    def pay(self, scope, amount_micro=None, *, adapter=None, job_id=None, execute=False, expected_currency=None):
        """Spend one issued single-use card through an independently verified merchant adapter.

        The card is re-read and its controls re-verified immediately before dispatch. A durable
        request precedes the merchant call; any uncertainty raises OutcomeUnknown and a second
        merchant call is never made automatically. The receipt records merchant acknowledgement and,
        separately, whether independent settlement evidence exists (settlement_verified).
        """
        if adapter is None:
            raise PolicyError('Issuing is not merchant acquiring. Configure an independently verified merchant adapter; no automatic fallback or charge')
        if not execute:
            raise ValueError('A merchant payment requires --execute and separate written approval for this amount')
        issued = self.journal.get(scope, 'issue')
        if not issued or issued['state'] != 'OBSERVED':
            raise PolicyError('No observed issued card for this scope; reconcile issuing first')
        with self.journal.connect() as db:
            stored = db.execute('SELECT body FROM card_mandates WHERE scope=?', (scope,)).fetchone()
        if not stored:
            raise PolicyError('Original card controls are unavailable; reconcile the approved issuing mandate first')
        expected = json.loads(stored['body'])
        account = getattr(self.client, 'account_id', None)
        if (not account or expected.get('account_context_sha256') != hashlib.sha256(account.encode()).hexdigest()
                or hashlib.sha256(canonical(expected).encode()).hexdigest() != issued['digest']):
            raise PolicyError('Card account or immutable issuing mandate differs')
        card_id = json.loads(issued['response'])['id']
        card = self._read_and_validate(card_id, expected)
        controls = card['authorization_controls']
        limits = controls.get('transaction_limits', {})
        currency = (controls.get('allowed_currencies') or [None])[0]
        per_transaction = next((x['amount'] for x in limits.get('limits', []) if x.get('interval') == 'PER_TRANSACTION'), None)
        expiry = datetime.fromisoformat(controls.get('active_to', '1970-01-01T00:00:00+00:00').replace('Z', '+00:00'))
        if (card.get('status') != 'ACTIVE' or controls.get('allowed_transaction_count') != 'SINGLE' or per_transaction is None
                or type(amount_micro) is not int or amount_micro <= 0 or api_usd(amount_micro) > per_transaction
                or expiry <= datetime.now(timezone.utc) or limits.get('currency') != currency or currency is None):
            raise PolicyError('Card is not active, single-use, unexpired and large enough for this exact amount')
        if expected_currency is not None and expected_currency != currency:
            raise PolicyError('Card currency differs from the purchase currency; no conversion is performed')
        job_id = job_id or scope
        body = {'card_id': card_id, 'amount_micro': amount_micro, 'currency': currency, 'job_id': job_id, 'adapter': adapter.name}
        action = 'merchant_charge'
        request_id, prior = self.journal.begin(scope, action, '/merchant/charge', body)
        if prior:
            return {**prior, 'idempotent_replay': True}
        try:
            charge = adapter.charge(job_id=job_id, card_id=card_id, amount_micro=amount_micro, currency=currency)
            settlement = adapter.confirm(charge)
        except Exception:
            self.journal.uncertain(scope, action)
            raise OutcomeUnknown('Merchant outcome is unknown; reconcile with the merchant and never charge again automatically') from None
        result = {'label': getattr(self.client, 'evidence_label', 'MOCK'), 'mode': self.mode, 'scope': scope, 'card_id': card_id,
                  'request_id': request_id, 'amount_micro': amount_micro, 'currency': currency, 'adapter': adapter.name,
                  'merchant_acknowledged': charge['merchant_acknowledged'], 'merchant_receipt': charge,
                  'settlement_verified': bool(settlement), 'settlement_evidence': settlement,
                  'merchant_payment_completed': bool(settlement), 'visa_approved_agent': False,
                  'sensitive_card_details_requested': False}
        self.journal.observe_raw(scope, action, result)
        return result
