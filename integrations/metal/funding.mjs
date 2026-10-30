import { generatePrivateKey, privateKeyToAccount } from 'viem/accounts';
import { mkdirSync, readFileSync, writeFileSync, chmodSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

export function prepareFundingWallet(filename) {
  mkdirSync(dirname(filename), { recursive: true, mode: 0o700 });
  let existing;
  try { existing = JSON.parse(readFileSync(filename, 'utf8')); }
  catch (e) { if (e.code !== 'ENOENT') throw Error('Existing funding wallet is unreadable; preserve it'); }
  if (!existing) {
    const private_key = generatePrivateKey();
    existing = { private_key, address: privateKeyToAccount(private_key).address, network: 'eip155:63825' };
    writeFileSync(filename, JSON.stringify(existing) + '\n', { flag: 'wx', mode: 0o600 });
    chmodSync(filename, 0o600);
  }
  const address = privateKeyToAccount(existing.private_key).address;
  if (existing.address !== address || existing.network !== 'eip155:63825') throw Error('Funding wallet identity mismatch');
  return { mode: 'LOCAL_ONLY', network: existing.network, address, funded: false, private_key_disclosed: false, transactions_sent: 0 };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = resolve(fileURLToPath(new URL('../..', import.meta.url)));
  try { console.log(JSON.stringify(prepareFundingWallet(resolve(root, 'data/metal/funding-wallet.json')), null, 2)); }
  catch { console.error('Funding wallet setup failed; private data hidden'); process.exitCode = 1; }
}
