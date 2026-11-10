"""Capped sandbox configuration writes. Never calls a payment or model endpoint."""
import hashlib
import json
import re
import urllib.request
from urllib.parse import urlsplit

from .holds import OutcomeUnknown
from .ledger import PolicyError, canonical
from .treasury import AirwallexHTTPError, NoRedirect

PREFIX = '/api/v1/pa/agentic_commerce'
SCOPE = 'merchant-onboarding-20261111-v1'


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def approved_plan(saved, approval):
    plan = saved['plan']
    digest = fingerprint(plan)
    if not saved.get('approved') or digest != saved.get('plan_sha256') or approval != digest[:16]:
        raise PolicyError('Exact approved merchant plan required')
    origin = urlsplit(plan['origin'])
    if (origin.scheme != 'https' or not origin.hostname or not origin.hostname.endswith('.chatgpt.site')
            or origin.username or origin.password or origin.port or origin.path or origin.query or origin.fragment):
        raise PolicyError('Expected the approved HTTPS Sites origin')
    expected = {'mode':'SANDBOX_CONFIGURATION_ONLY','make_public':True,
        'checkout_url':plan['origin']+'/api/checkout','oauth_issuer':plan['origin'],
        'jwks_url':plan['origin']+'/.well-known/jwks.json','maximum_onboarding_posts':1,
        'maximum_catalog_upserts':1,'synthetic_catalog_products':100,
        'existing_config_replacement_allowed':False,'automatic_retries_allowed':False,
        'unknown_write_outcome':'READ_ONLY_RECONCILIATION_REQUIRED','merchant_charges':0,
        'new_cards':0,'funding_transfers':0,'model_calls':0,'new_cash_usd':'0.00',
        'claude_total_ceiling_usd':'3.00','gpu_start':False,
        'bank_or_model_credentials_hosted':False,'raw_secret_values_published':False,
        'support_messages_authorized':False}
    if any(plan.get(k) != v for k,v in expected.items()):
        raise PolicyError('Configuration limits changed')
    return plan


def public_json(url):
    request = urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'Touchstone-Sandbox-Verification/1.0'})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=25) as response:
        if response.status != 200:
            raise ValueError('Merchant endpoint unavailable anonymously')
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError('Merchant response too large')
        return json.loads(data)


def expected_catalog(origin):
    return [{'id':f'invoice-lab-{i:03d}','title':f'Synthetic invoice practice set {i:03d}',
        'description':'Synthetic source documents for sandbox verification testing. No inference or real invoice payment.',
        'link':origin+f'/products/invoice-lab-{i:03d}','image_link':origin+'/product-image.png',
        'availability':'in_stock' if i<=95 else 'out_of_stock','price':'0.01 USD','condition':'new'}
        for i in range(1,101)]


def preflight(plan, config, reader=public_json):
    origin = plan['origin']
    health = reader(origin+'/api/merchant-health')
    if (health.get('mode') != 'SANDBOX_ONLY' or health.get('payment_dispatch') is not False
            or health.get('hosted_inference') is not False):
        raise PolicyError('Sandbox service guard failed')
    discovery = reader(origin+'/.well-known/openid-configuration')
    for name,path in {'issuer':'','authorization_endpoint':'/oauth/authorize','token_endpoint':'/oauth/token',
                      'registration_endpoint':'/oauth/register','jwks_uri':'/.well-known/jwks.json'}.items():
        if discovery.get(name) != origin+path:
            raise PolicyError('OAuth endpoint origin differs')
    if discovery.get('code_challenge_methods_supported') != ['S256']:
        raise PolicyError('PKCE S256 required')
    public = reader(plan['jwks_url'])['keys']
    local = json.loads(config['OAUTH_PRIVATE_JWK'])
    if (len(public) != 1 or any(public[0].get(k) != local.get(k) for k in ('n','e','kid'))
            or any(k in public[0] for k in ('d','p','q','dp','dq','qi'))):
        raise PolicyError('Hosted signing key mismatch or private key exposure')
    if len(config.get('CHECKOUT_HMAC_SECRET','')) < 32:
        raise PolicyError('Checkout signing secret unavailable')
    catalog = expected_catalog(origin)
    if reader(origin+'/catalog.json') != {'mode':'SYNTHETIC_SANDBOX','products':catalog}:
        raise PolicyError('Public catalog differs from the approved synthetic products')
    return catalog


def read_config(client):
    try:
        return client.request('GET', PREFIX+'/config')
    except AirwallexHTTPError as error:
        if error.status == 404 and error.code == 'MERCHANT_CONFIG_NOT_FOUND':
            return None
        raise


def verify_config(raw, plan, client):
    if not isinstance(raw,dict):raise ValueError('Invalid merchant response')
    psp, apis = raw.get('psp_config',{}), raw.get('apis',{})
    merchant = raw.get('merchant_id')
    if (not isinstance(merchant,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,150}',merchant)
            or raw.get('status') != 'active' or psp.get('psp_name') != 'AIRWALLEX'
            or psp.get('client_id') != client.client_id or psp.get('api_key_configured') is not True
            or psp.get('managed_payment') is not True or apis.get('create_checkout') != plan['checkout_url']
            or apis.get('secret_key_configured') is not True
            or raw.get('whitelisted_image_domains') != [plan['origin']]
            or raw.get('mcp_endpoints',{}).get('acp') != f'/pa/ai/{merchant}/acp/mcp'):
        raise PolicyError('Merchant read-back differs from the submitted sandbox configuration')
    return {'status':'active','merchant_fingerprint':fingerprint(merchant),
        'checkout_url':plan['checkout_url'], 'psp_key_configured':True,'checkout_secret_configured':True,
        'mcp_url':'https://mcp.sandbox.airwallex.com'+raw['mcp_endpoints']['acp'],
        'oauth_values_returned_by_config_read':False}


def binding_terms(client, plan, config):
    if not client.account_id:raise PolicyError('Explicit sandbox account required')
    return {'plan_sha256':fingerprint(plan),'account':fingerprint(client.account_id),
        'client':fingerprint(client.client_id),'api_key':fingerprint(client.api_key),
        'checkout_secret':fingerprint(config['CHECKOUT_HMAC_SECRET']),
        'public_jwk':{k:json.loads(config['OAUTH_PRIVATE_JWK'])[k] for k in ('n','e','kid')}}


def execute(client, journal, saved, config, approval, reader=public_json):
    plan = approved_plan(saved, approval)
    binding = binding_terms(client,plan,config)
    catalog = preflight(plan, config, reader)
    _, prior = journal.begin(SCOPE,'binding','/local/approved-merchant-plan',binding)
    if prior is None:journal.observe_raw(SCOPE,'binding',{'bound':True})
    for action in ('onboard','catalog'):
        old = journal.get(SCOPE,action)
        if old and old['state'] != 'OBSERVED':
            raise OutcomeUnknown('Prior configuration write unresolved; status is read-only, never repeat a POST')
    payload = {'psp_config':{'api_key_data':{'client_id':client.client_id,'api_key':client.api_key}},
        'apis':{'create_checkout':plan['checkout_url'],'secret_key':config['CHECKOUT_HMAC_SECRET'],
                'oauth':{'acp':{'oauth_base':plan['oauth_issuer'],'oauth_jwks':plan['jwks_url'],'scopes':['openid','email']}}},
        'whitelisted_image_domains':[plan['origin']]}
    if not journal.get(SCOPE,'onboard'):
        if read_config(client) is not None:
            raise PolicyError('Existing merchant configuration found; no writes or replacement authorized')
    _, observed = journal.begin(SCOPE,'onboard',PREFIX+'/onboard',payload)
    if observed is None:
        try:
            observed = verify_config(client.request('POST',PREFIX+'/onboard',payload),plan,client)
            journal.observe_raw(SCOPE,'onboard',observed)
        except Exception as error:
            journal.error(SCOPE,'onboard',error);journal.uncertain(SCOPE,'onboard')
            raise OutcomeUnknown('Onboarding outcome requires read-only reconciliation; no automatic retry') from None
    current = verify_config(read_config(client),plan,client)
    if current != observed:raise PolicyError('Configuration changed after onboarding; no catalog write sent')
    products = {'type':'gmc','gmc_products':catalog}
    _, counts = journal.begin(SCOPE,'catalog',PREFIX+'/products',products)
    if counts is None:
        try:
            raw = client.request('POST',PREFIX+'/products',products)
            counts = {name:raw.get(name) for name in ('records_added','records_updated','records_failed')}
            if (any(type(n) is not int or n<0 for n in counts.values()) or sum(counts.values()) != 100):
                raise ValueError('Catalog row counts are incomplete')
            counts['error_report_present'] = bool(raw.get('error_gcs_file_loc'))
            journal.observe_raw(SCOPE,'catalog',counts)
        except Exception as error:
            journal.error(SCOPE,'catalog',error);journal.uncertain(SCOPE,'catalog')
            raise OutcomeUnknown('Catalog outcome requires read-only reconciliation; never repeat the upload') from None
    return {'label':'MEASURED_SANDBOX_CONFIGURATION','plan_sha256':fingerprint(plan),
        'phase':'MERCHANT_AND_CATALOG_OBSERVED' if counts['records_failed']==0 else 'CATALOG_PARTIAL_NO_RETRY',
        'configuration':current,'catalog':counts,'oauth_configuration_submitted':True,
        'oauth_gateway_verification':False,'financial_transactions':0,'model_calls':0,
        'new_cards':0,'visa_approved':False}
