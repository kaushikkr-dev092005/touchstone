import { createHash } from 'node:crypto';
import { clearingPaymentId, decodeSend, verifyClearingSignature } from '@metalntwx/metal-pay';
import { stableJson, verifyDelivery } from './delivery-proof.mjs';
import { faultRoot, verifyFaultSignature } from './fault-signature.mjs';
import { verifyFaultReceipt } from './fault-receipt.mjs';

const ACK_NAMESPACE = '_TOUCHSTONE_FAULT_ACK_V1';
export class FaultReviewStore {
  constructor(db, signer) {
    this.db = db; this.signer = signer;
    db.exec(`CREATE TABLE IF NOT EXISTS fault_reviews(root TEXT PRIMARY KEY, nonce TEXT UNIQUE NOT NULL,
      invoice TEXT NOT NULL, decision TEXT NOT NULL, acknowledgement TEXT NOT NULL);
      CREATE UNIQUE INDEX IF NOT EXISTS one_fault_credit_per_invoice ON fault_reviews(invoice) WHERE decision='ACCEPTED';`);
  }
  async review(proof, policy = null, now = Date.now()) {
    const body = proof.body, root = faultRoot(body), payer = decodeSend(body.payment.receipt.body).payer;
    if (root !== proof.commitment.root || !verifyFaultSignature(body, root, proof.fault_signature, payer)) throw Error('Invalid signed fault');
    if (body.requirements.payTo !== this.signer.publicKey || body.original_charge_base_units !== body.payment.invoice.amount) throw Error('Not this provider/charge');
    await verifyFaultReceipt(body);
    const cached = this.db.prepare('SELECT acknowledgement FROM fault_reviews WHERE root=?').get(root);
    if (cached) return JSON.parse(cached.acknowledgement);
    if (this.db.prepare('SELECT 1 FROM fault_reviews WHERE nonce=?').get(body.nonce)) throw Error('Fault nonce already consumed');
    const age = now - Date.parse(body.created_at);
    if (!Number.isFinite(age) || age < -30000 || age > 24*3600000) throw Error('Fault receipt expired');
    const paymentId = clearingPaymentId(body.payment);
    const original = this.db.prepare('SELECT resource,receipt_digest,state,output FROM deliveries WHERE payment_id=?').get(paymentId);
    const receiptDigest = createHash('sha256').update(body.payment.receipt.body + ':' + body.payment.receipt.operatorSignature + ':' + body.payment.invoice.id).digest('hex');
    let reason = 'No original authenticated delivery', credit = '0';
    if (original?.state === 'DELIVERED' && original.resource === body.resource && original.receipt_digest === receiptDigest) {
      const delivered = JSON.parse(original.output);
      if (stableJson(delivered.output) !== stableJson(body.output) || !verifyDelivery(delivered.delivery_attestation,
          this.signer.publicKey, body.resource, paymentId, body.task, body.output)) reason = 'Output lacks the original provider signature';
      else if (!numericFault(body)) reason = 'Counterexample does not reproduce against the original task';
      else if (!policy || policy.id !== 'integer-total-credit-v1' || !policy.allow_credit_acknowledgement) reason = 'Refund/credit policy does not authorize a credit';
      else if (this.db.prepare("SELECT 1 FROM fault_reviews WHERE invoice=? AND decision='ACCEPTED'").get(body.payment.invoice.id)) reason = 'Credit already acknowledged for this invoice';
      else if (BigInt(body.payment.invoice.amount) > BigInt(policy.maximum_credit_base_units)) reason = 'Policy credit cap exceeded';
      else { credit = body.payment.invoice.amount; reason = 'Provider reproduced the integer total fault; credit acknowledged only'; }
    }
    const ack = { version: 1, fault_root: root, invoice_id: body.payment.invoice.id,
      decision: credit === '0' ? 'REJECTED' : 'ACCEPTED', reason, credit_base_units: credit,
      credit_status: credit === '0' ? 'NONE' : 'ACKNOWLEDGED_NOT_SETTLED',
      original_charge_base_units: body.payment.invoice.amount, refund_executed: false,
      created_at: new Date(now).toISOString(), signer: this.signer.publicKey };
    const signature = await this.signer.sign(ACK_NAMESPACE, '0x'+createHash('sha256').update(stableJson(ack)).digest('hex'));
    const signed = { ...ack, signature };
    this.db.prepare('INSERT INTO fault_reviews VALUES(?,?,?,?,?)').run(root, body.nonce, body.payment.invoice.id,
      ack.decision, JSON.stringify(signed));
    return signed;
  }
}

export function verifyAcknowledgement(ack, seller, root, invoiceId) {
  try {
    const { signature, ...body } = ack;
    return body.signer === seller && body.fault_root === root && body.invoice_id === invoiceId &&
      body.refund_executed === false && ['ACCEPTED','REJECTED'].includes(body.decision) &&
      verifyClearingSignature(seller, ACK_NAMESPACE, '0x'+createHash('sha256').update(stableJson(body)).digest('hex'), signature);
  } catch { return false; }
}

function numericFault(body) {
  const task = body.task, s = task.source, c = body.counterexample;
  if (task.min_quality!==undefined && (!Number.isFinite(task.min_quality)||task.min_quality<0||task.min_quality>1)) return false;
  let total = null;
  if (task.kind === 'arithmetic' && Object.keys(s).sort().join(',')==='amounts_cents,discount_cents' && Array.isArray(s.amounts_cents) && s.amounts_cents.length >= 1 && s.amounts_cents.length <= 1000 &&
      s.amounts_cents.every(x => Number.isSafeInteger(x) && x >= 0 && x <= 1e12) && Number.isSafeInteger(s.discount_cents)) {
    const sum = s.amounts_cents.reduce((a,b)=>a+b,0);
    if (sum <= 1e12 && s.discount_cents >= 0 && s.discount_cents <= sum) total = sum-s.discount_cents;
  } else if (task.kind === 'invoice' && Object.keys(s).join(',')==='text' && typeof s.text === 'string') {
    const m = /^Invoice (INV-[A-Za-z0-9-]{1,64})\. Currency USD\. Quantity ([0-9]{1,6})\. Unit price ([0-9]{1,12}) cents\. Tax ([0-9]{1,12}) cents\.$/.exec(s.text);
    if (m && Number(m[2]) >= 1) { const value = Number(m[2])*Number(m[3])+Number(m[4]); if (Number.isSafeInteger(value) && value <= 1e12) total=value; }
  }
  return total !== null && c.error_code === 'INVOICE_TOTAL_MISMATCH' && c.decision === 'VERIFIED_FAIL' &&
    Number.isSafeInteger(body.output.total_cents) && body.output.total_cents !== total &&
    c.claimed_total_minor === body.output.total_cents && c.recomputed_total_minor === total;
}
