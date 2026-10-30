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
  if (!task || typeof task.id !== 'string' || task.id.length > 80 || !['invoice','arithmetic','classification'].includes(task.kind) ||
      typeof task.source !== 'object' || task.source === null || Array.isArray(task.source) ||
      Object.keys(task).some(k => !['id','kind','source','min_quality'].includes(k))) throw Error('Invalid task');
  return { key: match[1], task };
}

export class DeliveryStore {
  constructor(db) {
    this.db = db;
    db.exec(`CREATE TABLE IF NOT EXISTS deliveries(
      payment_id TEXT PRIMARY KEY, resource TEXT NOT NULL, receipt_digest TEXT NOT NULL,
      state TEXT NOT NULL, output TEXT);`);
  }
  async deliver(paymentId, resource, receiptDigest, perform) {
    let row = this.db.prepare('SELECT * FROM deliveries WHERE payment_id=?').get(paymentId);
    if (row) {
      if (row.resource !== resource || row.receipt_digest !== receiptDigest) throw Error('Receipt already belongs to another resource');
      if (row.state === 'DELIVERED') return JSON.parse(row.output);
      // A restart after model execution but before persistence may repeat CPU
      // inference; it does not charge another payment or duplicate a bank action.
    } else {
      this.db.prepare("INSERT INTO deliveries VALUES(?,?,?,'RUNNING',NULL)").run(paymentId, resource, receiptDigest);
    }
    const output = await perform();
    this.db.prepare("UPDATE deliveries SET state='DELIVERED',output=? WHERE payment_id=?").run(JSON.stringify(output), paymentId);
    return output;
  }
}
