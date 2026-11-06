import { createHash } from 'node:crypto';
import { createPublicClient, http } from 'viem';
import { clearingAbi, clearingPaymentId, clearingPaymentMismatch, clearingPaymentOf, decodeSend,
  verifyClearingSignature, verifyClearingPayment, verifyReceipt, USDZ } from '@metalntwx/metal-pay';
import { decodeResource } from './provider-core.mjs';
import { verifyDelivery, stableJson } from './delivery-proof.mjs';
import { discover } from './adapter.mjs';

export async function verifyFaultReceipt(packet, options = {}) {
  const { payment, requirements, resource, task, output, delivery_attestation: attestation } = packet;
  const decoded = decodeResource(new URL(resource).pathname + new URL(resource).search);
  if (stableJson(decoded.task) !== stableJson(task) || requirements.extra.invoicePrefix !==
      '0x' + createHash('sha256').update(resource).digest('hex')) throw Error('Task/resource binding failed');
  if (requirements.network !== 'eip155:63825' || requirements.asset.toLowerCase() !== USDZ.address.toLowerCase() ||
      !clearingPaymentOf({ payload: payment }) || clearingPaymentMismatch(payment, requirements)) throw Error('Invoice binding failed');
  const send = decodeSend(payment.receipt.body);
  if (!verifyClearingSignature(send.payer, '_COMMONWARE_CLEARING_VECTOR_SEND', payment.receipt.body,
      payment.receipt.payerSignature)) throw Error('Payer signature failed');
  let operatorKey = options.operatorKey, anchor = operatorKey ? 'OPERATOR_KEY_SUPPLIED_BY_VERIFIER' : 'UNANCHORED';
  if (options.rpcUrl) {
    const trusted=await discover();
    if (payment.invoice.settlement.toLowerCase()!==trusted.settlement.toLowerCase() ||
        requirements.extra.serviceUrl.replace(/\/$/,'')!==trusted.serviceUrl) throw Error('Untrusted clearing service/deployment');
    const client = createPublicClient({ transport: http(options.rpcUrl, { retryCount: 0, timeout: 15000 }) });
    if (await client.getChainId() !== 63825) throw Error('Wrong chain');
    const context = await client.readContract({ address: payment.invoice.settlement, abi: clearingAbi,
      functionName: 'contextOf', args: [send.epoch] });
    if (operatorKey && operatorKey !== context.operatorKey) throw Error('Operator trust anchor mismatch');
    operatorKey = context.operatorKey;
    await verifyClearingPayment(payment, requirements, { rpcUrl: options.rpcUrl,
      settlement: payment.invoice.settlement, serviceUrl: requirements.extra.serviceUrl });
    anchor = 'READ_ONLY_ONCHAIN_CONTEXT_AND_OPERATOR_JOURNAL';
  }
  if (operatorKey && !verifyReceipt(payment.receipt, operatorKey)) throw Error('Operator signature failed');
  const attributed = Boolean(attestation && verifyDelivery(attestation, requirements.payTo, resource,
    clearingPaymentId(payment), task, output));
  if (attestation && !attributed) throw Error('Delivery signature failed');
  return { payer_signature_verified: true, invoice_and_task_bound: true,
    operator_signature_verified: Boolean(operatorKey), trust_anchor: anchor,
    operator_public_key: operatorKey || null, provider_output_signature_verified: attributed,
    provider_output_attribution: attributed ? 'SIGNED_BY_INVOICE_RECIPIENT' : 'UNSIGNED_HISTORICAL_DELIVERY',
    receipt_status: 'preconfirmed', final_settlement_verified: false, transactions_sent: 0 };
}
