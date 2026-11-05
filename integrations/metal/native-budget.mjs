export function gasCappedAccount(account, db, maximumWei) {
  if (typeof maximumWei !== 'string' || !/^[1-9][0-9]{0,30}$/.test(maximumWei)) throw Error('Positive native fee cap in wei required');
  const maximum = BigInt(maximumWei);
  const key = 'deposit_native_gas_budget';
  const previous = db.prepare('SELECT value FROM settings WHERE key=?').get(key);
  if (previous && JSON.parse(previous.value).maximum_wei !== maximumWei) throw Error('Native fee cap is already bound');
  if (!previous) db.prepare('INSERT INTO settings VALUES(?,?)').run(key, JSON.stringify({ maximum_wei: maximumWei, reserved_wei: '0' }));
  return { ...account, async signTransaction(transaction, ...rest) {
    if (transaction.chainId !== 63825) throw Error('Native fee budget is restricted to testnet chain 63825');
    if (typeof transaction.gas !== 'bigint' || transaction.gas <= 0n ||
        typeof transaction.maxFeePerGas !== 'bigint' || transaction.maxFeePerGas < 0n ||
        (transaction.value ?? 0n) !== 0n) throw Error('Native fee exposure cannot be bounded');
    const exposure = transaction.gas * transaction.maxFeePerGas;
    db.exec('BEGIN IMMEDIATE');
    try {
      const budget = JSON.parse(db.prepare('SELECT value FROM settings WHERE key=?').get(key).value);
      const reserved = BigInt(budget.reserved_wei) + exposure;
      if (reserved > maximum) throw Error('Aggregate native fee cap exceeded; transaction not signed');
      budget.reserved_wei = reserved.toString();
      db.prepare('UPDATE settings SET value=? WHERE key=?').run(JSON.stringify(budget), key);
      db.exec('COMMIT');
    } catch (error) { db.exec('ROLLBACK'); throw error; }
    // Reserve the full signed ceiling durably, including definitive reverted transactions.
    return account.signTransaction(transaction, ...rest);
  } };
}
