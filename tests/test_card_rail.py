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
    def __init__(self):self.calls=[];self.card=None;self.lose=False
    def request(self,method,path,body=None):
        self.calls.append((method,path))
        if method=='POST':
            self.card={'id':'card_fixture','status':'ACTIVE',**copy.deepcopy(body)}
            if self.lose:raise OSError('Lost response')
            return self.card
        if '/cards?' in path:return {'items':[self.card] if self.card else []}
        return self.card


class CardRailTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.client=Client();self.rail=CardRail(self.client,OperationJournal(Path(self.temp.name)/'journal.sqlite'))
        self.args=('scope','holder_fixture','Fixture Operator',10000,'USD',(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat())

    def test_issue_requires_execute_before_any_bank_request(self):
        with self.assertRaises(ValueError):self.rail.issue(*self.args)
        self.assertEqual(self.client.calls,[])

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

    def test_read_only_doctor_does_not_claim_issuing_write_or_visa_identity(self):
        result=self.rail.doctor()
        self.assertFalse(result['issuing_write_verified']);self.assertEqual(result['cards_created'],0)
        self.assertEqual(self.client.calls[0][0],'GET')

    def diagnose(self, denied=False, authentication=False):
        def request(method,path,body=None):
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
