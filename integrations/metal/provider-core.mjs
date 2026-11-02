import { createHash } from 'node:crypto';

export function decodeResource(path) {
  const parsed = new URL(path, 'http://localhost');
  const match = /^\/inference\/([a-f0-9]{64})$/.exec(parsed.pathname);
  const value = parsed.searchParams.get('task');
  if (!match || !value || value.length > 16000 || !/^[A-Za-z0-9_-]+$/.test(value) ||
      [...parsed.searchParams.keys()].length !== 1) throw Error('Invalid resource');
  const bytes = Buffer.from(value, 'base64url');
  if (createHash('sha256').update(bytes).digest('hex') !== match[1]) throw Error('Task digest mismatch');
  const task = JSON.parse(bytes.toString('utf8'));
  if (!task || typeof task.id !== 'string' || task.id.length > 80 || !['invoice','arithmetic','classification','invoice_consistency'].includes(task.kind) ||
      typeof task.source !== 'object' || task.source === null || Array.isArray(task.source) ||
      Object.keys(task).some(k => !['id','kind','source','min_quality'].includes(k))) throw Error('Invalid task');
  return { key: match[1], task };
}

export class DeliveryStore {
  constructor(db) {
    this.db = db;
    db.exec(`CREATE TABLE IF NOT EXISTS deliveries(
      payment_id TEXT PRIMARY KEY, resource TEXT NOT NULL, receipt_digest TEXT NOT NULL,
      state TEXT NOT NULL, output TEXT);
      CREATE TABLE IF NOT EXISTS quote_offers(
      resource TEXT NOT NULL, digest TEXT NOT NULL, offer TEXT NOT NULL,
      expires_at INTEGER NOT NULL, queue_depth INTEGER NOT NULL, latency_ms INTEGER NOT NULL,
      PRIMARY KEY(resource,digest));`);
  }
  rememberQuote(resource, offer, expiresAt, queueDepth, latencyMs) {
    const serialized = stableJson(offer);
    const digest = createHash('sha256').update(serialized).digest('hex');
    this.db.prepare('DELETE FROM quote_offers WHERE expires_at < ?').run(Date.now());
    this.db.prepare('INSERT OR REPLACE INTO quote_offers VALUES(?,?,?,?,?,?)')
      .run(resource, digest, serialized, expiresAt, queueDepth, latencyMs);
    return digest;
  }
  findQuote(resource, offer) {
    const serialized = stableJson(offer);
    const digest = createHash('sha256').update(serialized).digest('hex');
    const row = this.db.prepare('SELECT * FROM quote_offers WHERE resource=? AND digest=?').get(resource, digest);
    if (!row || row.expires_at <= Date.now() || row.offer !== serialized) return null;
    return { offer: JSON.parse(row.offer), queue_depth: row.queue_depth, latency_ms: row.latency_ms };
  }
  async deliver(paymentId, resource, receiptDigest, perform, { retryRunning = true } = {}) {
    let row = this.db.prepare('SELECT * FROM deliveries WHERE payment_id=?').get(paymentId);
    if (row) {
      if (row.resource !== resource || row.receipt_digest !== receiptDigest) throw Error('Receipt already belongs to another resource');
      if (row.state === 'DELIVERED') return JSON.parse(row.output);
      if (row.state === 'RUNNING' && !retryRunning) throw Error('Hosted delivery outcome is unknown; refusing a duplicate billable model call');
      // Local CPU/GPU work may be repeated after a crash; hosted billable calls can opt out.
    } else {
      this.db.prepare("INSERT INTO deliveries VALUES(?,?,?,'RUNNING',NULL)").run(paymentId, resource, receiptDigest);
    }
    const output = await perform();
    this.db.prepare("UPDATE deliveries SET state='DELIVERED',output=? WHERE payment_id=?").run(JSON.stringify(output), paymentId);
    return output;
  }
}

export function priceForQueue(basePriceMicroUsd, queueDepth, maxPriceMicroUsd = 50000n) {
  if (typeof basePriceMicroUsd !== 'bigint' || basePriceMicroUsd <= 0n ||
      !Number.isInteger(queueDepth) || queueDepth < 0 ||
      typeof maxPriceMicroUsd !== 'bigint' || maxPriceMicroUsd < basePriceMicroUsd) throw Error('Invalid queue price inputs');
  const surchargePercent = 100n + BigInt(Math.min(queueDepth, 4)) * 20n;
  const adjusted = (basePriceMicroUsd * surchargePercent + 99n) / 100n;
  return (adjusted > maxPriceMicroUsd ? maxPriceMicroUsd : adjusted) * 10n ** 12n;
}

export function qualityDropOutput(task, output) {
  if (!output || typeof output !== 'object' || Array.isArray(output)) return { quality_drop: true };
  const result = structuredClone(output);
  if (task.kind === 'invoice_consistency' && Array.isArray(result.line_items) && result.line_items.length &&
      Number.isInteger(result.line_items[0].line_total_cents) &&
      (result.line_items.length === 1 || Number.isInteger(result.line_items[1].line_total_cents))) {
    result.line_items[0].line_total_cents += 1;
    if (result.line_items.length > 1) result.line_items[1].line_total_cents -= 1;
    return result;
  }
  if (task.kind === 'classification' && ['billing','technical','shipping'].includes(result.label)) {
    result.label = { billing: 'technical', technical: 'shipping', shipping: 'billing' }[result.label];
    return result;
  }
  if (Number.isInteger(result.total_cents)) {
    result.total_cents += 1;
    return result;
  }
  return { quality_drop: true };
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
