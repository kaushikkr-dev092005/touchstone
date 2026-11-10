import copy
import json
from pathlib import Path
import tempfile
import unittest

from touchstone.holds import OperationJournal, OutcomeUnknown
from touchstone.ledger import PolicyError
from touchstone.merchant_onboarding import execute, expected_catalog, fingerprint, PREFIX, read_config
from touchstone.treasury import AirwallexHTTPError


class MerchantOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.journal=OperationJournal(Path(self.directory.name)/'journal.sqlite')
        self.saved=json.loads((Path(__file__).resolve().parent.parent/'bench/results/completion-20261110/merchant-onboarding-plan.json').read_text())
        self.saved['approved']=True;self.origin=self.saved['plan']['origin']
        self.approval=self.saved['plan_sha256'][:16]
        self.config={'OAUTH_PRIVATE_JWK':json.dumps({'n':'fixture-public-modulus','e':'AQAB','kid':'fixture'}),
                     'CHECKOUT_HMAC_SECRET':'fixture-only-'*4}
        origin=self.origin
        class Client:
            account_id='fixture-account';client_id='fixture-client';api_key='fixture-key'
            state=None;lose=None
            def __init__(self):self.calls=[]
            def request(self,method,path,body=None):
                self.calls.append((method,path))
                if method=='GET':
                    if self.state is None:raise AirwallexHTTPError(404,'MERCHANT_CONFIG_NOT_FOUND')
                    return copy.deepcopy(self.state)
                if path==PREFIX+'/onboard':
                    self.state={'merchant_id':'fixture-merchant','status':'active',
                        'psp_config':{'psp_name':'AIRWALLEX','client_id':self.client_id,'api_key_configured':True,'managed_payment':True},
                        'apis':{'create_checkout':origin+'/api/checkout','secret_key_configured':True},
                        'whitelisted_image_domains':[origin],
                        'mcp_endpoints':{'acp':'/pa/ai/fixture-merchant/acp/mcp'},
                        'product_upload':{'url':'private-signed-url-never-publish'}}
                    if self.lose=='onboard':raise RuntimeError('lost response')
                    return copy.deepcopy(self.state)
                assert path==PREFIX+'/products' and len(body['gmc_products'])==100
                if self.lose=='catalog':raise RuntimeError('lost response')
                return {'records_added':100,'records_updated':0,'records_failed':0,'error_gcs_file_loc':None}
        self.client=Client()

    def reader(self,url):
        path=url.removeprefix(self.origin)
        if path=='/api/merchant-health':return {'mode':'SANDBOX_ONLY','payment_dispatch':False,'hosted_inference':False}
        if path=='/.well-known/jwks.json':return {'keys':[json.loads(self.config['OAUTH_PRIVATE_JWK'])]}
        if path=='/catalog.json':return {'mode':'SYNTHETIC_SANDBOX','products':expected_catalog(self.origin)}
        return {**{k:self.origin+v for k,v in {'issuer':'','authorization_endpoint':'/oauth/authorize',
            'token_endpoint':'/oauth/token','registration_endpoint':'/oauth/register','jwks_uri':'/.well-known/jwks.json'}.items()},
            'code_challenge_methods_supported':['S256']}

    def run_plan(self,approval=None):
        return execute(self.client,self.journal,self.saved,self.config,approval or self.approval,self.reader)

    def posts(self):return [c for c in self.client.calls if c[0]=='POST']

    def test_exact_two_configuration_posts_and_replay_does_not_write(self):
        report=self.run_plan();self.assertEqual(report['catalog']['records_added'],100)
        self.assertFalse(report['oauth_gateway_verification']);self.assertEqual(report['financial_transactions'],0)
        self.assertNotIn('private-signed-url',json.dumps(report))
        self.assertEqual(self.posts(),[('POST',PREFIX+'/onboard'),('POST',PREFIX+'/products')])
        self.run_plan();self.assertEqual(len(self.posts()),2)

    def test_missing_approval_or_changed_plan_refuses_before_network(self):
        with self.assertRaises(PolicyError):self.run_plan('wrong')
        self.assertFalse(self.client.calls)
        self.saved['plan']['maximum_onboarding_posts']=2
        self.saved['plan_sha256']=fingerprint(self.saved['plan'])
        with self.assertRaises(PolicyError):self.run_plan(self.saved['plan_sha256'][:16])
        self.assertFalse(self.client.calls)

    def test_existing_config_is_never_replaced_or_uploaded(self):
        self.client.state={'existing':'configuration'}
        with self.assertRaises(PolicyError):self.run_plan()
        self.assertFalse(self.posts())

    def test_lost_onboarding_response_is_not_retried_even_when_config_exists(self):
        self.client.lose='onboard'
        with self.assertRaises(OutcomeUnknown):self.run_plan()
        self.assertIsNotNone(read_config(self.client))
        with self.assertRaises(OutcomeUnknown):self.run_plan()
        self.assertEqual(len(self.posts()),1)

    def test_lost_catalog_response_never_reuploads(self):
        self.client.lose='catalog'
        with self.assertRaises(OutcomeUnknown):self.run_plan()
        with self.assertRaises(OutcomeUnknown):self.run_plan()
        self.assertEqual(len(self.posts()),2)

    def test_changed_account_and_hosted_key_cannot_use_original_scope(self):
        self.run_plan();self.client.account_id='other-account'
        with self.assertRaises(ValueError):self.run_plan()
        self.assertEqual(len(self.posts()),2)
        self.config['OAUTH_PRIVATE_JWK']=json.dumps({'n':'wrong-key','e':'AQAB','kid':'fixture','d':'private'})
        with self.assertRaises(PolicyError):self.run_plan()
        self.assertEqual(len(self.posts()),2)
