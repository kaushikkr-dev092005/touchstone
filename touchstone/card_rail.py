"""Sandbox issuing is a separate rail; issuing a card is not a merchant payment."""
import hashlib
import json
from datetime import datetime, timezone
import re
from urllib.parse import urlencode

from .holds import OperationJournal, OutcomeUnknown, api_usd
from .ledger import PolicyError, canonical
from .treasury import AirwallexHTTPError


class CardRail:
    mode = 'AIRWALLEX_SANDBOX_CARD'
    api_version = '2024-03-31'

    def __init__(self, client, journal: OperationJournal):
        self.client, self.journal = client, journal
        with journal.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS card_mandates(scope TEXT PRIMARY KEY, body TEXT NOT NULL)')

    def _request(self, method, path, body=None):
        return self.client.request(method, path, body, api_version=self.api_version)

    def _bind_mandate(self, scope, body):
        encoded = canonical(body)
        with self.journal.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body FROM card_mandates WHERE scope=?', (scope,)).fetchone()
            if row and row['body'] != encoded:
                raise ValueError('Card scope is bound to a different approved mandate')
            db.execute('INSERT OR IGNORE INTO card_mandates VALUES(?,?)', (scope, encoded))

    def doctor(self, diagnose=False):
        result={'label':'BLOCKED','issuing_read':False,'issuing_write_verified':False,
            'merchant_payment_supported':False,'cards_created':0,'transactions_sent':0,
            'visa_tap_identity':'NOT_VERIFIED'}
        try:
            raw=self._request('GET','/api/v1/issuing/cards?page_size=10')
            readable=isinstance(raw,dict) and isinstance(raw.get('items'),list)
            result.update(label=getattr(self.client,'evidence_label','MOCK') if readable else 'BLOCKED',issuing_read=readable)
            if readable:
                result['cards_sample']={'count':len(raw['items']),
                    'has_more':raw.get('has_more') if type(raw.get('has_more')) is bool else None,
                    'scope':'FIRST_PAGE_ONLY'}
        except AirwallexHTTPError as error:
            result.update(http_status=error.status,code=error.code,reason='Issuing access/scope not enabled or unavailable')
        if not diagnose:return result
        probes={}
        for name,path in [('balances','/api/v1/balances/current'),
            ('cardholders','/api/v1/issuing/cardholders?page_size=10'),('issuing_config','/api/v1/issuing/config')]:
            try:
                raw=self._request('GET',path) if '/issuing/' in path else self.client.request('GET',path)
                valid=(isinstance(raw,list) if name=='balances' else
                    isinstance(raw,dict) and (name=='issuing_config' or isinstance(raw.get('items'),list)))
                probes[name]={'allowed':valid,'status':'PASS' if valid else 'INVALID_RESPONSE'}
                if valid and name=='cardholders':
                    probes[name]['sample']={'count':len(raw['items']),
                        'has_more':raw.get('has_more') if type(raw.get('has_more')) is bool else None,
                        'ready_individual_count':sum(isinstance(item,dict) and item.get('status')=='READY'
                            and item.get('type')=='INDIVIDUAL' for item in raw['items']),
                        'scope':'FIRST_PAGE_ONLY'}
            except AirwallexHTTPError as error:
                probes[name]={'allowed':False,'http_status':error.status,'code':error.code}
            except (OSError,ValueError,RuntimeError):probes[name]={'allowed':False,'status':'UNAVAILABLE'}
        if result['issuing_read']:
            diagnosis='ISSUING_READ_AVAILABLE'
        elif probes['balances']['allowed'] and result.get('http_status') in {401,403}:
            diagnosis='ISSUING_PERMISSION_DENIED'
            result['reason']='Account authentication works, but issuing permission is denied. Check scoped-key issuing permissions and account enablement.'
        elif probes['balances'].get('code') in {'credentials_invalid','credentials_expired'}:
            diagnosis='AUTHENTICATION_REJECTED'
        else:diagnosis='ACCOUNT_OR_ISSUING_ACCESS_UNRESOLVED'
        result.update(diagnosis=diagnosis,read_probes=probes,
            account_context_configured=bool(getattr(self.client,'account_id',None)),
            required_read_scopes=['Issuing / Cards / Read','Issuing / Cardholders / Read','Issuing / Config / Read'],
            remediation=['Select the configured sandbox account under the current scoped API key.',
                'In Settings > Developer > API keys, enable the required account-level issuing read scopes.',
                'If issuing scopes are unavailable, ask the account owner or Airwallex to enable Issuing APIs.',
                'Recheck access. Creating a card or spending still requires its own explicit approval.'],
            scope_reference='https://www.airwallex.com/docs/developer-tools/api/api-key-scopes',
            enablement_reference='https://www.airwallex.com/docs/issuing/test-and-go-live/integration-checklist')
        if result['issuing_read']:
            result['required_write_scopes']=['Issuing / Cards / Write']
            result['remediation']=[
                'Issuing reads pass. An account owner must enable Cards / Write on the selected scoped sandbox key.',
                'Use an existing READY individual cardholder for the personalized commercial card; Cardholders / Write is needed only if a cardholder must be created.',
                'Confirm the allowed card program and creation limit with Airwallex; Config / Write is not required to create a card.',
                'Approve a fresh card scope, amount, currency and expiry before creation. Issuing and merchant payment are separate operations.']
        result['api_version']=self.api_version
        return result

    @staticmethod
    def body(scope, cardholder_id, created_by, cap_micro, currency, expires_at, *, read_only=False, personalized=True):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',scope) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',cardholder_id):
            raise ValueError('Valid issuing scope and existing cardholder ID required')
        if not isinstance(created_by,str) or not created_by.strip() or len(created_by)>100:
            raise ValueError('Issuer requires the requesting user name')
        if type(personalized) is not bool:raise ValueError('Personalization must be an explicit boolean')
        if type(cap_micro) is not int or not 0<cap_micro<=1000000 or currency not in {'USD','EUR','SGD'}:
            raise ValueError('Sandbox card cap must be positive, at most one currency unit and whole cents')
        amount=api_usd(cap_micro)
        expiry=datetime.fromisoformat(expires_at.replace('Z','+00:00'))
        if expiry.tzinfo is None or (not read_only and not 0<(expiry-datetime.now(timezone.utc)).total_seconds()<=3600):
            raise ValueError('Card controls must expire within one hour')
        return {'cardholder_id':cardholder_id,'created_by':created_by,'form_factor':'VIRTUAL',
                'is_personalized':personalized,'program':{'purpose':'COMMERCIAL'},'client_data':scope,
                'authorization_controls':{'allowed_transaction_count':'SINGLE','allowed_currencies':[currency],
                    'active_to':expires_at,'blocked_transaction_usages':[{'transaction_scope':'CASH_WITHDRAWAL','usage_scope':'ALL'}],
                    'transaction_limits':{'currency':currency,'limits':[{'interval':'PER_TRANSACTION','amount':amount},
                                                                        {'interval':'ALL_TIME','amount':amount}]}}}

    def issue(self, scope, cardholder_id, created_by, cap_micro, currency, expires_at, *, execute=False, personalized=True):
        if not execute:
            raise ValueError('Issuing requires --execute and separate written approval with a stated card cap')
        body=self.body(scope,cardholder_id,created_by,cap_micro,currency,expires_at,personalized=personalized)
        account=getattr(self.client,'account_id',None)
        if not account:raise ValueError('An explicit sandbox account context is required')
        holder=self._request('GET','/api/v1/issuing/cardholders/'+cardholder_id)
        if (not isinstance(holder,dict) or holder.get('cardholder_id')!=cardholder_id
                or holder.get('status')!='READY' or holder.get('type') not in (
                    {'INDIVIDUAL'} if personalized else {'INDIVIDUAL','DELEGATE'})):
            raise PolicyError('Card creation requires an approved READY compatible cardholder; no create sent')
        digest_body={**body,'account_context_sha256':hashlib.sha256(account.encode()).hexdigest()}
        self._bind_mandate(scope, digest_body)
        request_id,prior=self.journal.begin(scope,'issue','/api/v1/issuing/cards/create',digest_body)
        if prior:
            return self._read_and_validate(prior['id'],body,request_id=request_id)
        try:
            raw=self._request('POST','/api/v1/issuing/cards/create',{**body,'request_id':request_id})
            card_id=raw.get('card_id') if isinstance(raw,dict) else None
            if not isinstance(card_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',card_id):
                raise ValueError('Issuing response has no safe object ID')
            result=self._read_and_validate(card_id,body,request_id=request_id)
            self.journal.observe(scope,'issue',{'id':card_id,'status':result['status']})
            return result
        except Exception:
            self.journal.uncertain(scope,'issue')
            raise OutcomeUnknown('Card creation outcome needs read-only reconciliation; never create another card') from None

    def _read_and_validate(self, card_id, expected, *, request_id):
        if not isinstance(card_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',card_id):
            raise ValueError('Invalid card identifier; no request sent')
        raw=self._request('GET','/api/v1/issuing/cards/'+card_id)
        if not isinstance(raw,dict):raise ValueError('Invalid card read-back')
        actual=raw.get('authorization_controls',{})
        controls=expected['authorization_controls']
        if (raw.get('card_id')!=card_id or raw.get('request_id')!=request_id
                or raw.get('card_status') not in {'PENDING','FAILED','INACTIVE','ACTIVE','LOST','STOLEN','CLOSED','BLOCKED','EXPIRED','UNKNOWN'}
                or raw.get('form_factor')!='VIRTUAL' or raw.get('is_personalized') is not expected['is_personalized']
                or raw.get('created_by')!=expected['created_by']
                or not isinstance(raw.get('program'),dict) or raw['program'].get('purpose')!='COMMERCIAL'
                or raw.get('client_data')!=expected['client_data'] or not isinstance(actual,dict)
                or actual.get('allowed_transaction_count')!='SINGLE' or actual.get('transaction_limits')!=controls['transaction_limits']
                or actual.get('allowed_currencies')!=controls['allowed_currencies']
                or raw.get('cardholder_id')!=expected['cardholder_id']
                or actual.get('blocked_transaction_usages')!=controls['blocked_transaction_usages']
                or datetime.fromisoformat(actual.get('active_to','').replace('Z','+00:00'))!=datetime.fromisoformat(controls['active_to'].replace('Z','+00:00'))):
            raise ValueError('Issued card controls do not match the immutable approved cap, currency or expiry')
        return {'label':getattr(self.client,'evidence_label','MOCK'),'mode':self.mode,'card_id':card_id,
                'status':raw['card_status'],'controls_verified':True,'sensitive_card_details_requested':False,
                'authorization_controls':controls,'merchant_payment_completed':False,'visa_approved_agent':False}

    def reconcile(self, scope, cardholder_id, created_by, cap_micro, currency, expires_at, *, personalized=True):
        expected=self.body(scope,cardholder_id,created_by,cap_micro,currency,expires_at,read_only=True,personalized=personalized)
        row=self.journal.get(scope,'issue')
        if not row:raise ValueError('No original issuing operation to reconcile')
        bound={**expected,'account_context_sha256':hashlib.sha256(self.client.account_id.encode()).hexdigest()}
        if row['digest']!=hashlib.sha256(canonical(bound).encode()).hexdigest():
            raise ValueError('Reconciliation terms differ from the original issuing mandate')
        prior=json.loads(row['response']) if row['response'] else {}
        card_id=prior.get('id')
        if not card_id:
            found=set()
            for page in range(10):
                query=urlencode({'page_size':100,'page_num':page,'cardholder_id':cardholder_id})
                result=self._request('GET','/api/v1/issuing/cards?'+query)
                if (not isinstance(result,dict) or not isinstance(result.get('items'),list)
                        or len(result['items'])>100 or type(result.get('has_more')) is not bool):
                    raise OutcomeUnknown('Incomplete issuing read-back')
                for item in result['items']:
                    if not isinstance(item,dict):raise OutcomeUnknown('Invalid card list')
                    candidate=item.get('card_id')
                    if not isinstance(candidate,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',candidate):
                        raise OutcomeUnknown('Card list has no safe identifier')
                    if item.get('cardholder_id')!=cardholder_id:continue
                    # Lists omit client_data, request_id and authorization controls.
                    detail=self._request('GET','/api/v1/issuing/cards/'+candidate)
                    if not isinstance(detail,dict) or detail.get('card_id')!=candidate:
                        raise OutcomeUnknown('Invalid card detail read-back')
                    if detail.get('request_id')==row['request_id'] and detail.get('client_data')==scope:
                        found.add(candidate)
                if not result['has_more']:break
            else:raise OutcomeUnknown('Issuing read-back exceeds the bounded page limit')
            if len(found)!=1:raise OutcomeUnknown('No unique issued card found; retain the original request and do not recreate')
            card_id=next(iter(found))
        result=self._read_and_validate(card_id,expected,request_id=row['request_id'])
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
        card = self._read_and_validate(card_id, expected, request_id=issued['request_id'])
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
