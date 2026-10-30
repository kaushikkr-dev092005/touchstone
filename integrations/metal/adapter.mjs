import * as sdk from '@metalntwx/metal-pay';
import { createPublicClient, http } from 'viem';
import { privateKeyToAccount, generatePrivateKey } from 'viem/accounts';
import { openWallet } from './wallet.mjs';
import { encodePaymentSignatureHeader, readLimitedText } from '@x402/core/http';

export const NETWORK = 'eip155:63825';
const UNIT = 10n ** 12n;
const token = sdk.USDZ.address.toLowerCase();
const json = value => JSON.stringify(value, (_, v) => typeof v === 'bigint' ? v.toString() : v);

export function amount(value) {
  if (typeof value !== 'string' || !/^\d+(?:\.\d{1,6})?$/.test(value)) throw Error('Use a nonnegative decimal string with at most six places');
  return BigInt(sdk.usdzBaseUnits(value));
}

export function resourceUrl(value) {
  const url = new URL(value);
  if (url.username || url.password || url.hash || (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost','127.0.0.1','[::1]'].includes(url.hostname)))) throw Error('Provider URL must use HTTPS or loopback HTTP, with no credentials or fragment');
  return url.href;
}

export async function discover(fetcher = fetch) {
  const response = await fetcher(sdk.METAL_NETWORKS.testnet.facilitatorUrl + '/supported', { redirect: 'error', signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw Error('Metal facilitator discovery failed');
  const result = await response.json();
  const kind = result.kinds?.find(k => k.x402Version === 2 && k.scheme === 'bajillion' && k.network === NETWORK && k.extra?.asset?.toLowerCase() === token);
  if (!kind || !/^0x[0-9a-fA-F]{40}$/.test(kind.extra?.settlement || '')) throw Error('Facilitator advertises no supported testnet USDZ clearing deployment');
  const serviceUrl = resourceUrl(kind.extra.serviceUrl);
  if (new URL(serviceUrl).protocol !== 'https:') throw Error('Remote clearing service must use HTTPS');
  return { network: NETWORK, asset: sdk.USDZ.address, settlement: kind.extra.settlement,
    serviceUrl: serviceUrl.replace(/\/$/, ''), validatorUrls: kind.extra.validatorUrls || [] };
}

export function approvedOffer(header, deployment, maximum) {
  let packet;
  try { packet = JSON.parse(Buffer.from(header || '', 'base64').toString('utf8')); } catch { throw Error('Malformed PAYMENT-REQUIRED header'); }
  if (packet.x402Version !== 2) throw Error('Only x402 v2 is supported');
  const candidates = (packet.accepts || []).filter(q => q.scheme === 'bajillion' && q.network === NETWORK && q.asset?.toLowerCase() === token
    && q.extra?.settlement?.toLowerCase() === deployment.settlement.toLowerCase() && q.extra?.serviceUrl?.replace(/\/$/,'') === deployment.serviceUrl);
  const offer = candidates.find(q => /^\d+$/.test(q.amount || '') && BigInt(q.amount) > 0n && BigInt(q.amount) <= maximum && BigInt(q.amount) % UNIT === 0n);
  if (!offer) throw Error('No clearing quote fits the approved network, deployment, asset and price cap');
  // Let the SDK additionally validate the P-256 seller key and invoice namespace.
  sdk.clearingInvoice(offer, offer.extra?.invoicePrefix + ':touchstone-quote-validation');
  return offer;
}

const termsKey = q => json({ url: q.url, amount: q.offer.amount, payTo: q.offer.payTo,
  network: q.offer.network, asset: q.offer.asset, extra: q.offer.extra });

async function retrieveDelivery(terms, paid) {
  if (!paid) throw Error('No original paid proof');
  const signature = encodePaymentSignatureHeader({ x402Version: 2, payload: paid,
    accepted: terms.offer, resource: { url: terms.url, mimeType: 'application/json' } });
  const response = await fetch(terms.url, { headers: { 'PAYMENT-SIGNATURE': signature },
    redirect: 'error', signal: AbortSignal.timeout(30000) });
  if (!response.ok) return null;
  return { ok: true, status: response.status, body: JSON.parse(await readLimitedText(response, 1000000)) };
}

export async function quote(url, deployment, maximum, fetcher = fetch) {
  url = resourceUrl(url);
  const response = await fetcher(url, { redirect: 'error', signal: AbortSignal.timeout(20000) });
  if (response.status !== 402) throw Error('Provider did not return a 402 challenge');
  const offer = approvedOffer(response.headers.get('PAYMENT-REQUIRED'), deployment, maximum);
  return { url, offer, expires_at: Date.now() + 30000 };
}

function purchase(wallet, id) {
  const row = wallet.db.prepare('SELECT * FROM purchases WHERE id=?').get(id);
  return row ? { ...row, terms: JSON.parse(row.terms), before_ids: JSON.parse(row.before_ids), result: row.result ? JSON.parse(row.result) : null } : null;
}

function invoiceMatches(offer, invoice) {
  try {
    const expected = sdk.clearingInvoice(offer, invoice.id);
    return ['id','network','amount'].every(k => invoice[k] === expected[k]) &&
      ['asset','settlement','recipient'].every(k => invoice[k]?.toLowerCase() === expected[k]?.toLowerCase());
  } catch { return false; }
}

async function newReceipt(wallet, row) {
  const state = await wallet.store.load();
  const found = Object.entries(state?.payments || {}).filter(([id]) => !row.before_ids.includes(id));
  if (found.length > 1) throw Error('More than one receipt appeared during a serialized purchase; reconciliation required');
  if (!found.length) return null;
  const [id, paid] = found[0];
  if (!invoiceMatches(row.terms.offer, paid.invoice)) throw Error('Receipt differs from the reserved invoice terms');
  return { id, invoice: paid.invoice, receipt: paid.receipt, invoice_signature: paid.invoiceSignature ?? null,
    entries: paid.entries ?? [], previous: paid.previous ?? null, status: 'preconfirmed', transaction: null };
}

export async function recoverPurchase(wallet, id, clearing, retrieve = null) {
  const row = purchase(wallet, id);
  if (!row) throw Error('Unknown reservation ID');
  if (row.state === 'DELIVERED') return row.result;
  if (row.state === 'PAID_OUTPUT_MISSING' && !retrieve) return row.result;
  const state = await wallet.store.load();
  if (state?.pending) {
    if (state.pending.url !== row.terms.url || !invoiceMatches(row.terms.offer, state.pending.invoice)) throw Error('Pending SDK invoice is not this reserved request');
    // The SDK resends the held invoice itself, never a fresh invoice at a new provider.
    await clearing.pay(state.pending.invoice, state.pending.url);
  }
  const receipt = await newReceipt(wallet, row);
  if (!receipt) {
    const current = await wallet.store.load();
    const ids = Object.keys(current?.payments || {});
    if (!current?.pending && ids.length === row.before_ids.length && ids.every(x => row.before_ids.includes(x))) {
      // In the pinned SDK, pay durably stores pending BEFORE its first send.
      // It clears pending only after a verified receipt or authoritative refusal.
      // Thus this is local protocol evidence, not an empty remote lookup.
      const result = { mode: 'TESTNET', state: 'UNPAID_CONFIRMED', receipt: null, output: null,
        next_action: 'Retry this same reservation and identical offer; the SDK retains no possible charge' };
      wallet.db.prepare("UPDATE purchases SET state='UNPAID_CONFIRMED',result=? WHERE id=?").run(json(result), id);
      return result;
    }
    throw Error('Payment remains unconfirmed; reservation retained. Do not create a replacement purchase');
  }
  const result = { mode: 'TESTNET', state: 'PAID_OUTPUT_MISSING', receipt, output: null,
    next_action: 'Retrieve original delivery from the provider by receipt; no replacement payment was sent' };
  wallet.db.prepare("UPDATE purchases SET state='PAID_OUTPUT_MISSING',result=? WHERE id=?").run(json(result), id);
  if (retrieve) {
    try {
      const paid = (await wallet.store.load())?.payments?.[receipt.id];
      const output = await retrieve(row.terms, paid);
      if (output?.ok) {
        const delivered = { ...result, state: 'DELIVERED', output, next_action: 'none' };
        wallet.db.prepare("UPDATE purchases SET state='DELIVERED',result=? WHERE id=?").run(json(delivered), id);
        return delivered;
      }
    } catch { /* Retain the real receipt and missing delivery; never create another payment. */ }
  }
  return result;
}

export async function executePurchase(wallet, id, q, budget, perform) {
  if (!/^[A-Za-z0-9_-]{1,80}$/.test(id)) throw Error('Invalid reservation ID');
  const prior = purchase(wallet, id);
  if (prior) {
    if (termsKey(prior.terms) !== termsKey(q)) throw Error('Idempotency conflict: reserved purchase terms changed');
    if (prior.state === 'DELIVERED' || prior.state === 'PAID_OUTPUT_MISSING') return prior.result;
    if (prior.state !== 'UNPAID_CONFIRMED') throw Error('Existing purchase requires recover; no new request dispatched');
  }
  if (Date.now() >= q.expires_at) throw Error('Quote expired before reservation');
  const blocked = wallet.db.prepare("SELECT id FROM purchases WHERE state IN ('RESERVED','UNKNOWN','PAID_OUTPUT_MISSING')").get();
  if (blocked) throw Error('Wallet has an unresolved purchase or missing delivery; reconcile before another purchase');
  const state = await wallet.store.load();
  if (state?.pending) throw Error('SDK has an unresolved invoice; recover it before another purchase');
  const payments = state?.payments || {};
  const spent = Object.values(payments).reduce((s,p) => s + BigInt(p.invoice.amount), 0n);
  if (spent + BigInt(q.offer.amount) > budget) throw Error('Job payment budget exhausted');
  if (prior) wallet.db.prepare("UPDATE purchases SET terms=?,before_ids=?,state='RESERVED',result=NULL WHERE id=?").run(json(q), json(Object.keys(payments)), id);
  else wallet.db.prepare('INSERT INTO purchases VALUES(?,?,?,?,NULL)').run(id, json(q), json(Object.keys(payments)), 'RESERVED');
  const row = purchase(wallet, id);
  try {
    const output = await perform();
    const receipt = await newReceipt(wallet, row);
    if (!receipt) throw Error('Provider response arrived without a durable clearing receipt');
    const result = { mode: 'TESTNET', state: output.ok ? 'DELIVERED' : 'PAID_OUTPUT_MISSING', receipt, output };
    wallet.db.prepare('UPDATE purchases SET state=?,result=? WHERE id=?').run(result.state, json(result), id);
    return result;
  } catch {
    wallet.db.prepare("UPDATE purchases SET state='UNKNOWN' WHERE id=?").run(id);
    throw Error('Purchase outcome requires recovery; do not pay again or reroute');
  }
}

export async function connectJob(config) {
  if (!config.rpcUrl) throw Error('Set METAL_RPC_URL to your testnet RPC endpoint');
  if (!config.providerUrl) throw Error('Set METAL_PROVIDER_URL to an approved provider resource');
  const approvedUrl = resourceUrl(config.providerUrl);
  const publicClient = createPublicClient({ transport: http(config.rpcUrl, { retryCount: 0, timeout: 15000 }) });
  try { if (await publicClient.getChainId() !== 63825) throw Error('wrong chain'); }
  catch { throw Error('RPC must be reachable and report testnet chain 63825; endpoint details hidden'); }
  const deployment = await discover();
  const wallet = openWallet(config.directory);
  try {
    wallet.bindDeployment(deployment);
    const maximum = amount(config.maxPrice || '0.05');
    const budget = amount(config.budget || '0.50');
    if (!maximum || !budget || maximum > budget) throw Error('Price cap and budget must be positive and consistent');
    const clearing = sdk.createClearingClient({ ...deployment, rpcUrl: config.rpcUrl, signer: wallet.signer, store: wallet.store, maxAmount: maximum });
    return { wallet, deployment, clearing,
      async quote() { return quote(approvedUrl, deployment, maximum); },
      async buy(id, reservedQuote = null) {
        const existing = purchase(wallet, id);
        if (existing && existing.terms.url !== approvedUrl) throw Error('Idempotency conflict: provider resource changed');
        // A completed retry returns its exact original result without fetching a fresh quote.
        if (existing?.state === 'DELIVERED' || existing?.state === 'PAID_OUTPUT_MISSING') return existing.result;
        if (existing && existing.state !== 'UNPAID_CONFIRMED') throw Error('Existing reservation must be recovered before requesting any new quote');
        const q = reservedQuote || await quote(approvedUrl, deployment, maximum);
        if (q.url !== approvedUrl || Date.now() >= q.expires_at) throw Error('Reserved quote changed URL or expired');
        const checked = approvedOffer(Buffer.from(json({ x402Version: 2, accepts: [q.offer] })).toString('base64'), deployment, maximum);
        if (termsKey({url: approvedUrl, offer: checked}) !== termsKey(q)) throw Error('Reserved quote terms differ');
        const guardedFetch = async (input, init = {}) => {
          const url = resourceUrl(typeof input === 'string' ? input : input.url || input.href);
          if (url !== approvedUrl) throw Error('Payment resource changed');
          const response = await fetch(input, { ...init, redirect: 'error', signal: AbortSignal.timeout(30000) });
          if (response.status === 402) {
            const offer = approvedOffer(response.headers.get('PAYMENT-REQUIRED'), deployment, maximum);
            if (termsKey({url,offer}) !== termsKey(q)) throw Error('Offer changed; a fresh quote and reservation are required');
          }
          return response;
        };
        // An unfunded ephemeral EVM signer and a zero exact cap prevent spending the owner's EVM wallet as a fallback.
        const client = sdk.createMetalPaymentClient({ account: privateKeyToAccount(generatePrivateKey()), network: 'testnet', maxAmount: 0n, fetch: guardedFetch });
        sdk.registerClearingClient(client.client, NETWORK, clearing, { exactFallback: false });
        return executePurchase(wallet, id, q, budget, async () => {
          const response = await client.fetchWithPayment(approvedUrl, { redirect: 'error' });
          const text = await readLimitedText(response, 1000000);
          let body;
          try { body = JSON.parse(text); } catch { body = { text }; }
          return { ok: response.ok, status: response.status, body };
        });
      },
      recover(id) { return recoverPurchase(wallet, id, clearing, async (terms, paid) => {
        if (!paid || terms.url !== approvedUrl) throw Error('No original delivery proof');
        // Re-present the already-paid SDK receipt. This plain fetch never invokes
        // fetchWithPayment, so another 402 cannot cause a replacement purchase.
        return retrieveDelivery(terms, paid);
      }); },
      async replayDelivery(id) {
        const row = purchase(wallet, id);
        if (!row || row.terms.url !== approvedUrl || !row.result?.receipt) throw Error('No paid original resource');
        const paid = (await wallet.store.load())?.payments?.[row.result.receipt.id];
        return retrieveDelivery(row.terms, paid);
      },
      close() { wallet.close(); },
    };
  } catch (error) { wallet.close(); throw error; }
}

export async function deposit(config, dollars) {
  const client = await connectJob(config);
  try {
    if (!/^0x[0-9a-fA-F]{64}$/.test(config.privateKey || '')) throw Error('Set AGENT_PRIVATE_KEY locally to your funded testnet key');
    const value = amount(dollars);
    if (value <= 0n || value > amount(config.budget || '0.50')) throw Error('Deposit must fit the configured job budget');
    // Journal before deposit. An unknown chain outcome is never blindly rebroadcast.
    const prior = client.wallet.db.prepare("SELECT value FROM settings WHERE key='deposit'").get();
    if (prior) throw Error('This wallet already has a deposit record; inspect its transaction before any further deposit');
    client.wallet.db.prepare("INSERT INTO settings VALUES('deposit',?)").run(json({ state: 'IN_FLIGHT', amount: value }));
    const result = await sdk.depositToClearing({ rpcUrl: config.rpcUrl, chainId: 63825,
      from: privateKeyToAccount(config.privateKey), settlement: client.deployment.settlement,
      asset: sdk.USDZ.address, account: client.wallet.signer.publicKey, amount: value });
    client.wallet.db.prepare("UPDATE settings SET value=? WHERE key='deposit'").run(json({ state: 'BROADCAST', amount: value, ...result }));
    return { mode: 'TESTNET', ...result, spendable_confirmed: false };
  } finally { client.close(); }
}

export async function withdraw(config) {
  const client = await connectJob(config);
  try {
    if (!/^0x[0-9a-fA-F]{64}$/.test(config.privateKey || '')) throw Error('Set AGENT_PRIVATE_KEY locally to your funded testnet key');
    const result = await sdk.withdrawFromClearing({ rpcUrl: config.rpcUrl, chainId: 63825,
      from: privateKeyToAccount(config.privateKey), settlement: client.deployment.settlement,
      signer: client.wallet.signer, serviceUrl: client.deployment.serviceUrl });
    return { mode: 'TESTNET', ...result, returned_float_confirmed: result.status === 'sent' && result.claimed.some(c => !c.deferred) };
  } finally { client.close(); }
}
