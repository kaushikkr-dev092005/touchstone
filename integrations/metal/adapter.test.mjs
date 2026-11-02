import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { amount, approvedOffer, executePurchase, recoverPurchase, resourceUrl, discover, quote } from './adapter.mjs';
import { openWallet } from './wallet.mjs';
import { clearingRequirements, clearingInvoice, createClearingSigner, USDZ } from '@metalntwx/metal-pay';

const seller = createClearingSigner('0x' + '12'.repeat(32));
const deployment = { network: 'eip155:63825', settlement: '0x' + '34'.repeat(20), asset: USDZ.address,
  serviceUrl: 'https://clearing.example', validatorUrls: [] };
const url = 'https://provider.example/inference';
const offer = clearingRequirements({ ...deployment, recipient: seller.publicKey }, amount('0.01'), url);
const q = () => ({ url, offer, expires_at: Date.now() + 30000 });
const header = value => Buffer.from(JSON.stringify({ x402Version: 2, accepts: [value] })).toString('base64');

async function fixture(fn) {
  const path = mkdtempSync(join(tmpdir(), 'touchstone-wallet-'));
  const wallet = openWallet(path);
  try { await fn(wallet, path); } finally { wallet.close(); rmSync(path, { recursive: true, force: true }); }
}
async function receipt(wallet) {
  const invoice = clearingInvoice(offer, offer.extra.invoicePrefix + ':receipt-1');
  await wallet.store.save({ payments: { [invoice.id]: { invoice, receipt: { body: 'public-test-receipt' } } }, entries: [], sequence: '1' });
}

test('amounts and resource URLs reject rounding and unapproved protocols', () => {
  assert.equal(amount('0.000001'), 1000000000000n);
  for (const x of ['0.0000001', '-1', '1e2', 0.01]) assert.throws(() => amount(x));
  for (const x of ['http://example.com', 'https://user:pass@example.com', 'https://example.com/#x']) assert.throws(() => resourceUrl(x));
  assert.equal(resourceUrl('http://127.0.0.1:8080/infer'), 'http://127.0.0.1:8080/infer');
});

test('quote guards reject wrong price, token, chain and deployment', () => {
  assert.equal(approvedOffer(header(offer), deployment, amount('0.02')).amount, offer.amount);
  for (const bad of [ { ...offer, amount: amount('0.03').toString() }, { ...offer, network: 'eip155:1' },
    { ...offer, asset: '0x' + '00'.repeat(20) }, { ...offer, extra: { ...offer.extra, settlement: '0x' + '56'.repeat(20) } } ]) {
    assert.throws(() => approvedOffer(header(bad), deployment, amount('0.02')));
  }
});

test('live quote records queue depth and completed latency sample count', async () => {
  const values = { 'PAYMENT-REQUIRED': header(offer), 'X-Touchstone-Queue-Depth': '2',
    'X-Touchstone-Latency-Ms': '3000', 'X-Touchstone-Latency-Samples': '0',
    'X-Touchstone-Provider': 'hosted-premium' };
  const result = await quote(url, deployment, amount('0.02'), async () => ({
    status: 402, headers: { get: name => values[name] ?? null },
  }));
  assert.equal(result.queue_depth, 2);
  assert.equal(result.latency_ms, 3000);
  assert.equal(result.latency_samples, 0);
  assert.equal(result.provider_id, 'hosted-premium');
});

test('SDK store and exclusive owner lock persist across reopen', () => {
  const path = mkdtempSync(join(tmpdir(), 'touchstone-wallet-'));
  const one = openWallet(path);
  const publicKey = one.signer.publicKey;
  assert.throws(() => openWallet(path), /already be owned/);
  one.close();
  const two = openWallet(path);
  try { assert.equal(two.signer.publicKey, publicKey); }
  finally { two.close(); rmSync(path, { recursive: true, force: true }); }
});

test('completed purchase is idempotent and terms cannot change', async () => fixture(async wallet => {
  let effects = 0;
  const perform = async () => { effects++; await receipt(wallet); return { ok: true, status: 200, body: { total: 5 } }; };
  const result = await executePurchase(wallet, 'reservation-1', q(), amount('0.50'), perform);
  assert.equal(result.state, 'DELIVERED');
  assert.deepEqual(await executePurchase(wallet, 'reservation-1', q(), amount('0.50'), perform), result);
  assert.equal(effects, 1);
  await assert.rejects(executePurchase(wallet, 'reservation-1', { ...q(), url: url + '/changed' }, amount('0.50'), perform), /terms changed/);
}));

test('lost delivery recovers paid receipt without a second payment', async () => fixture(async wallet => {
  let effects = 0;
  await assert.rejects(executePurchase(wallet, 'reservation-2', q(), amount('0.50'), async () => {
    effects++; await receipt(wallet); throw Error('Process lost provider output after receipt');
  }), /requires recovery/);
  await assert.rejects(executePurchase(wallet, 'reservation-2', q(), amount('0.50'), async () => { effects++; }), /requires recover/);
  const result = await recoverPurchase(wallet, 'reservation-2', { pay() { throw Error('Must not pay again'); } });
  assert.equal(result.state, 'PAID_OUTPUT_MISSING');
  assert.equal(effects, 1);
  await assert.rejects(executePurchase(wallet, 'reservation-3', q(), amount('0.50'), async () => {}), /missing delivery/);
}));

test('delivery recovery presents the existing paid proof without another purchase', async () => fixture(async wallet => {
  await assert.rejects(executePurchase(wallet, 'delivery-replay', q(), amount('0.50'), async () => {
    await receipt(wallet); throw Error('lost output');
  }));
  let deliveries = 0;
  const result = await recoverPurchase(wallet, 'delivery-replay', { pay() { throw Error('Must not pay again'); } }, async (terms, paid) => {
    assert.equal(terms.url, url);
    assert.equal(paid.invoice.amount, offer.amount);
    deliveries++;
    return {ok: true, status: 200, body: {output: {total_cents: 100}}};
  });
  assert.equal(result.state, 'DELIVERED');
  assert.equal(deliveries, 1);
  assert.equal((await recoverPurchase(wallet, 'delivery-replay', {})).state, 'DELIVERED');
}));

test('unknown payment retains reservation and stops another purchase', async () => fixture(async wallet => {
  await assert.rejects(executePurchase(wallet, 'reservation-4', q(), amount('0.50'), async () => {
    await wallet.store.save({ payments: {}, pending: { url, invoice: clearingInvoice(offer, offer.extra.invoicePrefix + ':unknown') } });
    throw Error('timeout');
  }));
  await assert.rejects(recoverPurchase(wallet, 'reservation-4', { async pay() { throw Error('still held'); } }), /still held/);
  await assert.rejects(executePurchase(wallet, 'reservation-5', q(), amount('0.50'), async () => {}), /unresolved/);
}));

test('an authoritative SDK refusal permits only an identical unpaid reservation retry', async () => fixture(async wallet => {
  await assert.rejects(executePurchase(wallet, 'unpaid-retry', q(), amount('0.50'), async () => {
    await wallet.store.save({ payments: {}, entries: [], sequence: '0' });
    throw Error('SDK cleared its refused invoice');
  }));
  assert.equal((await recoverPurchase(wallet, 'unpaid-retry', {})).state, 'UNPAID_CONFIRMED');
  await assert.rejects(executePurchase(wallet, 'unpaid-retry', {...q(), url: url + '/changed'}, amount('0.50'), async () => {}), /terms changed/);
  const result = await executePurchase(wallet, 'unpaid-retry', q(), amount('0.50'), async () => {
    await receipt(wallet); return {ok:true, status:200, body:{total:5}};
  });
  assert.equal(result.state, 'DELIVERED');
}));

test('pending payment recovery resends the exact original SDK invoice', async () => fixture(async wallet => {
  const invoice = clearingInvoice(offer, offer.extra.invoicePrefix + ':held');
  await assert.rejects(executePurchase(wallet, 'held', q(), amount('0.50'), async () => {
    await wallet.store.save({ payments: {}, pending: { url, invoice }, entries: [], sequence: '1' });
    throw Error('Service answer was lost');
  }));
  let calls = 0;
  const result = await recoverPurchase(wallet, 'held', { async pay(original, resource) {
    assert.deepEqual(original, invoice); assert.equal(resource, url); calls++;
    await receipt(wallet);
  } });
  assert.equal(calls, 1);
  assert.equal(result.state, 'PAID_OUTPUT_MISSING');
}));

test('pending invoice for another URL is never replayed', async () => fixture(async wallet => {
  await assert.rejects(executePurchase(wallet, 'held-other-url', q(), amount('0.50'), async () => {
    await wallet.store.save({ payments: {}, pending: { url: url + '/different', invoice: { amount: offer.amount } } });
    throw Error('lost');
  }));
  await assert.rejects(recoverPurchase(wallet, 'held-other-url', { pay() { throw Error('Must not be called'); } }), /not this reserved request/);
}));

test('pending invoice for another seller is never replayed', async () => fixture(async wallet => {
  await assert.rejects(executePurchase(wallet, 'held-other-seller', q(), amount('0.50'), async () => {
    const invoice = { ...clearingInvoice(offer, offer.extra.invoicePrefix + ':held'), recipient: createClearingSigner('0x' + '23'.repeat(32)).publicKey };
    await wallet.store.save({ payments: {}, pending: { url, invoice } });
    throw Error('lost');
  }));
  await assert.rejects(recoverPurchase(wallet, 'held-other-seller', { pay() { throw Error('Must not be called'); } }), /not this reserved request/);
}));

test('budget and expiry block dispatch before an effect', async () => fixture(async wallet => {
  let effects = 0;
  const perform = async () => { effects++; };
  await assert.rejects(executePurchase(wallet, 'low-budget', q(), amount('0.001'), perform), /budget exhausted/);
  await assert.rejects(executePurchase(wallet, 'expired', { ...q(), expires_at: Date.now() - 1 }, amount('1'), perform), /expired/);
  assert.equal(effects, 0);
}));

test('discovery uses pinned testnet facilitator and validates response', async () => {
  let endpoint;
  const metadata = await discover(async u => { endpoint = u; return { ok: true, json: async () => ({ kinds: [{ x402Version: 2, scheme: 'bajillion', network: deployment.network, extra: deployment }] }) }; });
  assert.match(endpoint, /^https:\/\/x402-testnet\.metalntwx\.com\//);
  assert.equal(metadata.settlement, deployment.settlement);
});
