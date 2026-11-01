import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { clearingRequirements, clearingPaymentOf, verifyClearingPayment, clearingPaymentId } from '@metalntwx/metal-pay';
import { decodePaymentSignatureHeader, encodePaymentRequiredHeader } from '@x402/core/http';
import { discover, amount } from './adapter.mjs';
import { openWallet } from './wallet.mjs';
import { decodeResource, DeliveryStore, priceForQueue, qualityDropOutput } from './provider-core.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const port = Number(process.env.TOUCHSTONE_PROVIDER_PORT || '8092');
const origin = `http://127.0.0.1:${port}`;
const mode = process.env.TOUCHSTONE_PROVIDER_MODE || 'model';
const chaos = process.env.TOUCHSTONE_PROVIDER_CHAOS || 'none';
if (!Number.isInteger(port) || port < 1024 || port > 65535 || !['model','tool'].includes(mode) ||
    !['none','outage','quality-drop'].includes(chaos)) throw Error('Invalid provider settings');
if (!process.env.METAL_RPC_URL) throw Error('Configure Metal RPC first');
const deployment = await discover();
const wallet = openWallet(resolve(root, 'data/metal/local-provider'));
wallet.bindDeployment(deployment);
const store = new DeliveryStore(wallet.db);
const price = amount(process.env.TOUCHSTONE_PROVIDER_PRICE_USD || '0.01');
if (price <= 0n || price > amount('0.05')) throw Error('Provider test price must be in (0, 0.05] USD');
const basePriceMicroUsd = price / 10n ** 12n;
const maxPriceMicroUsd = amount('0.05') / 10n ** 12n;
let queueDepth = 0;
let deliveryTail = Promise.resolve();
const serviceSamples = [];

function averageServiceMs() {
  return serviceSamples.length ? Math.round(serviceSamples.reduce((sum, value) => sum + value, 0) / serviceSamples.length) : 1000;
}

function runQueued(work) {
  queueDepth++;
  const delivery = deliveryTail.then(async () => {
    const started = performance.now();
    try { return await work(); }
    finally {
      serviceSamples.push(Math.max(1, Math.round(performance.now() - started)));
      if (serviceSamples.length > 50) serviceSamples.shift();
    }
  });
  deliveryTail = delivery.catch(() => {});
  return delivery.finally(() => { queueDepth--; });
}

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
  if (chaos === 'outage') return send(response, 503, { error: 'Injected provider outage; no quote is available' });
  if (request.url === '/health') return send(response, 200, { mode: 'TESTNET_PROVIDER', provider_type: mode,
    inference_ready: await modelReady(), chain: 63825, paid_delivery: 'UNVERIFIED', chaos,
    queue_depth: queueDepth, queue_capacity: 1, seller_public_key: wallet.signer.publicKey,
    base_price_micro_usd: basePriceMicroUsd.toString(),
    current_quote_base_units: priceForQueue(basePriceMicroUsd, queueDepth, maxPriceMicroUsd).toString() });
  try {
    const { task } = decodeResource(request.url);
    const resource = origin + request.url;
    if (!request.headers['payment-signature']) {
      if (!await modelReady()) return send(response, 503, { error: 'Local model is not ready; no quote offered' });
      const quotedQueueDepth = queueDepth;
      const latencyMs = averageServiceMs() * (quotedQueueDepth + 1);
      const offer = clearingRequirements({ ...deployment, recipient: wallet.signer.publicKey },
        priceForQueue(basePriceMicroUsd, quotedQueueDepth, maxPriceMicroUsd), resource);
      const expiresAt = Date.now() + 30000;
      store.rememberQuote(resource, offer, expiresAt, quotedQueueDepth, latencyMs);
      const packet = { x402Version: 2, resource: { url: resource, mimeType: 'application/json' }, accepts: [offer] };
      return send(response, 402, { error: 'Payment required', provider_type: mode, queue_depth: quotedQueueDepth },
        { 'PAYMENT-REQUIRED': encodePaymentRequiredHeader(packet), 'X-Touchstone-Queue-Depth': String(quotedQueueDepth),
          'X-Touchstone-Latency-Ms': String(latencyMs) });
    }
    const paymentPacket = decodePaymentSignatureHeader(request.headers['payment-signature']);
    const quote = store.findQuote(resource, paymentPacket.accepted);
    if (!quote) return send(response, 503, { error: 'Quote is missing or expired; preserve and recover the original receipt' });
    const paid = clearingPaymentOf(paymentPacket);
    if (!paid) return send(response, 403, { error: 'Invalid payment proof' });
    await verifyClearingPayment(paid, quote.offer, { rpcUrl: process.env.METAL_RPC_URL, ...deployment });
    const id = clearingPaymentId(paid);
    const receiptDigest = createHash('sha256').update(paid.receipt.body + ':' + paid.receipt.operatorSignature + ':' + paid.invoice.id).digest('hex');
    const result = await runQueued(() => store.deliver(id, resource, receiptDigest, async () => {
      if (!await modelReady()) throw Error('Local model unavailable after payment; retain the original receipt and retry delivery');
      const output = await worker(task);
      return chaos === 'quality-drop' ? qualityDropOutput(task, output) : output;
    }));
    return send(response, 200, result);
  } catch { return send(response, 503, { error: 'Delivery unconfirmed; retain and replay the original receipt without another payment' }); }
});
server.listen(port, '127.0.0.1', () => console.log(JSON.stringify({ url: origin, mode: 'TESTNET_PROVIDER', provider_type: mode, chaos })));
function close() { server.close(() => { wallet.close(); process.exit(0); }); }
process.on('SIGINT', close); process.on('SIGTERM', close);
