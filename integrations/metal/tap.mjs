import { createHash, createPublicKey, sign, verify } from 'node:crypto';

// Convert a fetched JWKS (RFC 7517, OKP/Ed25519 only) into the merchant's trusted-key map. Directory keys are
// time-limited and carry their own trust label: a directory is NOT Visa approval unless an operator separately
// establishes that, so no field here ever claims it.
export function keysFromJwks(jwks, now = Math.floor(Date.now()/1000), ttl = 3600) {
  if (!jwks || !Array.isArray(jwks.keys) || jwks.keys.length > 50) throw Error('Invalid key directory');
  const keys = new Map();
  for (const jwk of jwks.keys) {
    if (jwk?.kty !== 'OKP' || jwk.crv !== 'Ed25519' || typeof jwk.kid !== 'string' || !/^[A-Za-z0-9_-]{1,100}$/.test(jwk.kid) ||
        typeof jwk.x !== 'string' || (jwk.use !== undefined && jwk.use !== 'sig') || (jwk.alg !== undefined && !['EdDSA','Ed25519'].includes(jwk.alg))) continue;
    try {
      const key = createPublicKey({ key: jwk, format: 'jwk' });
      if (key.asymmetricKeyType !== 'ed25519') continue;
      keys.set(jwk.kid, { public_key: key.export({ type: 'spki', format: 'pem' }), expires_at: now + ttl, trust_source: 'KEY_DIRECTORY' });
    } catch { /* malformed key is ignored, never trusted */ }
  }
  return keys;
}

const COMPONENTS='("@authority" "@path" "@method" "content-digest")';
const digest = body => 'sha-256=:'+createHash('sha256').update(body).digest('base64')+':';
function base(authority,path,method,contentDigest,params) {
  return `"@authority": ${authority}\n"@path": ${path}\n"@method": ${method.toUpperCase()}\n"content-digest": ${contentDigest}\n"@signature-params": ${params}`;
}

export function signIntent({authority,path,method='POST',body,keyId,privateKey,nonce,created,expires,tag='agent-payer-auth'}) {
  if (![authority,path,keyId,nonce].every(v=>typeof v==='string' && !/[\r\n"\\]/.test(v))) throw Error('Invalid signature component');
  const params=`${COMPONENTS};created=${created};expires=${expires};keyid="${keyId}";alg="ed25519";nonce="${nonce}";tag="${tag}"`;
  const cd=digest(body), signature=sign(null,Buffer.from(base(authority,path,method,cd,params)),privateKey);
  return {'content-digest':cd,'signature-input':'sig1='+params,'signature':'sig1=:'+signature.toString('base64')+':'};
}

export class TapMerchant {
  constructor(db, trustedKeys) {
    this.db=db;this.keys=trustedKeys;
    db.exec('CREATE TABLE IF NOT EXISTS tap_nonces(key_id TEXT,nonce TEXT,expires INTEGER,PRIMARY KEY(key_id,nonce))');
  }
  verify({authority,path,method,headers,body},now=Math.floor(Date.now()/1000)) {
    if (typeof authority!=='string' || /[\r\n]/.test(authority) || path!=='/tap/intent' || method!=='POST' || Buffer.byteLength(body)>4096) throw Error('Merchant request refused');
    const input=headers['signature-input']||'', signature=headers.signature||'';
    const rx=/^sig1=(\("@authority" "@path" "@method" "content-digest"\);created=(\d+);expires=(\d+);keyid="([A-Za-z0-9_-]{1,100})";alg="ed25519";nonce="([A-Za-z0-9_-]{16,128})";tag="(agent-browser-auth|agent-payer-auth)")$/;
    const m=rx.exec(input), s=/^sig1=:([A-Za-z0-9+/]{86}==):$/.exec(signature);
    if (!m||!s) throw Error('Unsupported or malformed RFC 9421 profile');
    const [,params,createdText,expiresText,keyId,nonce,tag]=m, created=Number(createdText),expires=Number(expiresText);
    if (!Number.isSafeInteger(created)||!Number.isSafeInteger(expires)||created>now||expires<=now||expires-created>480||created>=expires) throw Error('Expired/future TAP signature');
    const entry=this.keys.get(keyId);
    if (!entry || entry.expires_at<=now || !['CONTROLLED_LOCAL_KEY','KEY_DIRECTORY'].includes(entry.trust_source)) throw Error('Agent key is not locally trusted');
    const key=createPublicKey(entry.public_key);
    if (key.asymmetricKeyType!=='ed25519' || headers['content-digest']!==digest(body) ||
        !verify(null,Buffer.from(base(authority,path,method,digest(body),params)),key,Buffer.from(s[1],'base64'))) throw Error('Signed intent changed');
    const intent=JSON.parse(body);
    if (!intent || typeof intent.job_id!=='string' || !/^[A-Za-z0-9_-]{1,80}$/.test(intent.job_id) ||
        !['browse','purchase'].includes(intent.intent) || !['USD','EUR','SGD'].includes(intent.currency) ||
        !Number.isSafeInteger(intent.amount_minor) || intent.amount_minor<0 || intent.amount_minor>100 ||
        (tag==='agent-browser-auth')!==(intent.intent==='browse')) throw Error('Signed intent violates merchant policy');
    this.db.prepare('DELETE FROM tap_nonces WHERE expires<=?').run(now);
    try {this.db.prepare('INSERT INTO tap_nonces VALUES(?,?,?)').run(keyId,nonce,expires);}
    catch {throw Error('TAP nonce replay refused');}
    return {label:'MOCK',cryptographic_verification:'MEASURED',profile:'RFC9421_ED25519_AGENT_RECOGNITION_WITH_BODY_DIGEST',
      signature_verified:true,intent_verified:true,replay_protected:true,identity_trust:entry.trust_source,
      visa_approved_agent:false,visa_credentials_verified:false,full_tap_payment_containers_verified:false,
      intent:{job_id:intent.job_id,intent:intent.intent,currency:intent.currency,amount_minor:intent.amount_minor},
      payments_sent:0};
  }
}
