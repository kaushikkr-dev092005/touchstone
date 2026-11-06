import { createHash } from 'node:crypto';
import { stringToHex } from 'viem';
import { verifyClearingSignature } from '@metalntwx/metal-pay';

const NAMESPACE = '_TOUCHSTONE_DELIVERY_V1';
export function stableJson(value) {
  if (Array.isArray(value)) return '[' + value.map(stableJson).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort((a,b) => Buffer.compare(Buffer.from(a), Buffer.from(b))).map(k => JSON.stringify(k) + ':' + stableJson(value[k])).join(',') + '}';
  return JSON.stringify(value);
}
const hash = value => createHash('sha256').update(stableJson(value)).digest('hex');

function statement(resource, paymentId, task, output) {
  return { version: 1, resource, payment_id: paymentId, task_sha256: hash(task), output_sha256: hash(output) };
}

export async function attestDelivery(signer, resource, paymentId, task, output) {
  const body = statement(resource, paymentId, task, output);
  return { ...body, signer: signer.publicKey, signature: await signer.sign(NAMESPACE, stringToHex(stableJson(body))) };
}

export function verifyDelivery(attestation, seller, resource, paymentId, task, output) {
  try {
    if (!attestation || attestation.signer !== seller) return false;
    const expected = statement(resource, paymentId, task, output);
    if (Object.keys(attestation).sort().join(',') !== [...Object.keys(expected), 'signer', 'signature'].sort().join(',')) return false;
    if (!Object.entries(expected).every(([key, value]) => attestation[key] === value)) return false;
    return verifyClearingSignature(seller, NAMESPACE, stringToHex(stableJson(expected)), attestation.signature);
  } catch { return false; }
}
