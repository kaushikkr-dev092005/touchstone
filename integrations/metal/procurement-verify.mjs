import { verifyApproval } from './procurement-approval.mjs';
let text='';
try {
  for await (const part of process.stdin) { text+=part; if(text.length>150000)throw Error(); }
  const r=JSON.parse(text);
  if(Object.keys(r).sort().join()!==['terms','signature','expected_signer'].sort().join())throw Error();
  console.log(JSON.stringify({ok:true,result:await verifyApproval(r.terms,r.signature,r.expected_signer)}));
} catch(e) { console.log(JSON.stringify({ok:false,code:e.code||'INVALID_SIGNATURE'}));process.exitCode=1; }
