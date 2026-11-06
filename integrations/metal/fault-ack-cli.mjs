import { verifyAcknowledgement } from './fault-review.mjs';

// Offline check of a provider's signed fault acknowledgement. No network, no wallet, no transaction.
let input = '';
try {
  for await (const chunk of process.stdin) {
    input += chunk;
    if (input.length > 20000) throw Error('Acknowledgement too large');
  }
  const { acknowledgement, seller, root, invoice_id: invoiceId } = JSON.parse(input);
  const valid = verifyAcknowledgement(acknowledgement, seller, root, invoiceId);
  console.log(JSON.stringify({ ok: true, result: { signature_valid: valid } }));
} catch {
  console.log(JSON.stringify({ ok: false, error: 'FAULT_ACK_CHECK_FAILED', transactions_sent: 0 }));
  process.exitCode = 1;
}
