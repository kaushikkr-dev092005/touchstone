// Human authorization is intentionally separate from payer/fault/TAP signing.
import { readFileSync, realpathSync } from 'node:fs';
import { resolve, basename } from 'node:path';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { recoverTypedDataAddress, verifyTypedData, hashTypedData } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';

const root = new URL('../..', import.meta.url);
export const schema = JSON.parse(readFileSync(new URL('./procurement-schema.json', import.meta.url), 'utf8'));
export const fail = code => { throw Object.assign(Error(code), {code}); };
const ascii = s => JSON.stringify(s).replace(/[\u007f-\uffff]/g, c => '\\u'+c.charCodeAt(0).toString(16).padStart(4,'0'));
function decimal(n) {
  if (!Number.isFinite(n) || Math.abs(n)>Number.MAX_SAFE_INTEGER) fail('MALFORMED_APPROVAL');
  let s=String(n);
  if (s.includes('e')) {
    const [mantissa,exp]=s.split('e'), negative=mantissa.startsWith('-');
    const m=negative?mantissa.slice(1):mantissa, [a,b='']=m.split('.'), digits=a+b, point=a.length+Number(exp);
    s=(negative?'-':'')+(point<=0?'0.'+'0'.repeat(-point)+digits:point>=digits.length?digits+'0'.repeat(point-digits.length):digits.slice(0,point)+'.'+digits.slice(point));
  }
  if (s.length>100) fail('MALFORMED_APPROVAL');
  return s;
}
export function canonical(value) {
  const tree=v=>{
    if (v===null) return ['null'];
    if (typeof v==='boolean') return ['bool',v];
    if (typeof v==='number') return ['number',decimal(v)];
    if (typeof v==='string') {
      if ([...v].some(c=>{const n=c.codePointAt(0);return n>=0xd800&&n<=0xdfff;})) fail('MALFORMED_APPROVAL');
      return ['string',v];
    }
    if (Array.isArray(v)) return ['array',v.map(tree)];
    if (v && Object.getPrototypeOf(v)===Object.prototype) {
      const order=(a,b)=>{const x=Array.from(a,c=>c.codePointAt(0)),y=Array.from(b,c=>c.codePointAt(0));for(let i=0;i<Math.min(x.length,y.length);i++) if(x[i]!==y[i])return x[i]-y[i];return x.length-y.length;};
      return ['object',Object.keys(v).sort(order).map(k=>[tree(k),tree(v[k])])];
    }
    fail('MALFORMED_APPROVAL');
  };
  return ascii(tree(value));
}
export const digest = value => '0x'+createHash('sha256').update(canonical(value),'ascii').digest('hex');
export function config() {
  let c;
  try { c=JSON.parse(readFileSync(process.env.TOUCHSTONE_APPROVAL_CONFIG || new URL('./data/private/procurement-approvers.json',root),'utf8')); }
  catch { fail('APPROVER_NOT_CONFIGURED'); }
  const keys=['environment','chain_id','salt','signers','agent_addresses','ledger_paths','api_credit_max'];
  if (Object.keys(c).sort().join()!=keys.sort().join() || !Number.isSafeInteger(c.chain_id)||c.chain_id<=0 ||
      !/^[A-Za-z0-9_.:-]{1,80}$/.test(c.environment)||!/^0x[0-9a-f]{64}$/.test(c.salt)||
      !Array.isArray(c.signers)||!c.signers.length||!Array.isArray(c.agent_addresses)||!c.agent_addresses.length||!Array.isArray(c.ledger_paths)||
      ![...c.signers,...c.agent_addresses].every(x=>/^0x[0-9a-fA-F]{40}$/.test(x))||
      !c.ledger_paths.every(x=>typeof x==='string')||!Number.isSafeInteger(c.api_credit_max)||c.api_credit_max<0) fail('APPROVER_NOT_CONFIGURED');
  return c;
}
export function typedData(terms,c) {
  if (!terms || Object.keys(terms).sort().join()!=Object.keys(schema).sort().join()) fail('MALFORMED_APPROVAL');
  for (const [k,type] of Object.entries(schema)) {
    const v=terms[k];
    if (type==='uint256' ? !Number.isSafeInteger(v)||v<0 : typeof v!=='string'||!v.length||v.length>2048) fail('MALFORMED_APPROVAL');
    if (type==='bytes32'&&!/^0x[0-9a-f]{64}$/.test(v)) fail('MALFORMED_APPROVAL');
  }
  return {domain:{name:'Touchstone',version:'1',chainId:c.chain_id,salt:c.salt},primaryType:'ProcurementApproval',
    types:{ProcurementApproval:Object.entries(schema).map(([name,type])=>({name,type}))},message:terms};
}
export async function verifyApproval(terms,signature,expectedSigner,c=config()) {
  const data=typedData(terms,c), now=Math.floor(Date.now()/1000);
  if (terms.protocol_version!=='1'||terms.purpose!=='PREMIUM_INFERENCE_PURCHASE'||terms.environment!==c.environment||terms.network!==`eip155:${c.chain_id}`) fail('TERMS_MISMATCH');
  if (terms.expires_at<=now||terms.issued_at>now+5||terms.expires_at<=terms.issued_at||terms.expires_at-terms.issued_at>300) fail('APPROVAL_EXPIRED');
  if (terms.quote_expires_ms<=Date.now()) fail('QUOTE_EXPIRED');
  if (typeof signature!=='string'||!/^0x[0-9a-fA-F]{130}$/.test(signature)) fail('INVALID_SIGNATURE');
  let address;
  try { address=(await recoverTypedDataAddress({...data,signature})).toLowerCase(); }
  catch { fail('INVALID_SIGNATURE'); }
  const agents=c.agent_addresses.map(a=>a.toLowerCase());
  if (process.env.AGENT_PRIVATE_KEY) {
    try { agents.push(privateKeyToAccount(process.env.AGENT_PRIVATE_KEY).address.toLowerCase()); }
    catch { fail('APPROVER_NOT_CONFIGURED'); }
  }
  if (agents.includes(address)) fail('AGENT_SIGNER_FORBIDDEN');
  if (!c.signers.some(a=>a.toLowerCase()===address)||address!==expectedSigner?.toLowerCase()) fail('SIGNER_UNTRUSTED');
  if (!await verifyTypedData({...data,address,signature})) fail('INVALID_SIGNATURE');
  return {signer:address,typed_data_hash:hashTypedData(data),terms_digest:digest(terms),verified_at:now,scheme:'EIP712_EOA'};
}

// Read only an operator-allowlisted authority database. Caller-supplied terms or
// approved=true cannot replace the exact consumed backend record.
export async function dispatchApproval(wallet,id,q,authorization,cfg) {
  if (!authorization || Object.keys(authorization).sort().join()!==['approval_id','ledger_path','purchase_key','dispatch_token'].sort().join()) fail('APPROVAL_REQUIRED');
  const c=config();
  if (c.chain_id!==63825) fail('TERMS_MISMATCH');
  let path;
  try { path=realpathSync(authorization.ledger_path); }
  catch { fail('APPROVAL_LEDGER_UNTRUSTED'); }
  const identity=p=>process.platform==='win32'?resolve(p).toLowerCase():resolve(p);
  if (!c.ledger_paths.some(p=>identity(p)===identity(path))) fail('APPROVAL_LEDGER_UNTRUSTED');
  const db=new DatabaseSync(path,{readOnly:true});
  let row;
  try {
    row=db.prepare('SELECT * FROM procurement_approvals WHERE id=?').get(authorization.approval_id);
    if (!row) fail('APPROVAL_REQUIRED');
    if(typeof authorization.dispatch_token!=='string'||!/^[0-9a-f]{64}$/.test(authorization.dispatch_token)||
      createHash('sha256').update(authorization.dispatch_token,'ascii').digest('hex')!==row.dispatch_token_hash) fail('APPROVAL_REQUIRED');
    if (row.state==='REVOKED') fail('APPROVAL_REVOKED');
    if (row.state!=='CONSUMED_AT_DISPATCH'||row.consuming_key!==id||row.purchase_key!==id||authorization.purchase_key!==id) fail('APPROVAL_REQUIRED');
    const terms=JSON.parse(row.terms);
    if (row.digest!==digest(terms)) fail('TERMS_MISMATCH');
    await verifyApproval(terms,row.signature,row.expected_signer,c);
    if (terms.payer_scope!==basename(cfg.directory)||terms.purchase_key!==id||terms.currency!=='USDZ'||
        terms.allocation_currency!=='USDZ'||terms.provider_id!==q.provider_id||terms.provider_origin!==new URL(q.url).origin||
        terms.quote_expires_ms!==q.expires_at||BigInt(terms.quoted_amount)*10n**12n!==BigInt(q.offer.amount)||
        BigInt(terms.max_amount)*10n**12n!==cfg.maximum||BigInt(terms.allocation)*10n**12n!==cfg.budget) fail('TERMS_MISMATCH');
    const attempt=db.prepare('SELECT * FROM attempts WHERE key=?').get(id);
    let publicQuote;
    if (attempt) {
      publicQuote=JSON.parse(attempt.quote);
      const job=db.prepare('SELECT * FROM jobs WHERE id=?').get(attempt.job_id);
      if(attempt.worker_token) {
        const lease=db.prepare('SELECT * FROM worker_leases WHERE job_id=?').get(attempt.job_id);
        if(!lease?.active||lease.token!==attempt.worker_token)fail('WORKER_NOT_OWNED');
      }
      if(attempt.state!=='DISPATCHING'||job.mandate_version!==terms.mandate_version||job.budget!==terms.job_ceiling||
         job.price_cap!==terms.max_amount||job.allocation!==terms.allocation||job.spent!==terms.spent||job.rail_spent!==terms.rail_spent) fail('TERMS_MISMATCH');
    } else {
      const banked=db.prepare('SELECT * FROM banked_jobs WHERE scope=?').get(terms.job_id);
      if (!banked) fail('APPROVAL_REQUIRED');
      const state=JSON.parse(banked.state);
      if(state.phase!=='PAYMENT_DISPATCHING'||state.reservation!==id) fail('APPROVAL_REQUIRED');
      publicQuote=state.quote;
    }
    if (digest(publicQuote)!==terms.quote_digest||digest(publicQuote.terms)!==digest(q)||publicQuote.id!==terms.quote_id) fail('TERMS_MISMATCH');
    wallet.db.exec('CREATE TABLE IF NOT EXISTS human_dispatches(nonce TEXT PRIMARY KEY,approval_id TEXT UNIQUE NOT NULL,purchase_key TEXT UNIQUE NOT NULL,digest TEXT NOT NULL)');
    if(wallet.db.prepare('SELECT 1 FROM human_dispatches WHERE nonce=? OR purchase_key=? OR approval_id=?').get(terms.nonce,id,row.id)) fail('APPROVAL_ALREADY_CONSUMED');
    // Wallet owner lock spans this durable consume and the SDK purchase. A crash
    // before SDK pending is fail-closed; recover never buys a fresh request.
    wallet.db.prepare('INSERT INTO human_dispatches VALUES(?,?,?,?)').run(terms.nonce,row.id,id,row.digest);
    return terms;
  } finally { db.close(); }
}
