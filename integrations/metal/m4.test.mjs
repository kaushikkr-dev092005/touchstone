import test from 'node:test';
import assert from 'node:assert/strict';
import { scenario } from './m4-chaos.mjs';

test('M4 faults bind the same source index to a named tier across policies', () => {
  const faults = Object.fromEntries([0,1,2,3].map(p => [`M4-20261120-3-${p}`, { 'local-gpu': 'outage' }]));
  const schedule = scenario(JSON.stringify({ version: 1, faults }));
  for (let p=0;p<4;p++) {
    assert.equal(schedule.fault(`M4-20261120-3-${p}`, 'local-gpu'), 'outage');
    assert.equal(schedule.fault(`M4-20261120-3-${p}`, 'hosted-premium'), 'none');
  }
  assert.equal(schedule.fault('ordinary-invoice', 'local-gpu'), 'none');
  assert.equal(schedule.sha256.length, 64);
  assert.equal(schedule.sha256, scenario(JSON.stringify({ faults, version: 1 })).sha256);
});

test('invalid M4 fault schedules fail before serving any payment', () => {
  for (const raw of ['{}', '{"version":1,"faults":[]}',
    '{"version":1,"faults":{"bad-id":{"local-gpu":"outage"}}}',
    '{"version":1,"faults":{"M4-1-2-0":{"other":"outage"}}}',
    '{"version":1,"faults":{"M4-1-2-0":{"local-gpu":"erase-wallet"}}}']) {
    assert.throws(() => scenario(raw));
  }
});
