import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { gasCappedAccount } from './native-budget.mjs';
import { createWalletClient, custom } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';

function fixture() {
  const db = new DatabaseSync(':memory:');
  db.exec('CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)');
  let signed = 0;
  const account = { address: 'fixture', async signTransaction() { signed++; return 'signed-fixture'; } };
  return { db, account, signed: () => signed };
}

test('native fee reservations aggregate across transactions and account reopen', async () => {
  const f = fixture();
  try {
    let guarded = gasCappedAccount(f.account, f.db, '100');
    await guarded.signTransaction({ chainId: 63825, gas: 10n, maxFeePerGas: 6n, value: 0n });
    guarded = gasCappedAccount(f.account, f.db, '100');
    await assert.rejects(guarded.signTransaction({ chainId: 63825, gas: 10n, maxFeePerGas: 5n }), /cap exceeded/);
    assert.equal(f.signed(), 1);
    assert.throws(() => gasCappedAccount(f.account, f.db, '200'), /already bound/);
  } finally { f.db.close(); }
});

test('unbounded fees and nonzero native transfers cannot be signed', async () => {
  const f = fixture();
  try {
    const guarded = gasCappedAccount(f.account, f.db, '100');
    for (const tx of [{ gas: 1n }, { gas: 1n, maxFeePerGas: 1n, value: 1n }])
      await assert.rejects(guarded.signTransaction({ chainId: 63825, ...tx }), /cannot be bounded/);
    await assert.rejects(guarded.signTransaction({ chainId: 1, gas: 1n, maxFeePerGas: 1n }), /testnet chain/);
    assert.equal(f.signed(), 0);
  } finally { f.db.close(); }
});

test('signer failure retains the reservation and prevents a replacement signature', async () => {
  const f = fixture();
  try {
    const guarded = gasCappedAccount({ ...f.account, async signTransaction() { throw Error('fixture failure'); } }, f.db, '100');
    await assert.rejects(guarded.signTransaction({ chainId: 63825, gas: 10n, maxFeePerGas: 10n }), /fixture failure/);
    await assert.rejects(guarded.signTransaction({ chainId: 63825, gas: 1n, maxFeePerGas: 1n }), /cap exceeded/);
  } finally { f.db.close(); }
});

test('viem uses the guarded signer and refuses excess before producing a raw transaction', async () => {
  const f = fixture();
  try {
    const account = privateKeyToAccount('0x' + '11'.repeat(32));
    const guarded = gasCappedAccount(account, f.db, '100');
    const wallet = createWalletClient({ account: guarded, transport: custom({ async request({ method }) { if (method === 'eth_chainId') return '0xf951'; throw Error('Network forbidden'); } }) });
    await assert.rejects(wallet.signTransaction({ chain: null, chainId: 63825,
      to: account.address, data: '0x', value: 0n, gas: 100n, maxFeePerGas: 2n,
      maxPriorityFeePerGas: 1n, nonce: 0, type: 'eip1559' }), /cap exceeded/);
  } finally { f.db.close(); }
});
