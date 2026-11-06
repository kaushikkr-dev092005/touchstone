// A real local signed-HTTP exchange with controlled identities, not Visa credentials.
import { createServer } from 'node:http';
import { generateKeyPairSync, randomBytes, createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { TapMerchant, signIntent } from './tap.mjs';

const { publicKey,privateKey }=generateKeyPairSync('ed25519');
const now=Math.floor(Date.now()/1000), db=new DatabaseSync(':memory:');
const publicPem=publicKey.export({type:'spki',format:'pem'});
const merchant=new TapMerchant(db,new Map([['controlled-agent',{public_key:publicPem,expires_at:now+600,trust_source:'CONTROLLED_LOCAL_KEY'}]]));
const server=createServer(async(req,res)=>{
  try {
    let body='';for await (const chunk of req){body+=chunk;if(body.length>4096)throw Error('Too large');}
    const value=merchant.verify({authority:req.headers.host,path:req.url,method:req.method,headers:req.headers,body});
    res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(value));
  } catch {res.writeHead(403,{'Content-Type':'application/json'});res.end(JSON.stringify({label:'BLOCKED',payments_sent:0}));}
});
try {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const authority='127.0.0.1:'+server.address().port, path='/tap/intent';
  const body=JSON.stringify({job_id:'controlled-job',intent:'purchase',currency:'USD',amount_minor:1});
  const headers=signIntent({authority,path,body,keyId:'controlled-agent',privateKey,nonce:randomBytes(24).toString('base64url'),created:now,expires:now+120});
  const first=await fetch('http://'+authority+path,{method:'POST',headers,body,redirect:'error'});
  const result=await first.json();
  const replay=await fetch('http://'+authority+path,{method:'POST',headers,body,redirect:'error'});
  if (first.status!==200 || replay.status!==403) throw Error('Controlled TAP probe failed');
  console.log(JSON.stringify({...result,merchant_http_status:first.status,replay_http_status:replay.status,
    controlled_public_key_sha256:createHash('sha256').update(publicPem).digest('hex'),
    request_sha256:createHash('sha256').update(body).digest('hex'),visa_integration_status:'BLOCKED_VISA_CREDENTIALS_NOT_CONFIGURED'}));
} finally {await new Promise(resolve=>server.close(resolve));db.close();}
