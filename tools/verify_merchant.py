"""Verify guest OAuth, MCP discovery and one catalog read; never mutates checkout."""
import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit, parse_qs

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tools.run_issuing_proof import save


class StopRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        # OAuth consent intentionally returns the authorization code in Location.
        # Read that response; never follow it or forward the cookie/bearer token.
        return None


def main():
    directory=ROOT/'bench/results/completion-20261110'
    onboarding=json.loads((directory/'merchant-onboarding.json').read_text(encoding='utf-8'))
    plan=json.loads((directory/'merchant-onboarding-plan.json').read_text(encoding='utf-8'))['plan']
    origin=plan['origin'];gateway=onboarding['configuration']['mcp_url']
    if not re.fullmatch(r'https://mcp\.sandbox\.airwallex\.com/pa/ai/[A-Za-z0-9_-]+/acp/mcp',gateway):
        raise ValueError('Only the returned sandbox MCP endpoint is allowed')
    opener=urllib.request.build_opener(StopRedirect())
    def request(url,body=None,headers=None):
        if not (url.startswith(origin+'/') or url==gateway):raise ValueError('Unexpected credential destination')
        h={'User-Agent':'Touchstone-Sandbox-Verification/1.0',**(headers or {})}
        req=urllib.request.Request(url,data=body,headers=h)
        try:
            with opener.open(req,timeout=30) as response:return response.status,response.read(2_000_000),response.headers
        except urllib.error.HTTPError as error:return error.code,error.read(20000),error.headers
    def post(url,value,headers=None):
        return request(url,json.dumps(value).encode(),{'Content-Type':'application/json',**(headers or {})})
    health_status,_,_=request(origin+'/api/merchant-health')
    # Keep this observation separate: a hosting edge can gate a diagnostic while
    # the actual merchant/OAuth endpoints remain anonymously reachable.
    status,raw,_=request(origin+'/.well-known/openid-configuration')
    assert status==200 and json.loads(raw)['issuer']==origin,'Public OAuth discovery unavailable'
    status,_,_=post(gateway,{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'touchstone-zero-cost-verification','version':'1'}}},{'Accept':'application/json, text/event-stream'})
    assert status==401,'Gateway must require guest OAuth'
    redirect='http://127.0.0.1:3334/callback';verifier=secrets.token_urlsafe(48)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    status,raw,_=post(origin+'/oauth/register',{'redirect_uris':[redirect],'client_name':'Touchstone zero-cost guest verification','token_endpoint_auth_method':'none'})
    assert status==201,'Guest client registration failed'
    client=json.loads(raw)['client_id'];state=secrets.token_urlsafe(24)
    query=urlencode({'client_id':client,'redirect_uri':redirect,'response_type':'code','scope':'openid email',
        'code_challenge':challenge,'code_challenge_method':'S256','resource':gateway,'state':state})
    status,raw,headers=request(origin+'/oauth/authorize?'+query);assert status==200,'Guest consent unavailable'
    text=raw.decode();consent=re.search(r'name="consent_id" value="([^"]+)"',text)[1];csrf=re.search(r'name="csrf" value="([^"]+)"',text)[1]
    cookie=headers.get('Set-Cookie').split(';',1)[0]
    status,_,headers=request(origin+'/oauth/consent',urlencode({'consent_id':consent,'csrf':csrf,'decision':'allow'}).encode(),
        {'Content-Type':'application/x-www-form-urlencoded','Origin':origin,'Cookie':cookie})
    assert status==302,'Guest consent did not complete'
    location=urlsplit(headers['Location']);assert location.scheme=='http' and location.netloc=='127.0.0.1:3334' and location.path=='/callback'
    params=parse_qs(location.query);assert params['state']==[state]
    form=urlencode({'grant_type':'authorization_code','code':params['code'][0],'client_id':client,'redirect_uri':redirect,'code_verifier':verifier}).encode()
    status,raw,_=request(origin+'/oauth/token',form,{'Content-Type':'application/x-www-form-urlencoded'});assert status==200,'Token issuance failed'
    token=json.loads(raw)['access_token'];parts=token.split('.')
    claims=json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4)))
    assert claims['iss']==origin and claims['aud']==gateway and claims['iat']<=time.time()<claims['exp'] and 'awx_customer_id' not in claims
    def rpc(body,bearer=token,session=None):
        headers={'Authorization':'Bearer '+bearer,'Accept':'application/json, text/event-stream'}
        if session:headers['Mcp-Session-Id']=session;headers['MCP-Protocol-Version']='2025-06-18'
        status,raw,response_headers=post(gateway,body,headers)
        if response_headers.get('Content-Type','').startswith('text/event-stream'):
            messages=[json.loads(line[6:]) for line in raw.decode().splitlines() if line.startswith('data: ')]
            result=next((m for m in messages if m.get('id')==body.get('id')),None)
        else:
            try:result=json.loads(raw) if raw else None
            except ValueError:result=None
        return status,result,response_headers
    bad=parts[0]+'.'+parts[1]+'.'+('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
    init={'jsonrpc':'2.0','id':2,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'touchstone-zero-cost-verification','version':'1'}}}
    status,_,_=rpc(init,bad);assert status==401,'Gateway accepted a tampered signature'
    status,result,headers=rpc(init);assert status==200 and result and 'result' in result,'Gateway rejected the signed guest token'
    session=headers.get('Mcp-Session-Id');version=result['result'].get('protocolVersion')
    status,_,_=rpc({'jsonrpc':'2.0','method':'notifications/initialized'},session=session);assert status in (200,202,204)
    status,result,_=rpc({'jsonrpc':'2.0','id':3,'method':'tools/list','params':{}},session=session)
    assert status==200 and result and 'tools' in result.get('result',{}),'MCP tools discovery failed'
    tools=result['result']['tools']
    (ROOT/'tmp').mkdir(exist_ok=True)
    save(ROOT/'tmp/merchant-tool-contracts.json',{'tools':tools})
    render=next(t for t in tools if t['name']=='render_products')
    assert render.get('annotations',{}).get('readOnlyHint') is True
    status,catalog_result,_=rpc({'jsonrpc':'2.0','id':4,'method':'tools/call',
        'params':{'name':'render_products','arguments':{'productIds':['invoice-lab-001','invoice-lab-050','invoice-lab-100']}}},session=session)
    assert status==200 and catalog_result and 'result' in catalog_result and not catalog_result['result'].get('isError'),'Catalog read failed'
    returned=catalog_result['result']
    products=returned.get('structuredContent',{}).get('products',[])
    assert isinstance(products,list) and len(products)==3,'Catalog returned an incomplete shortlist'
    ids=set(re.findall(r'invoice-lab-\d{3}',json.dumps(products)))
    assert {'invoice-lab-001','invoice-lab-050','invoice-lab-100'}<=ids,'Catalog read did not return the requested products'
    report={'label':'MEASURED_SANDBOX_OAUTH_MCP','origin':origin,'mcp_url':gateway,'public_anonymous_health_status':health_status,
        'unauthenticated_gateway_status':401,'tampered_signature_status':401,'guest_pkce_flow_verified':True,
        'gateway_accepts_signed_guest_token':True,'saved_card_identity_asserted':False,'protocol_version':version,
        'tools_count':len(tools),'tools':[{'name':t['name'],'read_only_hint':t.get('annotations',{}).get('readOnlyHint')} for t in tools],
        'merchant_tools_invoked':1,'read_only_catalog_tool':'render_products',
        'catalog_read_succeeded':True,'catalog_products_returned':len(products),
        'payment_operations':0,'model_calls':0,'visa_approved':False}
    save(directory/'merchant-oauth.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'VERIFICATION_STOPPED','failure_type':type(error).__name__,
            'reason':str(error) if isinstance(error,AssertionError) else 'Inspect local protocol checks; credentials are omitted',
            'payment_operations':0,'model_calls':0}))
        raise SystemExit(1) from None
