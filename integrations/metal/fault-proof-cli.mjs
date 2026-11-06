import { verifyFaultReceipt } from './fault-receipt.mjs';
import { DatabaseSync } from 'node:sqlite';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createClearingSigner, decodeSend } from '@metalntwx/metal-pay';
import { FAULT_NAMESPACE, faultRoot, verifyFaultSignature } from './fault-signature.mjs';

let input = '';
try {
  for await (const chunk of process.stdin) {
    input += chunk;
    if (input.length > 250000) throw Error('Proof too large');
  }
  const { packet, root, fault_signature: prior, sign_existing_wallet: walletScope,
    operator_key: operatorKey, check_network: checkNetwork } = JSON.parse(input);
  if (faultRoot(packet) !== root) throw Error('Fault commitment failed');
  if (checkNetwork && !process.env.METAL_RPC_URL) throw Error('Read-only RPC unavailable');
  const result = await verifyFaultReceipt(packet, { operatorKey, rpcUrl: checkNetwork ? process.env.METAL_RPC_URL : null });
  const payer = decodeSend(packet.payment.receipt.body).payer;
  if (prior && !verifyFaultSignature(packet, root, prior, payer)) throw Error('Fault signature failed');
  result.fault_signature_verified = Boolean(prior);
  if (walletScope) {
    if (!/^[A-Za-z0-9_-]{1,48}$/.test(walletScope)) throw Error('Invalid existing scope');
    const base = resolve(fileURLToPath(new URL('../..', import.meta.url)));
    const db = new DatabaseSync(resolve(base, 'data/metal', walletScope, 'wallet.sqlite'), { readOnly: true });
    try {
      const state = JSON.parse(db.prepare("SELECT value FROM settings WHERE key='sdk_state'").get().value);
      const original = state.payments[packet.payment.invoice.id];
      if (!original || original.receipt.body !== packet.payment.receipt.body ||
          original.receipt.operatorSignature !== packet.payment.receipt.operatorSignature) throw Error('Not this wallet invoice');
      const signer = createClearingSigner(db.prepare("SELECT value FROM settings WHERE key='private_key'").get().value);
      if (signer.publicKey !== payer) throw Error('Not the original payer');
      result.fault_signature = { signer: signer.publicKey, signature: signer.sign(FAULT_NAMESPACE, '0x'+root) };
      result.fault_signature_verified = true;
    } finally { db.close(); }
  }
  console.log(JSON.stringify({ ok: true, result }));
} catch {
  console.log(JSON.stringify({ ok: false, error: 'FAULT_PROOF_CRYPTOGRAPHIC_CHECK_FAILED', transactions_sent: 0 }));
  process.exitCode = 1;
}
