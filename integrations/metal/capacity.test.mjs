import test from 'node:test';
import assert from 'node:assert/strict';
import {capacityQuote} from './capacity.mjs';
test('capacity uses observed tail latency and actual throttling, without invented price coefficients',()=>{
  const q=capacityQuote(10000n,2,[100,200,300,400],{sample_id:'sample',observed_at:100,thermal_throttling_active:false});
  assert.equal(q.latency_ms,1200);assert.equal(q.price,10000n);assert.equal(q.quote_allowed,true);
  assert.equal(capacityQuote(10000n,0,[],{thermal_throttling_active:true}).quote_allowed,false);
  assert.equal(capacityQuote(10000n,0,[],null).recent_p95_ms,null);
});
