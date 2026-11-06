import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { TapMerchant,signIntent } from './tap.mjs';

function fixture() {
  const keys=generateKeyPairSync('ed25519'),db=new DatabaseSync(':memory:');
  const publicKey=keys.publicKey.export({type:'spki',format:'pem'});
  const merchant=new TapMerchant(db,new Map([['agent',{public_key:publicKey,expires_at:1000,trust_source:'CONTROLLED_LOCAL_KEY'}]]));
  const request={authority:'127.0.0.1:9000',path:'/tap/intent',method:'POST',body:JSON.stringify({job_id:'job',intent:'purchase',currency:'USD',amount_minor:1})};
  request.headers=signIntent({...request,keyId:'agent',privateKey:keys.privateKey,nonce:'controlled_nonce_0123456',created:100,expires:200});
  return {db,merchant,request,keys};
}

test('controlled merchant verifies intent and refuses durable nonce replay',()=>{
  const f=fixture();try {
    const result=f.merchant.verify(f.request,101);
    assert.equal(result.signature_verified,true);assert.equal(result.visa_approved_agent,false);
    assert.equal(result.payments_sent,0);
    assert.throws(()=>new TapMerchant(f.db,f.merchant.keys).verify(f.request,102),/replay/);
  } finally{f.db.close();}
});

test('method, authority, body, intent, timestamps and key substitution cannot bypass the signature',()=>{
  const changes=[r=>r.authority='evil.test',r=>r.path='/tap/intent?amount=2',r=>r.method='GET',
    r=>r.body=r.body.replace('"amount_minor":1','"amount_minor":2'),
    r=>r.headers['signature-input']=r.headers['signature-input'].replace('expires=200','expires=999'),
    r=>r.headers['signature-input']=r.headers['signature-input'].replace('keyid="agent"','keyid="unknown"')];
  for(const mutate of changes){const f=fixture();try{mutate(f.request);assert.throws(()=>f.merchant.verify(f.request,101));}finally{f.db.close();}}
  const f=fixture();try{assert.throws(()=>f.merchant.verify(f.request,201),/Expired/);}finally{f.db.close();}
});

import { keysFromJwks } from './tap.mjs';
test('a key directory (JWKS) yields time-limited Ed25519 keys and still never claims Visa approval',()=>{
  const keys=generateKeyPairSync('ed25519'), jwk={...keys.publicKey.export({format:'jwk'}),kid:'directory-agent',use:'sig'};
  const rsa=generateKeyPairSync('rsa',{modulusLength:2048}).publicKey.export({format:'jwk'});
  const trusted=keysFromJwks({keys:[jwk,{...rsa,kid:'rsa'},{...jwk,kid:'bad kid'},{kty:'OKP',crv:'Ed25519',kid:'broken',x:'!!'}]},100,600);
  assert.deepEqual([...trusted.keys()],['directory-agent']);
  assert.equal(trusted.get('directory-agent').trust_source,'KEY_DIRECTORY');assert.equal(trusted.get('directory-agent').expires_at,700);
  const db=new DatabaseSync(':memory:'),merchant=new TapMerchant(db,trusted);
  const request={authority:'127.0.0.1:9000',path:'/tap/intent',method:'POST',body:JSON.stringify({job_id:'job',intent:'purchase',currency:'USD',amount_minor:1})};
  request.headers=signIntent({...request,keyId:'directory-agent',privateKey:keys.privateKey,nonce:'directory_nonce_0123456',created:100,expires:200});
  const result=merchant.verify(request,101);
  assert.equal(result.identity_trust,'KEY_DIRECTORY');assert.equal(result.visa_approved_agent,false);
  assert.throws(()=>new TapMerchant(new DatabaseSync(':memory:'),trusted).verify(request,701),/Expired|locally trusted/);
  assert.throws(()=>keysFromJwks({keys:'x'}),/Invalid/);
  db.close();
});
