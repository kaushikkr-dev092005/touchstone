// Read-only discovery + quote. No wallet opening, key, funding or pay capability.
import { discover, quote } from './adapter.mjs';
let input = '';
try {
  for await (const chunk of process.stdin) {
    input += chunk;
    if (input.length > 32768) throw Error('INPUT_TOO_LARGE');
  }
  const request = JSON.parse(input);
  if (Object.keys(request).sort().join(',') !== 'maximum_micro_usdz,url' ||
      !Number.isSafeInteger(request.maximum_micro_usdz) || request.maximum_micro_usdz <= 0) throw Error('INVALID_QUOTE_REQUEST');
  const deployment = await discover();
  const result = await quote(request.url, deployment, BigInt(request.maximum_micro_usdz) * 10n ** 12n);
  process.stdout.write(JSON.stringify(result));
} catch {
  process.stdout.write(JSON.stringify({ error: 'PROVIDER_QUOTE_UNAVAILABLE' }));
  process.exitCode = 1;
}
