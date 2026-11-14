import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const html=readFileSync(new URL('../../apps/dashboard/index.html',import.meta.url),'utf8');
const source=html.slice(html.indexOf('function updateFlowStatuses('),html.indexOf('const nodeEvents='));
function state(workflow) {
  const nodes={};
  const context=vm.createContext({$:id=>nodes[id]??=( {textContent:'',dataset:{}} )});
  vm.runInContext(source,context);
  context.updateFlowStatuses({airwallex:{hold_workflow:workflow}},{attempts:[]});
  return nodes;
}
test('completed sandbox capture is saved proof, not an active hold or simulated payment',()=>{
  const nodes=state('MEASURED_HOSTED_CAPTURE_COMPLETE');
  assert.equal(nodes['node-hold-status'].textContent,'SAVED SANDBOX CAPTURE');
  assert.equal(nodes['node-hold-status'].dataset.state,'verified');
  assert.equal(nodes['node-pay-status'].textContent,'SIMULATED');
});
test('missing or merchant-blocked hold stays unverified or blocked',()=>{
  assert.equal(state('IMPLEMENTED_UNVERIFIED')['node-hold-status'].textContent,'UNVERIFIED');
  assert.equal(state('BLOCKED_MERCHANT_CONFIGURATION')['node-hold-status'].textContent,'BLOCKED');
});
