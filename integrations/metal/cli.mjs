import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { discover, connectJob, deposit, withdraw } from './adapter.mjs';
import { openWallet } from './wallet.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const args = process.argv.slice(2);
const [command = 'inspect', job = 'job-1', requestId] = args.filter(a => a !== '--execute');
if (!/^[A-Za-z0-9_-]{1,48}$/.test(job)) throw Error('Invalid job ID');
const config = { directory: resolve(root, 'data/metal', job), rpcUrl: process.env.METAL_RPC_URL,
  providerUrl: process.env.METAL_PROVIDER_URL, privateKey: process.env.AGENT_PRIVATE_KEY,
  maxPrice: process.env.METAL_MAX_PRICE_USD || '0.05', budget: process.env.METAL_JOB_BUDGET_USD || '0.50' };
try {
  if (['deposit', 'withdraw', 'pay', 'recover'].includes(command) && !args.includes('--execute')) throw Error('Explicit --execute and written spend approval required');
  let result;
  if (command === 'inspect') {
    result = { mode: 'READ_ONLY', sdk: '0.3.3', node: process.version, deployment: await discover(),
      configured: { rpc: !!config.rpcUrl, funding_key: !!config.privateKey, provider: !!config.providerUrl }, payments_sent: 0 };
  } else if (command === 'init') {
    const wallet = openWallet(config.directory);
    try { result = { mode: 'LOCAL_ONLY', job, public_key: wallet.signer.publicKey, payments_sent: 0 }; }
    finally { wallet.close(); }
  } else if (command === 'deposit') {
    result = await deposit(config, requestId || '0.10');
  } else if (command === 'withdraw') {
    result = await withdraw(config);
  } else if (command === 'pay' || command === 'recover') {
    if (command === 'pay') throw Error('APPROVAL_REQUIRED: prepare and sign an exact backend purchase; use the protected bridge');
    if (!requestId) throw Error('Supply a stable reservation ID as the third argument');
    const client = await connectJob(config);
    try { result = await (command === 'pay' ? client.buy(requestId) : client.recover(requestId)); }
    finally { client.close(); }
  } else { throw Error('Commands: inspect | init JOB | deposit JOB USD | pay JOB RESERVATION | recover JOB RESERVATION | withdraw JOB'); }
  console.log(JSON.stringify(result, (_, v) => typeof v === 'bigint' ? v.toString() : v, 2));
} catch (error) {
  // RPC URLs and key material can appear in upstream errors; emit only local, known messages.
  const message = String(error.message || 'Metal command failed');
  const redacted = [config.privateKey, config.rpcUrl, config.providerUrl].filter(Boolean).reduce((s, secret) => s.split(secret).join('[hidden]'), message);
  console.error('Touchstone Metal: ' + redacted);
  process.exitCode = 1;
}
