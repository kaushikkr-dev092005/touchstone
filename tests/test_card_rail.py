import copy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from touchstone.card_rail import CardRail
from touchstone.holds import OperationJournal,OutcomeUnknown
from touchstone.ledger import PolicyError
from touchstone.treasury import AirwallexHTTPError


class Client:
    account_id='acct_fixture';evidence_label='MOCK'
    def __init__(self):self.calls=[];self.versions=[];self.card=None;self.lose=False;self.holder_status='READY';self.holder_type='INDIVIDUAL'
    def request(self,method,path,body=None,api_version=None):
        self.calls.append((method,path))
        self.versions.append(api_version)
        if '/cardholders/' in path:return {'cardholder_id':path.rsplit('/',1)[-1],
            'status':self.holder_status,'type':self.holder_type}
        if method=='POST':
            self.card={'card_id':'card_fixture','card_status':'ACTIVE',**copy.deepcopy(body)}
            if self.lose:raise OSError('Lost response')
            return self.card
        if '/cards?' in path:return {'has_more':False,'items':[
            {k:self.card[k] for k in ('card_id','card_status','cardholder_id')}] if self.card else []}
        return self.card


class CardRailTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.client=Client();self.rail=CardRail(self.client,OperationJournal(Path(self.temp.name)/'journal.sqlite'))
        self.args=('scope','holder_fixture','Fixture Operator',10000,'USD',(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())

    def test_issue_requires_execute_before_any_bank_request(self):
        with self.assertRaises(ValueError):self.rail.issue(*self.args)
        self.assertEqual(self.client.calls,[])

    def test_missing_cardholder_approval_or_delegate_type_blocks_before_creation(self):
        for status,kind in [('PENDING','INDIVIDUAL'),('READY','DELEGATE')]:
            self.client.holder_status,self.client.holder_type=status,kind
            with self.assertRaises(PolicyError):self.rail.issue(*self.args,execute=True)
        self.assertFalse(any(m=='POST' for m,_ in self.client.calls))
        self.assertIsNone(self.rail.journal.get('scope','issue'))

    def test_capped_single_use_currency_expiry_and_readback(self):
        result=self.rail.issue(*self.args,execute=True)
        self.assertEqual(result['label'],'MOCK');self.assertTrue(result['controls_verified'])
        self.assertFalse(result['merchant_payment_completed'])
        controls=result['authorization_controls']
        self.assertEqual(controls['allowed_transaction_count'],'SINGLE')
        self.assertEqual(controls['transaction_limits']['limits'][1],{'interval':'ALL_TIME','amount':0.01})
        self.rail.issue(*self.args,execute=True)
        self.assertEqual(sum(m=='POST' for m,_ in self.client.calls),1)
        self.assertFalse(any('/details' in p for _,p in self.client.calls))
        self.assertEqual(set(self.client.versions),{'2024-03-31'})

    def test_unknown_create_cannot_be_retried(self):
        self.client.lose=True
        for _ in range(2):
            with self.assertRaises(OutcomeUnknown):self.rail.issue(*self.args,execute=True)
        self.assertEqual(sum(m=='POST' for m,_ in self.client.calls),1)

    def test_issuing_does_not_silently_make_a_merchant_charge_or_fallback(self):
        with self.assertRaises(PolicyError):self.rail.pay('job',10000)
        self.assertEqual(self.client.calls,[])

    def test_unknown_issue_is_recovered_by_readback_without_a_second_create(self):
        self.client.lose=True
        with self.assertRaises(OutcomeUnknown):self.rail.issue(*self.args,execute=True)
        result=self.rail.reconcile(*self.args)
        self.assertTrue(result['controls_verified'])
        self.assertEqual(sum(m=='POST' for m,_ in self.client.calls),1)
        self.assertTrue(any(m=='GET' and p=='/api/v1/issuing/cards/card_fixture' for m,p in self.client.calls))

    def test_changed_request_or_controls_never_become_an_observed_card(self):
        self.client.lose=True
        with self.assertRaises(OutcomeUnknown):self.rail.issue(*self.args,execute=True)
        original=copy.deepcopy(self.client.card)
        for change in ({'request_id':'another-operation'},{'is_personalized':False},
                       {'program':{'purpose':'CONSUMER'}},{'created_by':'Another Operator'}):
            with self.subTest(change=change):
                self.client.card={**copy.deepcopy(original),**change}
                with self.assertRaises((ValueError,OutcomeUnknown)):self.rail.reconcile(*self.args)
                self.assertEqual(self.rail.journal.get('scope','issue')['state'],'UNKNOWN')
        self.assertEqual(sum(m=='POST' for m,_ in self.client.calls),1)

    def test_card_detail_must_match_the_listed_card_identifier(self):
        self.client.lose=True
        with self.assertRaises(OutcomeUnknown):self.rail.issue(*self.args,execute=True)
        original=self.client.request
        def request(method,path,body=None,api_version=None):
            raw=original(method,path,body,api_version)
            if '/cards?' not in path:raw={**raw,'card_id':'different-card'}
            return raw
        with patch.object(self.client,'request',side_effect=request):
            with self.assertRaises(OutcomeUnknown):self.rail.reconcile(*self.args)
        self.assertEqual(sum(m=='POST' for m,_ in self.client.calls),1)

    def test_incomplete_card_list_cannot_resolve_an_unknown_create(self):
        self.client.lose=True
        with self.assertRaises(OutcomeUnknown):self.rail.issue(*self.args,execute=True)
        original=self.client.request
        def request(method,path,body=None,api_version=None):
            if '/cards?' in path:return {'items':[]}
            return original(method,path,body,api_version)
        with patch.object(self.client,'request',side_effect=request):
            with self.assertRaises(OutcomeUnknown):self.rail.reconcile(*self.args)
        self.assertEqual(sum(m=='POST' for m,_ in self.client.calls),1)

    def test_read_only_doctor_does_not_claim_issuing_write_or_visa_identity(self):
        result=self.rail.doctor()
        self.assertFalse(result['issuing_write_verified']);self.assertEqual(result['cards_created'],0)
        self.assertEqual(self.client.calls[0][0],'GET')

    def diagnose(self, denied=False, authentication=False):
        def request(method,path,body=None,api_version=None):
            self.client.calls.append((method,path))
            self.assertEqual(method,'GET')
            if authentication or (denied and '/issuing/' in path):
                error=AirwallexHTTPError(401,'credentials_invalid' if authentication else 'unauthorized')
                error.private_message='private provider message'
                raise error
            if '/balances/' in path:return []
            if path.endswith('/config'):return {'private':'must not appear'}
            return {'items':[{'private':'must not appear'}]}
        with patch.object(self.client,'request',side_effect=request):
            return self.rail.doctor(diagnose=True)

    def test_diagnosis_distinguishes_issuing_permission_from_authentication(self):
        result=self.diagnose(denied=True)
        self.assertEqual(result['diagnosis'],'ISSUING_PERMISSION_DENIED')
        self.assertTrue(result['read_probes']['balances']['allowed'])
        self.assertFalse(result['issuing_read'])
        self.assertNotIn('private provider message',str(result))
        self.assertEqual(len(self.client.calls),4)
        result=self.diagnose(authentication=True)
        self.assertEqual(result['diagnosis'],'AUTHENTICATION_REJECTED')

    def test_successful_diagnosis_verifies_reads_only_and_omits_raw_data(self):
        result=self.diagnose()
        self.assertEqual(result['diagnosis'],'ISSUING_READ_AVAILABLE')
        self.assertEqual(result['label'],'MOCK')
        self.assertTrue(all(p['allowed'] for p in result['read_probes'].values()))
        self.assertNotIn('must not appear',str(result))
        self.assertFalse(result['issuing_write_verified'])
        self.assertFalse(result['merchant_payment_supported'])
        self.assertEqual(result['visa_tap_identity'],'NOT_VERIFIED')
        self.assertEqual(result['cards_created'],0)

    def test_cap_cannot_change_after_issue(self):
        self.rail.issue(*self.args,execute=True)
        args=list(self.args);args[3]=20000
        with self.assertRaises(ValueError):self.rail.issue(*args,execute=True)
