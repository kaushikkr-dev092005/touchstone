import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { clearingRequirements, clearingPaymentOf, verifyClearingPayment, clearingPaymentId } from '@metalntwx/metal-pay';
import { decodePaymentSignatureHeader, encodePaymentRequiredHeader } from '@x402/core/http';
import { discover, amount } from './adapter.mjs';
import { openWallet } from './wallet.mjs';
import { decodeResource, DeliveryStore, priceForQueue, qualityDropOutput } from './provider-core.mjs';
import { scenario } from './m4-chaos.mjs';

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const port = Number(process.env.TOUCHSTONE_PROVIDER_PORT || '8092');
const origin = `http://127.0.0.1:${port}`;
const mode = process.env.TOUCHSTONE_PROVIDER_MODE || 'model';
const providerId = process.env.TOUCHSTONE_PROVIDER_ID || (mode === 'anthropic' ? 'hosted-premium' : 'metal-provider');
const chaos = process.env.TOUCHSTONE_PROVIDER_CHAOS || 'none';
const schedule = process.env.TOUCHSTONE_PROVIDER_SCENARIO_FILE ? scenario(readFileSync(process.env.TOUCHSTONE_PROVIDER_SCENARIO_FILE, 'utf8')) : null;
if (!Number.isInteger(port) || port < 1024 || port > 65535 || !['model','tool','anthropic'].includes(mode) ||
    !['metal-provider','local-gpu','hosted-premium'].includes(providerId) ||
    !['none','outage','quality-drop'].includes(chaos)) throw Error('Invalid provider settings');
if (!process.env.METAL_RPC_URL) throw Error('Configure Metal RPC first');
const deployment = await discover();
const walletDirectory = providerId === 'metal-provider' ? 'local-provider' : `provider-${providerId}`;
const wallet = openWallet(resolve(root, 'data/metal', walletDirectory));
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
  if (mode === 'anthropic') return Boolean(process.env.ANTHROPIC_API_KEY?.trim() &&
    (process.env.ANTHROPIC_MODEL || 'claude-sonnet-5').trim());
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
    if (mode !== 'anthropic') delete workerEnv.ANTHROPIC_API_KEY;
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
    upstream_funding: mode === 'anthropic' && process.env.TOUCHSTONE_HOSTED_FUNDING_SOURCE === 'PARTNER_CREDITS' ? 'PARTNER_CREDITS_OPERATOR_DECLARED' : 'UNVERIFIED',
    inference_ready: await modelReady(), chain: 63825, paid_delivery: 'UNVERIFIED', chaos,
    chaos_schedule_sha256: schedule?.sha256 || null,
    readiness_basis: mode === 'anthropic' ? 'api_key_and_model_configured_only' : 'local_health_check_or_tool_mode',
    provider_id: providerId,
    provider_model: mode === 'anthropic' ? (process.env.ANTHROPIC_MODEL || 'claude-sonnet-5') : mode === 'model' ? (process.env.LOCAL_MODEL || 'local-model') : null,
    provider_model_sha256: mode === 'model' ? (process.env.LOCAL_MODEL_SHA256 || null) : null,
    queue_depth: queueDepth, queue_capacity: 1, latency_samples: serviceSamples.length,
    latency_source: serviceSamples.length ? 'completed_provider_deliveries' : 'default_before_first_delivery',
    seller_public_key: wallet.signer.publicKey,
    base_price_micro_usd: basePriceMicroUsd.toString(),
    current_quote_base_units: priceForQueue(basePriceMicroUsd, queueDepth, maxPriceMicroUsd).toString() });
  try {
    const { task } = decodeResource(request.url);
    const taskChaos = schedule?.fault(task.id, providerId) || chaos;
    if (taskChaos === 'outage' && !request.headers['payment-signature']) return send(response, 503,
      { error: 'Scheduled provider outage; no quote or payment requested' },
      { 'X-Touchstone-Fault': 'outage', 'X-Touchstone-Scenario-SHA256': schedule.sha256 });
    const resource = origin + request.url;
    if (!request.headers['payment-signature']) {
      if (!await modelReady()) return send(response, 503, { error: 'Inference provider is not configured or ready; no quote offered' });
      const quotedQueueDepth = queueDepth;
      const latencyMs = averageServiceMs() * (quotedQueueDepth + 1);
      const offer = clearingRequirements({ ...deployment, recipient: wallet.signer.publicKey },
        priceForQueue(basePriceMicroUsd, quotedQueueDepth, maxPriceMicroUsd), resource);
      const expiresAt = Date.now() + 30000;
      store.rememberQuote(resource, offer, expiresAt, quotedQueueDepth, latencyMs);
      const packet = { x402Version: 2, resource: { url: resource, mimeType: 'application/json' }, accepts: [offer] };
      return send(response, 402, { error: 'Payment required', provider_type: mode, queue_depth: quotedQueueDepth },
        { 'PAYMENT-REQUIRED': encodePaymentRequiredHeader(packet), 'X-Touchstone-Queue-Depth': String(quotedQueueDepth),
          'X-Touchstone-Latency-Ms': String(latencyMs),
          'X-Touchstone-Latency-Samples': String(serviceSamples.length),
          'X-Touchstone-Provider': providerId });
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
      if (!await modelReady()) throw Error('Inference provider unavailable after payment; retain and recover the original receipt');
      const output = await worker(task);
      return taskChaos === 'quality-drop' ? { ...output, output: qualityDropOutput(task, output.output),
        provider_metadata: { ...output.provider_metadata, chaos_mode: taskChaos } } : output;
    }), { retryRunning: mode !== 'anthropic' });
    return send(response, 200, result);
  } catch { return send(response, 503, { error: 'Delivery unconfirmed; retain and replay the original receipt without another payment' }); }
});
server.listen(port, '127.0.0.1', () => console.log(JSON.stringify({ url: origin, mode: 'TESTNET_PROVIDER', provider_type: mode, chaos })));
function close() { server.close(() => { wallet.close(); process.exit(0); }); }
process.on('SIGINT', close); process.on('SIGTERM', close);
