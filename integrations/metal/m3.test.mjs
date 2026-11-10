import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { decodeResource } from './provider-core.mjs';

test('same x402 resource contract accepts unstructured invoice extraction without labels', () => {
  const task = {id:'ix-fixture',kind:'invoice_extraction',source:{text:'unfamiliar invoice',purchase_order:{},payments:[]}};
  const bytes = Buffer.from(JSON.stringify(task));
  const url = '/inference/'+createHash('sha256').update(bytes).digest('hex')+'?task='+bytes.toString('base64url');
  assert.deepEqual(decodeResource(url).task, task);
  assert.equal(Object.hasOwn(decodeResource(url).task.source,'truth'),false);
});

test('three-task panel preserves BLOCKED state and escapes evidence', () => {
  const html=readFileSync(new URL('../../apps/dashboard/index.html',import.meta.url),'utf8');
  const start=html.indexOf('function renderInvoiceStudy('),end=html.indexOf("fetch('/api/invoice-study')",start);
  const nodes={'invoice-study-summary':{},'invoice-showcase-rows':{},'invoice-model-rows':{}};
  const context=vm.createContext({$:id=>nodes[id],esc:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')});
  vm.runInContext(html.slice(start,end),context);
  context.renderInvoiceStudy({label:'MEASURED',models_measured:0,qualification_status:'BLOCKED_NO_ELIGIBLE_MODEL',baseline:{coverage:24/180},
    showcase:{tasks:[{task:'Known total',decision:'LOCAL_TOOL',label:'MEASURED',reason:'2000 cents'},
      {task:'Unfamiliar invoice',decision:'REVIEW_REQUIRED',label:'BLOCKED',reason:'<script>not qualified</script>'},
      {task:'Duplicate payment',decision:'HUMAN_REVIEW',label:'SIMULATED',reason:'Ambiguous'}]}});
  assert.match(nodes['invoice-study-summary'].textContent,/13\.3%/);
  assert.match(nodes['invoice-showcase-rows'].innerHTML,/BLOCKED/);
  assert.match(nodes['invoice-showcase-rows'].innerHTML,/HUMAN_REVIEW/);
  assert.doesNotMatch(nodes['invoice-showcase-rows'].innerHTML,/<script>/);
  context.renderInvoiceStudy({label:'MEASURED',profiles:[{model_id:'<unsafe>',eligible:false,
    calibration:{sources_scored:3,strict_correct:2,candidates:1,review:2,rejected:0,false_accepts:0},
    holdout:{sources_scored:0,strict_correct:0,candidates:0,review:0,rejected:0,false_accepts:0}}]});
  assert.match(nodes['invoice-model-rows'].innerHTML,/1 \/ 2 \/ 0/);
  assert.match(nodes['invoice-model-rows'].innerHTML,/INCOMPLETE OR INELIGIBLE/);
  assert.doesNotMatch(nodes['invoice-model-rows'].innerHTML,/<unsafe>/);
  context.renderInvoiceStudy({label:'BLOCKED'});
  assert.match(nodes['invoice-study-summary'].textContent,/stale or unavailable/);
  assert.doesNotMatch(nodes['invoice-showcase-rows'].innerHTML,/2000 cents/);
});
