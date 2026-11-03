import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../../apps/dashboard/index.html',import.meta.url),'utf8');
function body(name,next){return html.slice(html.indexOf('function '+name+'('),html.indexOf('function '+next+'('));}
const metric=body('renderMeasuredCost','setHealth');
function render(runs){
  const nodes=Object.fromEntries(['measured-cost','measured-unit','measured-badge','measured-scope'].map(id=>[id,{textContent:'stale',className:''}]));
  vm.runInNewContext(metric+'\nrenderMeasuredCost({runs});',{$:id=>nodes[id],runs});
  return nodes;
}
const valid={policy:'real-touchstone',valid_live_evidence:true,reconciled:true,verified_correct_steps:2,steps:3,cost_per_verified_correct_micro_usd:15000,observed_at:1,scope:'test fixture'};
test('hero cost refuses simulated, unreconciled, zero-correct and malformed evidence',()=>{
  for(const patch of [{policy:'simulated'},{valid_live_evidence:false},{reconciled:false},{verified_correct_steps:0},{cost_per_verified_correct_micro_usd:null},{cost_per_verified_correct_micro_usd:-1},{cost_per_verified_correct_micro_usd:Infinity}]){
    const nodes=render([{...valid,...patch}]);
    assert.equal(nodes['measured-cost'].textContent,'—');
    assert.match(nodes['measured-badge'].textContent,/BLOCKED/);
  }
});
test('hero cost selects latest qualifying run and discloses mixed accounting',()=>{
  const nodes=render([valid,{...valid,observed_at:2,cost_per_verified_correct_micro_usd:22000},{...valid,observed_at:3,reconciled:false}]);
  assert.equal(nodes['measured-cost'].textContent,'0.0220');
  assert.match(nodes['measured-badge'].textContent,/MEASURED PAYMENTS \+ SIMULATED CHECK FEES/);
  assert.match(nodes['measured-scope'].textContent,/hosted API USD costs excluded/);
});
test('server halt wins over running jobs and unfinished ignition',()=>{
  const context=vm.createContext({});
  vm.runInContext(body('eventLightState','setEventLight'),context);
  assert.equal(vm.runInContext("eventLightState({halted:true,jobs:[{status:'RUNNING'}]},false)",context),'kill');
  assert.equal(vm.runInContext("eventLightState({jobs:[{status:'PAUSED_POLICY'}]},true)",context),'pause');
  assert.equal(vm.runInContext("eventLightState({jobs:[]},true)",context),'idle');
});
