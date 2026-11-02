import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../../apps/dashboard/index.html', import.meta.url), 'utf8');
const start = html.indexOf('function loadBanked()');
const end = html.indexOf('loadBanked();setInterval', start);
const loader = html.slice(start, end);
const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

async function render(payload, fail = false) {
  const nodes = { 'treasury-job-rows': {innerHTML: 'old result'}, 'banked-job-rows': {innerHTML: ''} };
  const context = vm.createContext({
    $: id => nodes[id], esc, money: value => String(value / 1e6),
    fetch: async () => { if (fail) throw new Error('unavailable'); return {json: async () => payload}; },
  });
  vm.runInContext(loader + '\nloadBanked();', context);
  await new Promise(setImmediate);
  return nodes['treasury-job-rows'].innerHTML;
}

test('dashboard script parses after treasury integration', () => {
  for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
});

test('treasury evidence renders before a banked purchase and keeps account labels', async () => {
  const output = await render({jobs: [], treasury_jobs: [{scope: '<script>bad</script>', label: 'MOCK', phase: 'RECONCILED',
    terms: {customer_budget_microunits: 1000000, customer_budget_currency: 'USD', quote: {quote_id: 'q1'}, demo_usdz_per_unit: '1'},
    accounts: [{account: 'AIRWALLEX_TREASURY_FLOAT', currency: 'EUR', amount_microunits: 920000, label: 'MOCK'},
               {account: 'METAL_DEMO_FLOAT', currency: 'USDZ', amount_microunits: 920000, label: 'SIMULATED'}],
  }]});
  assert.match(output, /MOCK 0\.920000 EUR/);
  assert.match(output, /SIMULATED 0\.920000 USDZ/);
  assert.match(output, /Actual wallet funding unverified/);
  assert.match(output, /&lt;script&gt;/);
  assert.doesNotMatch(output, /<script>/);
});

test('absent or failed treasury evidence clears old values and shows BLOCKED', async () => {
  assert.match(await render({jobs: []}), /BLOCKED/);
  const failed = await render({}, true);
  assert.match(failed, /BLOCKED/);
  assert.doesNotMatch(failed, /old result/);
});
