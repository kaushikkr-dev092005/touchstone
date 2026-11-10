// Sandbox-only merchant callbacks and guest OAuth. No bank, model or payment dispatcher.
import productImage from './product-image.mjs';
const encoder = new TextEncoder();
const unbase64 = value => Uint8Array.from(atob(value.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));
const base64 = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');
const random = () => base64(crypto.getRandomValues(new Uint8Array(32)));
const digest = async value => base64(await crypto.subtle.digest('SHA-256',encoder.encode(value)));
const escape = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const json = (body,status=200,headers={}) => new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json','cache-control':'no-store',...headers}});
const html = (body,headers={}) => new Response('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Touchstone sandbox merchant</title><style>body{font:17px system-ui;max-width:900px;margin:50px auto;padding:20px;color:#162b2a;background:#f1f6f4}a{color:#156a5b}button{padding:14px 24px;background:#156a5b;color:white;border:0;border-radius:6px;font:inherit}li{margin:12px 0}small{color:#526662}</style>'+body+'</html>',{headers:{'content-type':'text/html; charset=utf-8','cache-control':'no-store','content-security-policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",...headers}});
const requireThat = (condition,message='Invalid request') => {if(!condition)throw new Error(message);};
const identifier = value => typeof value==='string' && /^[A-Za-z0-9_-]{1,100}$/.test(value);

export const catalog = Array.from({length:100},(_,index)=>({
  id:'invoice-lab-'+String(index+1).padStart(3,'0'),
  title:'Synthetic invoice practice set '+String(index+1).padStart(3,'0'),
  description:'Synthetic source documents for sandbox verification testing. No inference or real invoice payment.',
  unit_minor:1,stock:index<95?1:0,
}));

const SCHEMA = `CREATE TABLE IF NOT EXISTS merchant_clients(id TEXT PRIMARY KEY,body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS merchant_consents(id TEXT PRIMARY KEY,csrf_hash TEXT NOT NULL,body TEXT NOT NULL,expires INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS merchant_codes(hash TEXT PRIMARY KEY,body TEXT NOT NULL,expires INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS merchant_orders(id TEXT PRIMARY KEY,request_hash TEXT UNIQUE NOT NULL,body TEXT NOT NULL,created INTEGER NOT NULL);`;

export async function initialize(db){await db.exec(SCHEMA);}
async function row(db,query,...args){return db.prepare(query).bind(...args).first();}
async function run(db,query,...args){return db.prepare(query).bind(...args).run();}
function changed(result){return result.meta?.changes??result.changes??0;}

function originOf(env){
  const url=new URL(env.PUBLIC_ORIGIN);
  const local=['127.0.0.1','localhost'].includes(url.hostname);
  requireThat((url.protocol==='https:' || (env.ALLOW_LOCAL_HTTP==='1'&&local)) && !url.username && !url.password && url.pathname==='/' && !url.search && !url.hash,'Explicit merchant origin required');
  return url.origin;
}
function allowedRedirect(value,env){
  try{
    const url=new URL(value);
    if(url.username||url.password||url.hash)return false;
    if((env.OAUTH_REDIRECT_URIS||'').split(',').filter(Boolean).includes(value))return url.protocol==='https:';
    return url.protocol==='http:'&&['127.0.0.1','localhost','[::1]'].includes(url.hostname)&&Number(url.port)>=1024&&Number(url.port)<=65535;
  }catch{return false;}
}
async function bodyOf(request){
  requireThat(Number(request.headers.get('content-length')||0)<=32768,'Request too large');
  const reader=request.body?.getReader();if(!reader)return '';
  const chunks=[];let size=0;
  try{for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
    requireThat(size<=32768,'Request too large');chunks.push(value);}}
  finally{await reader.cancel();}
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
  return new TextDecoder('utf-8',{fatal:true}).decode(bytes);
}
function jwkOf(env){
  const key=JSON.parse(env.OAUTH_PRIVATE_JWK||'{}');
  requireThat(key.kty==='RSA'&&key.d&&key.kid&&unbase64(key.n).byteLength>=256,'RSA signing key unavailable');return key;
}
async function jwt(payload,env){
  const jwk=jwkOf(env);
  const input=base64(encoder.encode(JSON.stringify({alg:'RS256',kid:jwk.kid,typ:'JWT'})))+'.'+base64(encoder.encode(JSON.stringify(payload)));
  const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['sign']);
  return input+'.'+base64(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',key,encoder.encode(input)));
}
async function validSignature(request,body,secret,now){
  const time=request.headers.get('x-timestamp')||'',signature=request.headers.get('x-signature')||'';
  if(typeof secret!=='string'||secret.length<32||!/^\d{13}$/.test(time)||!Number.isSafeInteger(Number(time))||Math.abs(now-Number(time))>300000||!/^[a-fA-F0-9]{64}$/.test(signature))return false;
  const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['verify']);
  const bytes=Uint8Array.from(signature.match(/../g),v=>parseInt(v,16));
  return crypto.subtle.verify('HMAC',key,bytes,encoder.encode(time+body));
}

export async function handle(request,env,{now=Date.now()}={}){
  try{
    const origin=originOf(env),url=new URL(request.url),path=url.pathname,db=env.DB;
    requireThat(url.origin===origin,'Origin differs from configured merchant');
    if(path==='/health'&&request.method==='GET')return json({mode:'SANDBOX_ONLY',payment_dispatch:false,hosted_inference:false,catalog_products:catalog.length,oauth_ready:!!env.OAUTH_PRIVATE_JWK,checkout_secret_configured:!!env.CHECKOUT_HMAC_SECRET});
    if(path==='/.well-known/openid-configuration'&&request.method==='GET')return json({issuer:origin,authorization_endpoint:origin+'/oauth/authorize',token_endpoint:origin+'/oauth/token',registration_endpoint:origin+'/oauth/register',jwks_uri:origin+'/.well-known/jwks.json',response_types_supported:['code'],grant_types_supported:['authorization_code'],code_challenge_methods_supported:['S256'],token_endpoint_auth_methods_supported:['none'],scopes_supported:['openid','email'],subject_types_supported:['public'],id_token_signing_alg_values_supported:['RS256']});
    if(path==='/.well-known/jwks.json'&&request.method==='GET'){
      const key=jwkOf(env);return json({keys:[{kty:'RSA',kid:key.kid,n:key.n,e:key.e,alg:'RS256',use:'sig'}]});
    }
    if(path==='/'&&request.method==='GET')return html('<h1>Touchstone sandbox merchant</h1><p>Practice documents for testing source verification. Synthetic catalog; no model calls or real invoice payments.</p><p><a href="/catalog.json">Catalog data</a> · <a href="/.well-known/openid-configuration">OAuth discovery</a></p><ul>'+catalog.map(p=>'<li><a href="/products/'+p.id+'">'+escape(p.title)+'</a> · USD 0.01 · '+(p.stock?'Available':'Unavailable')+'</li>').join('')+'</ul>');
    if(path==='/catalog.json'&&request.method==='GET')return json({mode:'SYNTHETIC_SANDBOX',products:catalog.map(p=>({id:p.id,title:p.title,description:p.description,link:origin+'/products/'+p.id,image_link:origin+'/product-image.png',availability:p.stock?'in_stock':'out_of_stock',price:'0.01 USD',condition:'new'}))});
    if(path==='/product-image.png'&&request.method==='GET')return new Response(unbase64(productImage),{headers:{'content-type':'image/png','cache-control':'public,max-age=86400'}});
    if(path==='/product-image.svg'&&request.method==='GET')return new Response('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480" viewBox="0 0 480 480"><rect width="480" height="480" fill="#e6f3ee"/><rect x="110" y="60" width="260" height="360" rx="16" fill="white" stroke="#156a5b" stroke-width="8"/><path d="M155 140h170M155 200h170M155 260h120M155 320h80" stroke="#156a5b" stroke-width="12"/><text x="240" y="385" text-anchor="middle" font-family="sans-serif" font-size="22" fill="#156a5b">SYNTHETIC</text></svg>',{headers:{'content-type':'image/svg+xml','cache-control':'public,max-age=86400'}});
    if(path.startsWith('/products/')&&request.method==='GET'){
      const item=catalog.find(p=>p.id===path.split('/')[2]);if(!item)return json({error:'not_found'},404);
      return html('<h1>'+escape(item.title)+'</h1><p>'+escape(item.description)+'</p><p>USD 0.01 · '+(item.stock?'Available':'Unavailable')+'</p><p>Checkout is available through the configured Airwallex sandbox merchant connection. This page does not submit a payment.</p><a href="/">Catalog</a>');
    }
    if(path==='/oauth/register'&&request.method==='POST'){
      const input=JSON.parse(await bodyOf(request));
      requireThat(Array.isArray(input.redirect_uris)&&input.redirect_uris.length>0&&input.redirect_uris.length<=5&&input.redirect_uris.every(v=>allowedRedirect(v,env)),'Redirect URI not allowed');
      requireThat(!input.token_endpoint_auth_method||input.token_endpoint_auth_method==='none','Only public PKCE clients supported');
      const id=random(),body={redirect_uris:[...new Set(input.redirect_uris)],client_name:String(input.client_name||'Sandbox client').slice(0,100)};
      const created=await run(db,'INSERT INTO merchant_clients SELECT ?,? WHERE (SELECT COUNT(*) FROM merchant_clients)<1000',id,JSON.stringify(body));
      if(changed(created)!==1)return json({error:'registration_capacity_reached'},429);
      return json({client_id:id,client_id_issued_at:Math.floor(now/1000),...body,token_endpoint_auth_method:'none',grant_types:['authorization_code'],response_types:['code']},201);
    }
    if(path==='/oauth/authorize'&&request.method==='GET'){
      const q=url.searchParams,client=await row(db,'SELECT body FROM merchant_clients WHERE id=?',q.get('client_id'));
      requireThat(client,'Unknown client');const registered=JSON.parse(client.body);
      requireThat(q.get('response_type')==='code'&&registered.redirect_uris.includes(q.get('redirect_uri'))&&allowedRedirect(q.get('redirect_uri'),env),'Invalid authorization request');
      requireThat(q.get('code_challenge_method')==='S256'&&/^[A-Za-z0-9_-]{43}$/.test(q.get('code_challenge')||''),'PKCE S256 required');
      const scope=q.get('scope')||'openid';requireThat(scope.split(' ').every(s=>['openid','email'].includes(s)),'Unsupported scope');
      requireThat((q.get('state')||'').length<=1024&&(q.get('nonce')||'').length<=256,'Authorization metadata too large');
      requireThat(/^https:\/\/mcp\.sandbox\.airwallex\.com\/pa\/ai\/[A-Za-z0-9_-]+\/acp\/mcp$/.test(env.OAUTH_RESOURCE||''),'Sandbox merchant OAuth resource is not configured');
      if(q.get('resource'))requireThat(q.get('resource')===env.OAUTH_RESOURCE,'Unexpected OAuth resource');
      const id=random(),csrf=random(),body={client_id:q.get('client_id'),redirect_uri:q.get('redirect_uri'),challenge:q.get('code_challenge'),scope,state:q.get('state')||'',nonce:q.get('nonce')||'',resource:env.OAUTH_RESOURCE||''};
      await run(db,'DELETE FROM merchant_consents WHERE expires<=?',now);
      const created=await run(db,'INSERT INTO merchant_consents(id,csrf_hash,body,expires) SELECT ?,?,?,? WHERE (SELECT COUNT(*) FROM merchant_consents)<500',id,await digest(csrf),JSON.stringify(body),now+120000);
      if(changed(created)!==1)return json({error:'authorization_capacity_reached'},429);
      return html('<h1>Authorize sandbox catalog access</h1><p><strong>'+escape(registered.client_name)+'</strong> requests '+escape(scope)+' access.</p><p>This is a synthetic guest session. It does not identify a real shopper, access saved cards or authorize a payment.</p><form method="post" action="/oauth/consent"><input type="hidden" name="consent_id" value="'+id+'"><input type="hidden" name="csrf" value="'+csrf+'"><button name="decision" value="allow">Allow sandbox access</button> <button name="decision" value="deny">Decline</button></form>',{'set-cookie':'merchant_consent='+id+'; HttpOnly; SameSite=Lax; Path=/oauth; Max-Age=120'+(origin.startsWith('https:')?'; Secure':'')});
    }
    if(path==='/oauth/consent'&&request.method==='POST'){
      requireThat(request.headers.get('origin')===origin,'Consent origin mismatch');
      const input=new URLSearchParams(await bodyOf(request)),id=input.get('consent_id');
      requireThat((request.headers.get('cookie')||'').split(';').some(v=>v.trim()==='merchant_consent='+id),'Consent cookie mismatch');
      const pending=await row(db,'SELECT * FROM merchant_consents WHERE id=?',id);
      requireThat(pending&&pending.used===0&&pending.expires>now&&pending.csrf_hash===await digest(input.get('csrf')||''),'Invalid or expired consent');
      const consumed=await run(db,'UPDATE merchant_consents SET used=1 WHERE id=? AND used=0',id);requireThat(changed(consumed)===1,'Consent already used');
      const body=JSON.parse(pending.body),redirect=new URL(body.redirect_uri);
      if(body.state)redirect.searchParams.set('state',body.state);
      if(input.get('decision')!=='allow')redirect.searchParams.set('error','access_denied');
      else{
        const code=random();body.subject='synthetic-guest-'+random();
        await run(db,'DELETE FROM merchant_codes WHERE expires<=?',now);
        requireThat(changed(await run(db,'INSERT INTO merchant_codes(hash,body,expires) SELECT ?,?,? WHERE (SELECT COUNT(*) FROM merchant_codes)<1000',await digest(code),JSON.stringify(body),now+120000))===1,'Authorization capacity reached');
        redirect.searchParams.set('code',code);
      }
      return new Response(null,{status:302,headers:{location:redirect.href,'cache-control':'no-store','set-cookie':'merchant_consent=; HttpOnly; SameSite=Lax; Path=/oauth; Max-Age=0'+(origin.startsWith('https:')?'; Secure':'')}});
    }
    if(path==='/oauth/token'&&request.method==='POST'){
      const form=new URLSearchParams(await bodyOf(request));requireThat(form.get('grant_type')==='authorization_code','Unsupported grant');
      requireThat(/^[A-Za-z0-9._~-]{43,128}$/.test(form.get('code_verifier')||''),'Invalid PKCE verifier');
      const hash=await digest(form.get('code')||''),record=await row(db,'SELECT * FROM merchant_codes WHERE hash=?',hash);
      requireThat(record&&record.used===0&&record.expires>now,'Code invalid, expired or already used');
      const body=JSON.parse(record.body);
      requireThat(body.client_id===form.get('client_id')&&body.redirect_uri===form.get('redirect_uri')&&await digest(form.get('code_verifier'))===body.challenge,'Code binding mismatch');
      requireThat(env.OAUTH_RESOURCE&&body.resource===env.OAUTH_RESOURCE,'Merchant OAuth resource is not configured');
      requireThat(changed(await run(db,'UPDATE merchant_codes SET used=1 WHERE hash=? AND used=0',hash))===1,'Code already used');
      const nowSeconds=Math.floor(now/1000),claims={iss:origin,sub:body.subject,aud:env.OAUTH_RESOURCE,iat:nowSeconds,exp:nowSeconds+600,scope:body.scope};
      const result={access_token:await jwt(claims,env),token_type:'Bearer',expires_in:600,scope:body.scope};
      if(body.scope.split(' ').includes('openid'))result.id_token=await jwt({...claims,aud:body.client_id,...(body.nonce?{nonce:body.nonce}:{})},env);
      return json(result);
    }
    if(path==='/api/checkout'&&request.method==='POST'){
      const raw=await bodyOf(request);if(!await validSignature(request,raw,env.CHECKOUT_HMAC_SECRET,now))return json({error:'invalid_signature'},401);
      const input=JSON.parse(raw);requireThat(input.currency==='USD'&&Array.isArray(input.line_items)&&input.line_items.length===1,'Sandbox quote requires one USD line item');
      const item=input.line_items[0],product=catalog.find(p=>p.id===item.item_id);
      requireThat(identifier(item.id)&&product&&item.requested_quantity===1,'Unknown product or quantity');
      const requestHash=await digest(request.headers.get('x-timestamp')+raw),prior=await row(db,'SELECT body FROM merchant_orders WHERE request_hash=?',requestHash);
      if(prior)return json(JSON.parse(prior.body));
      const id='order_'+random(),amount=product.stock?product.unit_minor:0;
      const result={id,line_items:[{id:item.id,item_id:product.id,requested_quantity:1,available_quantity:product.stock}],totals:[{type:'subtotal',amount,display_text:'Subtotal'},{type:'total',amount,display_text:'Total'}],permalink_url:origin+'/orders/'+id};
      await run(db,'INSERT OR IGNORE INTO merchant_orders SELECT ?,?,?,? WHERE (SELECT COUNT(*) FROM merchant_orders)<1000',id,requestHash,JSON.stringify(result),now);
      const saved=await row(db,'SELECT body FROM merchant_orders WHERE request_hash=?',requestHash);
      if(!saved)return json({error:'quote_capacity_reached'},429);
      return json(JSON.parse(saved.body));
    }
    if(path.startsWith('/orders/')&&request.method==='GET'){
      const saved=await row(db,'SELECT body FROM merchant_orders WHERE id=?',path.split('/')[2]);if(!saved)return json({error:'not_found'},404);
      const order=JSON.parse(saved.body);return html('<h1>Sandbox checkout quote</h1><p>Order '+escape(order.id)+'</p><p>Total: USD '+(order.totals.at(-1).amount/100).toFixed(2)+'</p><p>Payment has not been independently verified. A quote does not confirm a purchase, receipt of funds or fulfillment.</p>');
    }
    return json({error:'not_found'},404);
  }catch{return json({error:'request_refused'},400);}
}

const initialized=new WeakSet();
export default {async fetch(request,env){
  if(!initialized.has(env.DB)){await initialize(env.DB);initialized.add(env.DB);}
  return handle(request,env);
}};
