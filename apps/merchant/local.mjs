import { createServer } from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { randomBytes, webcrypto } from 'node:crypto';
import { handle, initialize } from './worker.mjs';

export function sqliteAdapter(database){
  return {exec:async query=>database.exec(query),prepare:query=>({bind:(...values)=>({
    first:async()=>database.prepare(query).get(...values)??null,
    run:async()=>{const result=database.prepare(query).run(...values);return {meta:{changes:Number(result.changes)}};},
  })})};
}

export async function configure(path){
  try{return JSON.parse(await readFile(path,'utf8'));}catch(error){if(error.code!=='ENOENT')throw error;}
  const pair=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',hash:'SHA-256',modulusLength:2048,publicExponent:new Uint8Array([1,0,1])},true,['sign','verify']);
  const key=await webcrypto.subtle.exportKey('jwk',pair.privateKey);key.kid='merchant-'+randomBytes(12).toString('hex');
  const config={PUBLIC_ORIGIN:'http://127.0.0.1:8094',ALLOW_LOCAL_HTTP:'1',
    CHECKOUT_HMAC_SECRET:randomBytes(32).toString('hex'),OAUTH_PRIVATE_JWK:JSON.stringify(key),
    OAUTH_RESOURCE:'',OAUTH_REDIRECT_URIS:''};
  await mkdir(dirname(path),{recursive:true});
  await writeFile(path,JSON.stringify(config,null,2)+'\n',{mode:0o600,flag:'wx'});
  return config;
}

if(process.argv[1]&&resolve(process.argv[1])===resolve(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1'))){
  const configPath=resolve(process.argv[2]||'data/merchant-service/config.json');
  const env=await configure(configPath),origin=new URL(env.PUBLIC_ORIGIN);
  const database=new DatabaseSync(resolve(dirname(configPath),'state.sqlite'));
  env.DB=sqliteAdapter(database);await initialize(env.DB);
  const port=Number(process.env.TOUCHSTONE_MERCHANT_PORT||8094);
  createServer(async(req,res)=>{
    try{
      if(req.headers.host!==origin.host){res.writeHead(403);res.end();return;}
      const chunks=[];let size=0;
      for await(const chunk of req){size+=chunk.length;if(size>32768){res.writeHead(413);res.end();return;}chunks.push(chunk);}
      const body=Buffer.concat(chunks);
      const request=new Request(origin.origin+req.url,{method:req.method,headers:req.headers,
        ...(!['GET','HEAD'].includes(req.method)?{body}:{} )});
      const response=await handle(request,env);
      res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
    }catch{res.writeHead(500);res.end('Merchant request unavailable');}
  }).listen(port,'127.0.0.1',()=>console.log(JSON.stringify({mode:'SANDBOX_ONLY',url:'http://127.0.0.1:'+port,bank_calls:0,model_calls:0,secrets_logged:false})));
}
