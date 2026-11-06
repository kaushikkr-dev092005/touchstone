import test from 'node:test';
import assert from 'node:assert/strict';
import {capacityQuote} from './capacity.mjs';
test('capacity uses observed tail latency and actual throttling, without invented price coefficients',()=>{
  const q=capacityQuote(10000n,2,[100,200,300,400],{sample_id:'sample',observed_at:100,thermal_throttling_active:false});
  assert.equal(q.latency_ms,1200);assert.equal(q.price,10000n);assert.equal(q.quote_allowed,true);
  assert.equal(capacityQuote(10000n,0,[],{thermal_throttling_active:true}).quote_allowed,false);
  assert.equal(capacityQuote(10000n,0,[],null).recent_p95_ms,null);
});

import { createHash } from 'node:crypto';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { loadCalibration, capacityMultiplier } from './capacity.mjs';
const stable=v=>Array.isArray(v)?'['+v.map(stable).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stable(v[k])).join(',')+'}':JSON.stringify(v);
function calibrationFixture(overrides={}) {
  const body={version:'touchstone-capacity-calibration-v1',model_sha256:'ab'.repeat(32),valid_until:Date.now()/1000+3600,
    baseline_tps:100,max_multiplier:1.25,minimum_live_samples:5,...overrides};
  return {label:'MEASURED',body,digest:createHash('sha256').update(stable(body)).digest('hex')};
}
test('calibrated multiplier follows measured throughput only, is bounded and needs enough live samples',()=>{
  const c=calibrationFixture();
  assert.equal(capacityMultiplier(c,[100,100,100,100]),1);           // too few live samples
  assert.equal(capacityMultiplier(c,[100,100,100,100,100]),1);       // at baseline
  assert.equal(capacityMultiplier(c,[80,80,80,80,80]),1.25);         // exactly at the cap
  assert.equal(capacityMultiplier(c,[10,10,10,10,10]),1.25);         // cap holds when throughput collapses
  assert.equal(capacityMultiplier(c,[200,200,200,200,200]),1);       // faster never discounts below base
  const q=capacityQuote(10000n,0,[],{thermal_throttling_active:false,sample_id:'s',observed_at:1},c,[80,80,80,80,80],12000n);
  assert.equal(q.price,12000n);                                      // ceiling honoured
  assert.equal(capacityQuote(10000n,0,[],{temperature_c:99,thermal_throttling_active:false},c,[],null).price,10000n);
});
test('tampered, expired or wrong-model calibrations are ignored',()=>{
  const dir=mkdtempSync(join(tmpdir(),'cal-')), file=join(dir,'c.json'), sha='ab'.repeat(32);
  writeFileSync(file,JSON.stringify(calibrationFixture()));assert.ok(loadCalibration(file,sha));
  assert.equal(loadCalibration(file,'cd'.repeat(32)),null);
  writeFileSync(file,JSON.stringify(calibrationFixture({valid_until:1})));assert.equal(loadCalibration(file,sha),null);
  const edited=calibrationFixture();edited.body.baseline_tps=1;writeFileSync(file,JSON.stringify(edited));assert.equal(loadCalibration(file,sha),null);
  writeFileSync(file,JSON.stringify(calibrationFixture({max_multiplier:9})));assert.equal(loadCalibration(file,sha),null);
  assert.equal(loadCalibration(join(dir,'missing.json'),sha),null);
});
