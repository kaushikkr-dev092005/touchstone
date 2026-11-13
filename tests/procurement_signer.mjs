// Test-only subprocess. Keys never leave process memory or enter committed data.
import { generatePrivateKey, privateKeyToAccount } from '../integrations/metal/node_modules/viem/_esm/accounts/index.js';
import { createInterface } from 'node:readline';
const accounts=Array.from({length:3},()=>privateKeyToAccount(generatePrivateKey()));
console.log(JSON.stringify({addresses:accounts.map(a=>a.address)}));
for await(const line of createInterface({input:process.stdin})) {
  try {
    const r=JSON.parse(line);
    if(!r.data?.message?.environment?.startsWith('LOCAL_TEST'))throw Error('Test domain only');
    console.log(JSON.stringify({signature:await accounts[r.account??0].signTypedData(r.data)}));
  } catch { console.log(JSON.stringify({error:'TEST_SIGNING_REFUSED'})); }
}
