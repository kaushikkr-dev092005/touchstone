import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { clearingRequirements, clearingPaymentOf, verifyClearingPayment, clearingPaymentId } from '@metalntwx/metal-pay';
import { decodePaymentSignatureHeader, encodePaymentRequiredHeader } from '@x402/core/http';
import { discover, amount } from './adapter.mjs';
import { openWallet } from './wallet.mjs';
import { decodeResource, DeliveryStore } from './provider-core.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const port = Number(process.env.TOUCHSTONE_PROVIDER_PORT || '8092');
const origin = `http://127.0.0.1:${port}`;
const mode = process.env.TOUCHSTONE_PROVIDER_MODE || 'model';
if (!Number.isInteger(port) || port < 1024 || port > 65535 || !['model','tool'].includes(mode)) throw Error('Invalid provider settings');
if (!process.env.METAL_RPC_URL) throw Error('Configure Metal RPC first');
const deployment = await discover();
const wallet = openWallet(resolve(root, 'data/metal/local-provider'));
wallet.bindDeployment(deployment);
const store = new DeliveryStore(wallet.db);
const price = amount(process.env.TOUCHSTONE_PROVIDER_PRICE_USD || '0.01');
if (price <= 0n || price > amount('0.05')) throw Error('Provider test price must be in (0, 0.05] USD');
let busy = false;

async function modelReady() {
  if (mode === 'tool') return true;
  const url = new URL(process.env.LOCAL_INFERENCE_URL || 'http://127.0.0.1:8080/v1/chat/completions');
  if (url.protocol !== 'http:' || !['127.0.0.1','localhost','[::1]'].includes(url.hostname)) return false;
  try { return (await fetch(new URL('/health', url), { redirect: 'error', signal: AbortSignal.timeout(2000) })).ok; }
  catch { return false; }
}

function worker(task) {
  return new Promise((resolveResult, reject) => {
    const workerEnv = { ...process.env };
    delete workerEnv.METAL_RPC_URL;
    delete workerEnv.AGENT_PRIVATE_KEY;
    for (const key of Object.keys(workerEnv)) if (key.startsWith('AIRWALLEX_')) delete workerEnv[key];
    const processWorker = spawn(process.env.TOUCHSTONE_PYTHON || 'python', ['-m', 'touchstone.provider_worker'],
      { cwd: root, stdio: ['pipe','pipe','pipe'], windowsHide: true, env: workerEnv });
    let output = '';
    const timer = setTimeout(() => { processWorker.kill(); reject(Error('Worker timeout')); }, 95000);
    processWorker.stdout.on('data', b => { output += b; if (output.length > 1000000) processWorker.kill(); });
    processWorker.stderr.resume();
    processWorker.on('error', () => { clearTimeout(timer); reject(Error('Worker failed')); });
    processWorker.on('close', code => { clearTimeout(timer); if (code) reject(Error('Worker failed')); else {
      try { resolveResult(JSON.parse(output)); } catch { reject(Error('Invalid worker output')); }
    } });
    processWorker.stdin.end(JSON.stringify({ mode, task }));
  });
}

function send(response, status, body, headers = {}) {
  const bytes = Buffer.from(JSON.stringify(body));
  response.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': bytes.length,
    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...headers });
  response.end(bytes);
}

const server = createServer({ maxHeaderSize: 65536 }, async (request, response) => {
  if (request.headers.host !== `127.0.0.1:${port}` || request.method !== 'GET') return send(response, 403, { error: 'Loopback GET required' });
  if (request.url === '/health') return send(response, 200, { mode: 'TESTNET_PROVIDER', provider_type: mode,
    inference_ready: await modelReady(), chain: 63825, paid_delivery: 'UNVERIFIED',
    seller_public_key: wallet.signer.publicKey, price_base_units: price.toString() });
  try {
    const { task } = decodeResource(request.url);
    if (!await modelReady()) return send(response, 503, { error: 'Local model is not ready; no quote offered' });
    const resource = origin + request.url;
    const offer = clearingRequirements({ ...deployment, recipient: wallet.signer.publicKey }, price, resource);
    const packet = { x402Version: 2, resource: { url: resource, mimeType: 'application/json' }, accepts: [offer] };
    if (!request.headers['payment-signature']) return send(response, 402, { error: 'Payment required', provider_type: mode },
      { 'PAYMENT-REQUIRED': encodePaymentRequiredHeader(packet) });
    if (busy) return send(response, 503, { error: 'Provider busy; replay the original paid receipt later' });
    busy = true;
    try {
      const packet = decodePaymentSignatureHeader(request.headers['payment-signature']);
      const paid = clearingPaymentOf(packet);
      if (!paid) return send(response, 403, { error: 'Invalid payment proof' });
      await verifyClearingPayment(paid, offer, { rpcUrl: process.env.METAL_RPC_URL, ...deployment });
      const id = clearingPaymentId(paid);
      const receiptDigest = createHash('sha256').update(paid.receipt.body + ':' + paid.receipt.operatorSignature + ':' + paid.invoice.id).digest('hex');
      const result = await store.deliver(id, resource, receiptDigest, () => worker(task));
      return send(response, 200, result);
    } finally { busy = false; }
  } catch { return send(response, 503, { error: 'Delivery unconfirmed; retain and replay the original receipt without another payment' }); }
});
server.listen(port, '127.0.0.1', () => console.log(JSON.stringify({ url: origin, mode: 'TESTNET_PROVIDER', provider_type: mode })));
function close() { server.close(() => { wallet.close(); process.exit(0); }); }
process.on('SIGINT', close); process.on('SIGTERM', close);
