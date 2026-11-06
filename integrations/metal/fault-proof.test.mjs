import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { readFileSync,writeFileSync } from 'node:fs';
import { createClearingSigner, clearingRequirements, clearingInvoice, encodeSend, outgoingRoot,
  invoiceMessage, clearingPaymentId, USDZ } from '@metalntwx/metal-pay';
import { attestDelivery, verifyDelivery } from './delivery-proof.mjs';
import { faultRoot, FAULT_NAMESPACE, verifyFaultSignature } from './fault-signature.mjs';
import { verifyFaultReceipt } from './fault-receipt.mjs';
import { FaultReviewStore, verifyAcknowledgement } from './fault-review.mjs';
import { DeliveryStore } from './provider-core.mjs';

async function fixture({ unsigned = false } = {}) {
  const seller=createClearingSigner('0x'+'01'.repeat(32)), payer=createClearingSigner('0x'+'02'.repeat(32)), operator=createClearingSigner('0x'+'03'.repeat(32));
  const task={id:'fixture',kind:'arithmetic',source:{amounts_cents:[1250,275,499],discount_cents:24},min_quality:1};
  const bytes=Buffer.from(JSON.stringify(task));
  const resource='http://127.0.0.1:8092/inference/'+createHash('sha256').update(bytes).digest('hex')+'?task='+bytes.toString('base64url');
  const requirements=clearingRequirements({network:'eip155:63825',asset:USDZ.address,settlement:'0x'+'11'.repeat(20),recipient:seller.publicKey,serviceUrl:'https://example.test'},10000000000000000n,resource);
  const entries=[{recipient:seller.publicKey,cumulative:'10000',count:'1'}];
  const wire=encodeSend({anchor:'0x'+'00'.repeat(32),epoch:1n,payer:payer.publicKey,sequence:0n,debit:10000n,vector:outgoingRoot(entries.map(e=>({...e,cumulative:10000n,count:1n})))});
  const invoice=clearingInvoice(requirements,requirements.extra.invoicePrefix+':fixture');
  const payment={invoice,receipt:{body:wire,payerSignature:payer.sign('_COMMONWARE_CLEARING_VECTOR_SEND',wire),operatorSignature:operator.sign('_COMMONWARE_CLEARING_VECTOR_ACK',wire)},
    invoiceSignature:payer.sign('_METAL_CLEARING_INVOICE',invoiceMessage(invoice,wire)),entries};
  const output={total_cents:1250}, paymentId=clearingPaymentId(payment);
  const attestation=unsigned?null:await attestDelivery(seller,resource,paymentId,task,output);
  const body={task,output,payment,requirements,resource,delivery_attestation:attestation,
    counterexample:{error_code:'INVOICE_TOTAL_MISMATCH',claimed_total_minor:1250,recomputed_total_minor:2000,decision:'VERIFIED_FAIL'},
    created_at:new Date().toISOString(),nonce:'ab'.repeat(16),original_charge_base_units:invoice.amount};
  const proof={body,commitment:{root:faultRoot(body)}};
  proof.fault_signature={signer:payer.publicKey,signature:payer.sign(FAULT_NAMESPACE,'0x'+proof.commitment.root)};
  const db=new DatabaseSync(':memory:'), deliveries=new DeliveryStore(db), reviews=new FaultReviewStore(db,seller);
  const receiptDigest=createHash('sha256').update(wire+':'+payment.receipt.operatorSignature+':'+invoice.id).digest('hex');
  await deliveries.deliver(paymentId,resource,receiptDigest,async()=>({output,delivery_attestation:attestation}));
  return {proof,db,reviews,payer,seller,operator,paymentId, policy:{id:'integer-total-credit-v1',allow_credit_acknowledgement:true,maximum_credit_base_units:invoice.amount}};
}

test('provider signature binds task, answer, paid invoice and resource',async()=>{
  const f=await fixture();try {
    const b=f.proof.body;
    assert.equal(verifyDelivery(b.delivery_attestation,f.seller.publicKey,b.resource,f.paymentId,b.task,b.output),true);
    for (const mutate of [x=>x.output.total_cents++,x=>x.task.source.discount_cents++,x=>x.resource+='x']) {
      const altered=structuredClone(b); mutate(altered);
      assert.equal(verifyDelivery(altered.delivery_attestation,f.seller.publicKey,altered.resource,f.paymentId,altered.task,altered.output),false);
    }
  } finally {f.db.close();}
});

test('payment needs an independent operator trust anchor, with invoice/task binding enforced',async()=>{
  const f=await fixture();try {
    assert.equal((await verifyFaultReceipt(f.proof.body)).operator_signature_verified,false);
    assert.equal((await verifyFaultReceipt(f.proof.body,{operatorKey:f.operator.publicKey})).operator_signature_verified,true);
    await assert.rejects(verifyFaultReceipt(f.proof.body,{operatorKey:f.payer.publicKey}));
    const bad=structuredClone(f.proof.body);bad.payment.invoice.amount='2';
    await assert.rejects(verifyFaultReceipt(bad));
  } finally {f.db.close();}
});

test('provider independently reproduces the fault and signs credit acknowledgement, without a refund',async()=>{
  const f=await fixture();try {
    const ack=await f.reviews.review(f.proof,f.policy);
    assert.equal(ack.decision,'ACCEPTED');assert.equal(ack.refund_executed,false);
    assert.equal(ack.credit_status,'ACKNOWLEDGED_NOT_SETTLED');
    assert.equal(verifyAcknowledgement(ack,f.seller.publicKey,f.proof.commitment.root,f.proof.body.payment.invoice.id),true);
    assert.deepEqual(await f.reviews.review(f.proof,f.policy),ack);
    assert.equal(f.db.prepare('SELECT count(*) AS n FROM fault_reviews').get().n,1);
    if (process.env.TOUCHSTONE_CONTROLLED_FAULT_EVIDENCE) writeFileSync(process.env.TOUCHSTONE_CONTROLLED_FAULT_EVIDENCE,
      JSON.stringify({label:'MOCK',cryptography:'MEASURED',trust_anchor:'CONTROLLED_FIXTURE_OPERATOR_KEY',
        fault:f.proof,acknowledgement:ack,acknowledgement_signature_verified:true,refund_executed:false,
        original_charge_preserved:true,credits_settled:0},null,2)+'\n');
  } finally {f.db.close();}
});

test('unsigned historical answers and absent policies retain the original charge',async()=>{
  for (const unsigned of [false,true]) {
    const f=await fixture({unsigned});try {
      const ack=await f.reviews.review(f.proof,unsigned?f.policy:null);
      assert.equal(ack.decision,'REJECTED');assert.equal(ack.credit_base_units,'0');
      assert.equal(ack.original_charge_base_units,'10000000000000000');
    } finally {f.db.close();}
  }
});

test('forged arithmetic, stale faults, nonce reuse and repeated invoice credit are refused',async()=>{
  const f=await fixture();try {
    const resign=p=>{p.commitment.root=faultRoot(p.body);p.fault_signature.signature=f.payer.sign(FAULT_NAMESPACE,'0x'+p.commitment.root);};
    const fake=structuredClone(f.proof);fake.body.counterexample.recomputed_total_minor=123;resign(fake);
    assert.equal((await f.reviews.review(fake,f.policy)).decision,'REJECTED');
    await assert.rejects(f.reviews.review(f.proof,f.policy),/nonce/);
    const fresh=structuredClone(f.proof);fresh.body.nonce='cd'.repeat(16);resign(fresh);
    assert.equal((await f.reviews.review(fresh,f.policy)).decision,'ACCEPTED');
    const repeat=structuredClone(fresh);repeat.body.nonce='ef'.repeat(16);resign(repeat);
    assert.equal((await f.reviews.review(repeat,f.policy)).decision,'REJECTED');
    const old=structuredClone(fresh);old.body.nonce='00'.repeat(16);old.body.created_at='2020-01-01T00:00:00Z';resign(old);
    await assert.rejects(f.reviews.review(old,f.policy),/expired/);
  } finally {f.db.close();}
});

test('Python-created historical proof has the identical Merkle root and a valid buyer signature',async()=>{
  const proof=JSON.parse(readFileSync(new URL('../../bench/results/faults/metal-fault.json',import.meta.url)));
  assert.equal(faultRoot(proof.body),proof.commitment.root);
  const payer=proof.fault_signature.signer;
  assert.equal(verifyFaultSignature(proof.body,proof.commitment.root,proof.fault_signature,payer),true);
  const result=await verifyFaultReceipt(proof.body);
  assert.equal(result.payer_signature_verified,true);
  assert.equal(result.provider_output_signature_verified,false);
});
