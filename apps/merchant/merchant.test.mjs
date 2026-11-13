import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { webcrypto,createHmac,createPublicKey,verify } from 'node:crypto';
import { handle,initialize } from './worker.mjs';
import { sqliteAdapter } from './local.mjs';

const origin='https://merchant.test',now=1794330000000;
const pair=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',hash:'SHA-256',modulusLength:2048,publicExponent:new Uint8Array([1,0,1])},true,['sign','verify']);
const key=await webcrypto.subtle.exportKey('jwk',pair.privateKey);key.kid='fixture-key';
async function fixture(t){const database=new DatabaseSync(':memory:');t.after(()=>database.close());
  const env={DB:sqliteAdapter(database),PUBLIC_ORIGIN:origin,OAUTH_PRIVATE_JWK:JSON.stringify(key),CHECKOUT_HMAC_SECRET:'fixture-only-'.repeat(4),OAUTH_RESOURCE:'https://mcp.sandbox.airwallex.com/pa/ai/fixture/acp/mcp'};
  await initialize(env.DB);return {env,database,call:(path,options={})=>handle(new Request(origin+path,options),env,{now})};}

test('discovery and JWKS contain public signing fields, not private material',async t=>{
  const {call}=await fixture(t),discovery=await (await call('/.well-known/openid-configuration')).json();
  assert.equal((await (await call('/api/merchant-health')).json()).payment_dispatch,false);
  assert.equal(discovery.issuer,origin);assert.deepEqual(discovery.code_challenge_methods_supported,['S256']);
  const jwks=await (await call('/.well-known/jwks.json')).json();assert.equal(jwks.keys[0].alg,'RS256');
  for(const name of ['d','p','q','dp','dq','qi'])assert.equal(jwks.keys[0][name],undefined);
  const products=(await (await call('/catalog.json')).json()).products;
  assert.equal(products.length,100);assert.equal(new Set(products.map(p=>p.id)).size,100);
  const image=await call('/product-image.png');assert.equal(image.headers.get('content-type'),'image/png');
  assert.deepEqual([...new Uint8Array(await image.arrayBuffer()).slice(0,8)],[137,80,78,71,13,10,26,10]);
});

test('public website context cannot dispatch the private operator API',async t=>{
  const {call}=await fixture(t);
  const context=await (await call('/api/site-context')).json();
  assert.equal(context.operator_console,false);assert.equal(context.financial_dispatch,false);
  for(const path of ['/api/demo','/api/resume','/console',
    '/api/procurement/prepare-approval','/api/procurement/submit-signature',
    '/api/procurement/revoke-approval','/api/procurement/dispatch-mock'])assert.equal((await call(path,{method:'POST',body:'{}'})).status,404);
  assert.equal((await call('/api/procurement/approvals')).status,404);
  assert.equal((await call('/merchant')).status,200);
});
test('dynamic registration refuses arbitrary remote redirect and implicit clients',async t=>{
  const {call}=await fixture(t);
  const response=await call('/oauth/register',{method:'POST',body:JSON.stringify({redirect_uris:['https://attacker.test/callback']})});
  assert.equal(response.status,400);
  const accepted=await call('/oauth/register',{method:'POST',body:JSON.stringify({redirect_uris:['http://127.0.0.1:3334/callback'],client_name:'Test client'})});assert.equal(accepted.status,201);
});
async function authorization(t){
  const f=await fixture(t),redirect='http://127.0.0.1:3334/callback',verifier='v'.repeat(43);
  const client=await (await f.call('/oauth/register',{method:'POST',body:JSON.stringify({redirect_uris:[redirect],client_name:'Test <script>client</script>'})})).json();
  const challenge=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))).toString('base64url');
  const query=new URLSearchParams({response_type:'code',client_id:client.client_id,redirect_uri:redirect,code_challenge:challenge,code_challenge_method:'S256',scope:'openid email',state:'bound-state',resource:f.env.OAUTH_RESOURCE});
  const consent=await f.call('/oauth/authorize?'+query),body=await consent.text();
  assert.ok(!body.includes('<script>client</script>'));
  const id=/name="consent_id" value="([^"]+)"/.exec(body)[1],csrf=/name="csrf" value="([^"]+)"/.exec(body)[1];
  return {...f,client,redirect,verifier,id,csrf,consentPost:{method:'POST',headers:{origin,cookie:'merchant_consent='+id},body:new URLSearchParams({consent_id:id,csrf,decision:'allow'})}};
}
test('consent is bound to origin and cookie and cannot be replayed',async t=>{
  const f=await authorization(t);
  assert.equal((await f.call('/oauth/consent',{...f.consentPost,headers:{origin:'https://attacker.test',cookie:'merchant_consent='+f.id}})).status,400);
  const result=await f.call('/oauth/consent',f.consentPost);assert.equal(result.status,302);
  assert.equal(new URL(result.headers.get('location')).searchParams.get('state'),'bound-state');
  assert.equal((await f.call('/oauth/consent',f.consentPost)).status,400);
});
test('PKCE code redemption signs a guest JWT once without saved-card identity',async t=>{
  const f=await authorization(t),consent=await f.call('/oauth/consent',f.consentPost),code=new URL(consent.headers.get('location')).searchParams.get('code');
  const form=new URLSearchParams({grant_type:'authorization_code',client_id:f.client.client_id,redirect_uri:f.redirect,code,code_verifier:'w'.repeat(43)});
  assert.equal((await f.call('/oauth/token',{method:'POST',body:form})).status,400);
  form.set('code_verifier',f.verifier);
  const response=await f.call('/oauth/token',{method:'POST',body:form});assert.equal(response.status,200);
  const result=await response.json(),parts=result.access_token.split('.'),claims=JSON.parse(Buffer.from(parts[1],'base64url'));
  assert.equal(claims.aud,f.env.OAUTH_RESOURCE);assert.equal(claims.awx_customer_id,undefined);assert.equal(claims.exp-claims.iat,600);
  const publicKey=createPublicKey({key:{kty:key.kty,n:key.n,e:key.e},format:'jwk'});
  assert.equal(verify('RSA-SHA256',Buffer.from(parts[0]+'.'+parts[1]),publicKey,Buffer.from(parts[2],'base64url')),true);
  assert.equal((await f.call('/oauth/token',{method:'POST',body:form})).status,400);
});
test('checkout requires HMAC over raw bytes and fresh milliseconds, never dispatches payment',async t=>{
  const {call,env,database}=await fixture(t),body=JSON.stringify({currency:'USD',line_items:[{id:'li_1',item_id:'invoice-lab-001',requested_quantity:1}]});
  const headers={'x-timestamp':String(now),'x-signature':createHmac('sha256',env.CHECKOUT_HMAC_SECRET).update(String(now)+body).digest('hex')};
  assert.equal((await call('/api/checkout',{method:'POST',body})).status,401);
  const first=await (await call('/api/checkout',{method:'POST',headers,body})).json();assert.equal(first.totals.at(-1).amount,1);
  const replay=await (await call('/api/checkout',{method:'POST',headers,body})).json();assert.equal(replay.id,first.id);
  assert.equal(database.prepare('SELECT COUNT(*) n FROM merchant_orders').get().n,1);
  assert.equal((await call('/api/checkout',{method:'POST',headers,body:body+' '})).status,401);
  assert.equal((await handle(new Request(origin+'/api/checkout',{method:'POST',headers,body}),env,{now:now+300001})).status,401);
  assert.match(await (await call('/orders/'+first.id)).text(),/Payment has not been independently verified/);
});
test('unknown products and excessive quantities are refused; unavailable stock is explicit',async t=>{
  const {call,env}=await fixture(t);
  for(const [item,quantity,status] of [['unknown',1,400],['invoice-lab-001',2,400],['invoice-lab-100',1,200]]){
    const body=JSON.stringify({currency:'USD',line_items:[{id:'li_1',item_id:item,requested_quantity:quantity}]});
    const headers={'x-timestamp':String(now),'x-signature':createHmac('sha256',env.CHECKOUT_HMAC_SECRET).update(String(now)+body).digest('hex')};
    const response=await call('/api/checkout',{method:'POST',headers,body});assert.equal(response.status,status);
    if(status===200)assert.equal((await response.json()).line_items[0].available_quantity,0);
  }
});

test('unconfigured or production OAuth resource cannot initiate guest authorization',async t=>{
  const f=await authorization(t);
  for(const resource of ['',f.env.OAUTH_RESOURCE.replace('mcp.sandbox.','mcp.')]){
    f.env.OAUTH_RESOURCE=resource;
    assert.equal((await f.call('/oauth/authorize?'+new URLSearchParams({response_type:'code',client_id:f.client.client_id,redirect_uri:f.redirect,code_challenge:'x'.repeat(43),code_challenge_method:'S256'}))).status,400);
  }
});

test('public registration has a durable capacity cap and streamed bodies are bounded',async t=>{
  const {call,database}=await fixture(t);
  const insert=database.prepare('INSERT INTO merchant_clients VALUES(?,?)');
  for(let i=0;i<1000;i++)insert.run('existing-'+i,'{}');
  const response=await call('/oauth/register',{method:'POST',body:JSON.stringify({redirect_uris:['http://127.0.0.1:3334/callback']})});
  assert.equal(response.status,429);
  assert.equal(database.prepare('SELECT COUNT(*) n FROM merchant_clients').get().n,1000);
  assert.equal((await call('/oauth/register',{method:'POST',body:' '.repeat(32769)})).status,400);
});
