import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { decodeResource, DeliveryStore, priceForQueue, qualityDropOutput } from './provider-core.mjs';
import { prepareFundingWallet } from './funding.mjs';

const task = { id: 'probe', kind: 'arithmetic', source: { amounts_cents: [100], discount_cents: 0 } };
const bytes = Buffer.from(JSON.stringify(task));
const path = '/inference/' + createHash('sha256').update(bytes).digest('hex') + '?task=' + bytes.toString('base64url');

test('resource task digest binds the full input', () => {
  assert.deepEqual(decodeResource(path).task, task);
  assert.throws(() => decodeResource(path + '&other=1'));
  assert.throws(() => decodeResource(path.replace(/.$/, 'x')));
  assert.throws(() => decodeResource('/inference/invalid?task=' + bytes.toString('base64url')));
});

test('paid delivery replays stored output without another model call', async () => {
  const db = new DatabaseSync(':memory:');
  try {
    const store = new DeliveryStore(db);
    let calls = 0;
    const perform = async () => { calls++; return { output: {total_cents: 100} }; };
    const result = await store.deliver('receipt1', path, 'digest1', perform);
    assert.deepEqual(await store.deliver('receipt1', path, 'digest1', perform), result);
    assert.equal(calls, 1);
    await assert.rejects(store.deliver('receipt1', path + 'changed', 'digest1', perform), /another resource/);
    await assert.rejects(store.deliver('receipt1', path, 'digest2', perform), /another resource/);
  } finally { db.close(); }
});

test('worker failure retains its receipt obligation and can retry CPU execution', async () => {
  const db = new DatabaseSync(':memory:');
  try {
    const store = new DeliveryStore(db);
    await assert.rejects(store.deliver('receipt2', path, 'digest2', async () => { throw Error('worker failed'); }));
    const result = await store.deliver('receipt2', path, 'digest2', async () => ({output: {total_cents: 100}}));
    assert.equal(result.output.total_cents, 100);
    assert.equal(db.prepare('SELECT count(*) AS n FROM deliveries').get().n, 1);
  } finally { db.close(); }
});

test('provider quotes bind queue-sensitive prices and load metadata', () => {
  const db = new DatabaseSync(':memory:');
  try {
    const store = new DeliveryStore(db);
    const offer = { amount: '10000000000000000', asset: 'usdz', extra: { serviceUrl: 'https://example.test' } };
    store.rememberQuote(path, offer, Date.now() + 30000, 2, 3000);
    assert.deepEqual(store.findQuote(path, offer), { offer, queue_depth: 2, latency_ms: 3000 });
    assert.equal(store.findQuote(path, { ...offer, amount: '12000000000000000' }), null);
    assert.equal(priceForQueue(10000n, 0), 10000n * 10n ** 12n);
    assert.equal(priceForQueue(10000n, 2), 14000n * 10n ** 12n);
    assert.equal(priceForQueue(50000n, 4), 50000n * 10n ** 12n);
  } finally { db.close(); }
});

test('quality-drop chaos changes a balanced invoice without hiding the aggregate', () => {
  const task = { kind: 'invoice_consistency' };
  const output = { finding: 'CONSISTENT', line_items: [{ line_total_cents: 100 }, { line_total_cents: 200 }] };
  const dropped = qualityDropOutput(task, output);
  assert.deepEqual(dropped.line_items.map(row => row.line_total_cents), [101, 199]);
  assert.equal(dropped.line_items.reduce((sum, row) => sum + row.line_total_cents, 0), 300);
  assert.deepEqual(output.line_items.map(row => row.line_total_cents), [100, 200]);
});

test('dedicated funding wallet is preserved and never returned as private data', () => {
  const directory = mkdtempSync(join(tmpdir(), 'touchstone-funding-'));
  try {
    const filename = join(directory, 'wallet.json');
    const first = prepareFundingWallet(filename);
    const raw = readFileSync(filename, 'utf8');
    assert.deepEqual(prepareFundingWallet(filename), first);
    assert.equal(readFileSync(filename, 'utf8'), raw);
    assert.equal(JSON.stringify(first).includes(JSON.parse(raw).private_key), false);
  } finally { rmSync(directory, {recursive: true, force: true}); }
});
