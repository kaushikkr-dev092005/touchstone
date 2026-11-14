import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// The dashboard's pure presentation helpers live between these two markers in the page script.
const html = readFileSync(new URL('../../apps/dashboard/index.html', import.meta.url), 'utf8');
const helpers = html.slice(html.indexOf('function txOutcome('), html.indexOf('/* ───────── Dashboard shell: behaviour'));
const money = n => (n < 0 ? '-' : '') + '$' + (Math.abs(n) / 1e6).toFixed(n !== 0 && Math.abs(n) < 1e4 ? 6 : 4);
const context = vm.createContext({ money });
vm.runInContext(helpers, context);
const { runSignals, chartRows, compareRuns, runTotals, niceCeil, txOutcome, modeClass } = context;
const text = items => items.map(item => item.parts.flat().map(part => typeof part === 'string' ? part : part.b).join('') + ' | ' + item.src);

const tx = (seq, provider, price, state, run = 'r2', job = 'r2-1') => ({
  seq, key: 'k' + seq, run_id: run, job_id: job, step_id: 'step-' + seq, attempt: 0, provider, price, verify_cost: 1000,
  state, passed: state === 'VERIFIED_OK' ? 1 : state === 'VERIFIED_FAIL' ? 0 : null,
  charged_provider: state === 'VOID' || state === 'RESERVED' ? 0 : price, charged_verification: state === 'VOID' || state === 'RESERVED' ? 0 : 1000,
});
const state = {
  runs: [{ id: 'r2', float_total: 1500000 }, { id: 'r1', float_total: 1500000 }],
  jobs: [
    { id: 'r2-1', run_id: 'r2', status: 'PAUSED_POLICY', hold: 750000, spent: 93000, reserved: 0, accepted: 2, count: 4, rail_spent: 90000, allocation: 500000, price_cap: 60000 },
    { id: 'r2-2', run_id: 'r2', status: 'COMPLETED', hold: 750000, spent: 0, reserved: 21000, accepted: 0, count: 0, rail_spent: 0, allocation: 500000, price_cap: 60000 },
    { id: 'r1-1', run_id: 'r1', status: 'COMPLETED', hold: 750000, spent: 62000, reserved: 0, accepted: 2, count: 2, rail_spent: 60000, allocation: 500000, price_cap: 60000 },
  ],
  reconciliation: { matched: true, rail_total: 150000, pending: 0, mode: 'SIMULATED' },
  audit: { valid: true, events: 12 },
};
const rows = [tx(1, 'economy', 10000, 'VERIFIED_OK'), tx(2, 'economy', 40000, 'VERIFIED_FAIL'), tx(3, 'premium', 50000, 'VERIFIED_OK'),
  tx(4, 'economy', 10000, 'RESERVED'), tx(5, 'premium', 50000, 'VERIFIED_OK', 'r1', 'r1-1')];

test('signals refuse to speak without a recorded run', () => {
  assert.equal(runSignals({ runs: [] }, rows).length, 0);
  assert.equal(runSignals(null, rows).length, 0);
});

test('signals are arithmetic over the latest run only', () => {
  const lines = text(runSignals(state, rows));
  // Latest run: charged 11000 + 41000 + 51000 + 0 = 103000; rejected 41000 → 39.8%.
  assert.match(lines[0], /Rejected attempts cost \$0\.0410 — 39\.8% of this run’s spend\./);
  assert.match(lines[0], /1 of 4 attempts rejected/);
  // economy: 52000 charged / 1 accepted; premium: 51000 / 1 — cheapest first, and r1's premium row is ignored.
  assert.match(lines[1], /^premium delivered accepted outputs at \$0\.0510 each; economy at \$0\.0520\./);
  assert.match(lines[2], /economy quotes moved from \$0\.0100 to \$0\.0400 \(4\.0×\)/);
  assert.match(lines[3], /^1 of 2 jobs paused within their limits/);
  assert.match(lines[4], /matched at \$0\.1500/);
  assert.match(lines[5], /Audit chain valid across 12 events/);
  for (const line of lines) assert.doesNotMatch(line, /sav(e|ing)|NaN|undefined|Infinity|project/i);
});

test('a run with attempts but no charges never prints NaN', () => {
  const lines = text(runSignals(state, [tx(9, 'economy', 10000, 'VOID'), tx(10, 'economy', 10000, 'RESERVED')]));
  assert.match(lines[0], /No attempt in this run was rejected/);
  for (const line of lines) assert.doesNotMatch(line, /NaN|Infinity/);
});

test('integrity failures and reconciliation gaps are reported as such', () => {
  const lines = text(runSignals({ ...state, reconciliation: { matched: false, rail_total: 1, pending: 2 }, audit: { valid: false, events: 3 } }, rows));
  assert.ok(lines.some(line => /require review/.test(line) && /2 unresolved/.test(line)));
  assert.ok(lines.some(line => /integrity failure/.test(line)));
});

test('chart rows: empty stays empty, run filter, seq order and newest-first truncation', () => {
  assert.deepEqual(JSON.parse(JSON.stringify(chartRows([], 'run', 'r2', 50))), { rows: [], total: 0 });
  assert.deepEqual(chartRows(rows, 'run', 'r2', 50).rows.map(t => t.seq), [1, 2, 3, 4]);
  assert.deepEqual(chartRows([...rows].reverse(), 'all', 'r2', 50).rows.map(t => t.seq), [1, 2, 3, 4, 5]);
  const limited = chartRows(rows, 'all', 'r2', 2);
  assert.deepEqual(limited.rows.map(t => t.seq), [4, 5]);
  assert.equal(limited.total, 5);
});

test('trends need a real prior value; run totals keep unknowns unknown', () => {
  assert.equal(compareRuns(10, null), null);
  assert.equal(compareRuns(10, 0), null);
  assert.equal(compareRuns(null, 10), null);
  assert.equal(compareRuns(15, 10), 50);
  const latest = runTotals(state, 'r2');
  assert.equal(latest.spent, 93000);
  assert.equal(latest.unit, 46500);
  assert.equal(latest.floatLeft, 1500000 - 90000);
  assert.equal(latest.used, (93000 + 21000) / 1500000 * 100);
  const none = runTotals({ runs: [{ id: 'x' }], jobs: [{ id: 'x-1', run_id: 'x', spent: 0, accepted: 0, hold: 0 }] }, 'x');
  assert.equal(none.unit, null);
  assert.equal(none.used, null);
});

test('outcome, axis and mode helpers', () => {
  assert.deepEqual([tx(1, 'a', 1, 'VERIFIED_OK'), tx(2, 'a', 1, 'VERIFIED_FAIL'), tx(3, 'a', 1, 'VOID'), tx(4, 'a', 1, 'RESERVED')].map(txOutcome), ['ok', 'fail', 'void', 'open']);
  assert.deepEqual([0, 17000, 20000, 21000, 61000].map(niceCeil), [1, 20000, 20000, 25000, 100000]);
  assert.deepEqual(['SIMULATED', 'mock', 'LIVE_TESTNET_AUTHORIZED', 'BLOCKED', ''].map(modeClass), ['simulated', 'mock', 'live', 'blocked', '']);
});

test('every hash target used by the shell resolves to an element, and each page has a nav entry', () => {
  const ids = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]));
  for (const [, target] of html.matchAll(/href="#([^"$]+)"/g)) assert.ok(ids.has(target), '#' + target);
  for (const [, view] of html.matchAll(/data-view="([a-z]+)"/g)) assert.match(html, new RegExp(`data-nav="${view}"`));
});
