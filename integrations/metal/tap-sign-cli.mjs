import { createPrivateKey } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { signIntent } from './tap.mjs';

// Sign one RFC 9421 intent with an existing local Ed25519 key. Never generates a key; sends nothing.
let input = '';
try {
  for await (const chunk of process.stdin) { input += chunk; if (input.length > 12000) throw Error('Request too large'); }
  const { authority, path, method = 'POST', body, key_id: keyId, private_key_file: file, tag } = JSON.parse(input);
  if (statSync(file).size > 4096) throw Error('Key file too large');
  const privateKey = createPrivateKey(readFileSync(file, 'utf8'));
  if (privateKey.asymmetricKeyType !== 'ed25519') throw Error('Ed25519 key required');
  const now = Math.floor(Date.now() / 1000);
  const headers = signIntent({ authority, path, method, body, keyId, privateKey, nonce: randomBytes(24).toString('base64url'),
    created: now, expires: now + 120, ...(tag ? { tag } : {}) });
  console.log(JSON.stringify({ ok: true, result: { headers } }));
} catch {
  console.log(JSON.stringify({ ok: false, error: 'TAP_SIGN_FAILED' }));
  process.exitCode = 1;
}
