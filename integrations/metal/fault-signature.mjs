import { createHash } from 'node:crypto';
import { verifyClearingSignature } from '@metalntwx/metal-pay';
import { stableJson } from './delivery-proof.mjs';

export const FAULT_NAMESPACE = '_TOUCHSTONE_FAULT_V1';
export function faultRoot(body) {
  let level = Object.keys(body).sort().map(name => createHash('sha256').update(Buffer.concat([
    Buffer.from([0]), Buffer.from(stableJson([name, body[name]]))])).digest());
  if (!level.length) throw Error('Empty fault');
  while (level.length > 1) {
    if (level.length % 2) level.push(level.at(-1));
    const next = [];
    for (let i=0; i<level.length; i+=2) next.push(createHash('sha256').update(Buffer.concat([
      Buffer.from([1]), level[i], level[i+1]])).digest());
    level = next;
  }
  return level[0].toString('hex');
}

export function verifyFaultSignature(body, root, attestation, payer) {
  return /^[0-9a-f]{64}$/.test(root) && faultRoot(body) === root && attestation?.signer === payer &&
    verifyClearingSignature(payer, FAULT_NAMESPACE, '0x'+root, attestation.signature);
}
