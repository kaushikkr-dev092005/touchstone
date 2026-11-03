import { DatabaseSync } from 'node:sqlite';
import { mkdirSync, chmodSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { randomBytes } from 'node:crypto';
import { createClearingSigner } from '@metalntwx/metal-pay';

// Shared EVM funding signer: serialize deposits/withdrawals across job wallets.
// Separate from the Python coordinator lock to avoid nested lock acquisition.
export function openFundingOwner(directory) {
  mkdirSync(dirname(directory), { recursive: true, mode: 0o700 });
  const owner = new DatabaseSync(join(dirname(directory), 'sdk-funding-owner.sqlite'));
  try {
    owner.exec('PRAGMA locking_mode=EXCLUSIVE; BEGIN EXCLUSIVE; CREATE TABLE IF NOT EXISTS owner(id INTEGER)');
    return owner;
  } catch {
    owner.close();
    throw Error('Another operation owns the funding account; no transaction dispatched');
  }
}

// Implements the SDK's ClearingClientStore with SQLite durability on Windows.
export function openWallet(directory) {
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const owner = new DatabaseSync(join(directory, 'owner.sqlite'));
  let db;
  try {
    owner.exec('PRAGMA locking_mode=EXCLUSIVE; BEGIN EXCLUSIVE; CREATE TABLE IF NOT EXISTS owner(id INTEGER)');
    const filename = join(directory, 'wallet.sqlite');
    db = new DatabaseSync(filename);
    chmodSync(filename, 0o600);
    db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS purchases(id TEXT PRIMARY KEY, terms TEXT NOT NULL,
        before_ids TEXT NOT NULL, state TEXT NOT NULL, result TEXT);`);
    let key = db.prepare("SELECT value FROM settings WHERE key='private_key'").get()?.value;
    if (!key) {
      for (;;) {
        key = '0x' + randomBytes(32).toString('hex');
        try { createClearingSigner(key); break; } catch { /* Rejection-sample scalar. */ }
      }
      db.prepare("INSERT INTO settings VALUES('private_key',?)").run(key);
    }
    const signer = createClearingSigner(key);
    const store = {
      async load() { const row = db.prepare("SELECT value FROM settings WHERE key='sdk_state'").get(); return row ? JSON.parse(row.value) : null; },
      async save(state) { db.prepare("INSERT INTO settings VALUES('sdk_state',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run(JSON.stringify(state)); },
    };
    return { signer, store, db,
      bindDeployment(value) {
        const text = JSON.stringify(value);
        const prior = db.prepare("SELECT value FROM settings WHERE key='deployment'").get();
        if (prior && prior.value !== text) throw Error('Clearing deployment changed; preserve this wallet and open a fresh job wallet');
        if (!prior) db.prepare("INSERT INTO settings VALUES('deployment',?)").run(text);
      },
      close() { db.close(); owner.close(); },
    };
  } catch {
    db?.close(); owner.close();
    throw Error('Cannot open the job wallet; it may already be owned by another process');
  }
}
