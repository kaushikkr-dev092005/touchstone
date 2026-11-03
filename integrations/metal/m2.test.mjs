import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { openFundingOwner, openWallet } from './wallet.mjs';

test('shared funding ownership serializes deposits across distinct wallets', () => {
  const root = mkdtempSync(join(tmpdir(), 'touchstone-m2-'));
  try {
    const a = openFundingOwner(join(root, 'a'));
    try {
      assert.throws(() => openFundingOwner(join(root, 'b')), /funding account/);
      const wa = openWallet(join(root, 'a')), wb = openWallet(join(root, 'b'));
      try { assert.notEqual(wa.signer.publicKey, wb.signer.publicKey); }
      finally { wa.close(); wb.close(); }
    } finally { a.close(); }
    openFundingOwner(join(root, 'b')).close();
  } finally { rmSync(root, { recursive: true, force: true }); }
});

test('bridge refuses every monetary command without explicit boolean execute', () => {
  for (const command of ['pay', 'deposit', 'withdraw', 'recover']) {
    const result = spawnSync(process.execPath, [fileURLToPath(new URL('./bridge.mjs', import.meta.url))], {
      input: JSON.stringify({ command, job: 'm2-guard-fixture', execute: false }), encoding: 'utf8', timeout: 15000,
    });
    assert.equal(result.status, 1);
    assert.equal(JSON.parse(result.stdout).ok, false);
    assert.equal(JSON.parse(result.stdout).error, 'METAL_OPERATION_UNRESOLVED');
  }
});

test('standalone CLI refuses money movement before network and wallet access', () => {
  for (const command of ['pay', 'deposit', 'withdraw', 'recover']) {
    const result = spawnSync(process.execPath, [fileURLToPath(new URL('./cli.mjs', import.meta.url)), command, 'm2-guard-fixture'],
      { encoding: 'utf8', timeout: 15000 });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Explicit --execute/);
  }
});
