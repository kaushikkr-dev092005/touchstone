import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

test('read-only quote command rejects caps and extra authorization fields before discovery',()=>{
  const env=Object.fromEntries(Object.entries(process.env).filter(([k])=>
    !/^(AIRWALLEX_|ANTHROPIC_|METAL_|TOUCHSTONE_)/.test(k)&&k!=='AGENT_PRIVATE_KEY'));
  for(const request of [
    {url:'https://provider.invalid',maximum_micro_usdz:0},
    {url:'https://provider.invalid',maximum_micro_usdz:true},
    {url:'https://provider.invalid',maximum_micro_usdz:1,approved:true},
  ]) {
    const p=spawnSync(process.execPath,[fileURLToPath(new URL('./quote-probe.mjs',import.meta.url))],
      {input:JSON.stringify(request),encoding:'utf8',env,timeout:10000});
    assert.equal(p.status,1);
    assert.deepEqual(JSON.parse(p.stdout),{error:'PROVIDER_QUOTE_UNAVAILABLE'});
  }
});
