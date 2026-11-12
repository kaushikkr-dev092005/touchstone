// Read the existing deployment's current admission context. Never signs or sends a transaction.
import { DatabaseSync } from 'node:sqlite';
import { createPublicClient, http } from 'viem';
import { clearingAbi } from '@metalntwx/metal-pay';
import { resolve } from 'node:path';
const scope=process.argv[2];
if(!/^[A-Za-z0-9_-]{1,36}$/.test(scope||''))throw Error('Existing scope required');
const db=new DatabaseSync(resolve('data/metal',scope,'wallet.sqlite'),{readOnly:true});
const d=JSON.parse(db.prepare("SELECT value FROM settings WHERE key='deployment'").get().value);db.close();
const client=createPublicClient({transport:http(process.env.METAL_RPC_URL,{retryCount:0,timeout:15000})});
const response=await fetch(d.serviceUrl.replace(/\/$/,'')+'/context',{redirect:'error',signal:AbortSignal.timeout(15000)});
let result={label:'MEASURED',http_status:response.status,ready:false,financial_transactions:0,inference_requests:0};
if(response.ok){
 const c=await response.json();
 const [registered,admitted,fault,context,block]=await Promise.all([
  ...['registered','admittedCount','fault'].map(functionName=>client.readContract({address:d.settlement,abi:clearingAbi,functionName})),
  client.readContract({address:d.settlement,abi:clearingAbi,functionName:'contextOf',args:[BigInt(c.epoch)]}),client.getBlock()]);
 const matches=c.anchor===context.anchor&&c.operator===context.operatorKey;
 result={...result,epoch:c.epoch,context_matches_chain:matches,seconds_before_admission_deadline:Number(context.admissionDeadline-block.timestamp),
  ready:registered&&admitted===BigInt(c.epoch)&&block.timestamp<context.admissionDeadline&&!fault&&matches};
}
console.log(JSON.stringify(result));
