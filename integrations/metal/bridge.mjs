// One request per process: Python owns the job journal; the SDK owns payment state.
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { connectJob, deposit, withdraw } from './adapter.mjs';
import { openWallet } from './wallet.mjs';
import { clearingSpendable } from '@metalntwx/metal-pay';
import { createPublicClient, http, erc20Abi } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { USDZ } from '@metalntwx/metal-pay';
import { fail } from './procurement-approval.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
let input = '';
for await (const chunk of process.stdin) { input += chunk; if (input.length > 250000) throw Error('Request too large'); }
let request;
try {
  request = JSON.parse(input);
  if (['deposit', 'withdraw', 'pay', 'recover'].includes(request.command) && request.execute !== true) throw Error('Explicit execute required');
  if (request.command === 'pay' && !request.authorization) fail('APPROVAL_REQUIRED');
  if (!/^[A-Za-z0-9_-]{1,48}$/.test(request.job || '')) throw Error('Invalid job');
  const config = { directory: resolve(root, 'data/metal', request.job), rpcUrl: process.env.METAL_RPC_URL,
    providerUrl: request.provider_url, privateKey: process.env.AGENT_PRIVATE_KEY,
    nativeGasCapWei: request.native_gas_cap_wei,
    maxPrice: request.max_price, budget: request.budget };
  let result;
  if (request.command === 'funding-status') {
    const client = createPublicClient({ transport: http(config.rpcUrl, { retryCount: 0, timeout: 15000 }) });
    if (await client.getChainId() !== 63825) throw Error('Wrong chain');
    const account = privateKeyToAccount(config.privateKey);
    const [gas, tokens] = await Promise.all([client.getBalance({address: account.address}),
      client.readContract({address: USDZ.address, abi: erc20Abi, functionName: 'balanceOf', args: [account.address]})]);
    result = { mode: 'READ_ONLY', chain_id: 63825, address: account.address,
      native_balance_base_units: gas.toString(), usdz_balance_base_units: tokens.toString(), transactions_sent: 0 };
  } else if (request.command === 'inspect-purchase') {
    const wallet = openWallet(config.directory);
    try {
      const row = wallet.db.prepare('SELECT state,before_ids,result FROM purchases WHERE id=?').get(request.id);
      if (!row) throw Error('No original purchase');
      const state = await wallet.store.load();
      const before = JSON.parse(row.before_ids);
      const ids = Object.keys(state?.payments || {});
      // Pinned SDK durably writes pending before its first send, then clears
      // it only after a verified receipt or authoritative non-payment.
      const unpaid = !state?.pending && ids.length === before.length && ids.every(id => before.includes(id));
      result = { state: row.state, confirmed_nonpayment: unpaid,
        assurance: 'PINNED_SDK_LOCAL_PROTOCOL_STATE_NOT_EMPTY_REMOTE_LOOKUP',
        pending_invoice: Boolean(state?.pending), historical_payments: ids.length,
        new_receipt_ids: ids.filter(id => !before.includes(id)), transactions_sent: 0,
        inference_requests_sent: 0 };
    } finally { wallet.close(); }
  } else if (request.command === 'lookup') {
    const wallet = openWallet(config.directory);
    try {
      const row = wallet.db.prepare('SELECT state,result FROM purchases WHERE id=?').get(request.id);
      result = row ? { state: row.state, result: row.result ? JSON.parse(row.result) : null } : { state: 'NOT_DISPATCHED', result: null };
    } finally { wallet.close(); }
  } else if (request.command === 'receipts') {
    const wallet = openWallet(config.directory);
    try {
      result = wallet.db.prepare('SELECT id,terms,state,result FROM purchases ORDER BY rowid').all().map(row => {
        const purchase = row.result ? JSON.parse(row.result) : null;
        const receipt = purchase?.receipt;
        return { key: row.id, terms: JSON.parse(row.terms), state: row.state,
          receipt: receipt ? { id: receipt.id, invoice: { amount: receipt.invoice.amount } } : null };
      });
    } finally { wallet.close(); }
  } else if (request.command === 'deposit') result = await deposit(config, request.dollars);
  else if (request.command === 'withdraw') result = await withdraw(config);
  else {
    const client = await connectJob(config);
    try {
      if (request.command === 'quote') result = await client.quote();
      else if (request.command === 'pay') result = await client.buy(request.id, request.quote, request.authorization);
      else if (request.command === 'recover') result = await client.recover(request.id);
      else if (request.command === 'replay-delivery') result = await client.replayDelivery(request.id);
      else if (request.command === 'balance') {
        const state = await client.wallet.store.load();
        result = { account: client.wallet.signer.publicKey,
          spendable_base_units: (await clearingSpendable({ rpcUrl: config.rpcUrl, ...client.deployment, account: client.wallet.signer.publicKey })).toString(),
          historical_payments: Object.keys(state?.payments || {}).length, pending_invoice: !!state?.pending,
          assurance: 'operator-estimate', finalized: false };
      }
      else throw Error('Unsupported command');
    } finally { client.close(); }
  }
  console.log(JSON.stringify({ ok: true, result }, (_, v) => typeof v === 'bigint' ? v.toString() : v));
} catch (error) {
  // An upstream error can contain full URLs, signatures or key material.
  console.log(JSON.stringify({ ok: false, error: error.code && /^[A-Z_]+$/.test(error.code) ? error.code : 'METAL_OPERATION_UNRESOLVED', command: request?.command || null }));
  process.exitCode = 1;
}
