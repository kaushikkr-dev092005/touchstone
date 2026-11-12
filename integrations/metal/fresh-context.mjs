// Transport wait for an unsigned, free context GET. Never repeats a POST or inference request.
// The unchanged SDK still verifies deployment, chain context and operator signatures.
export function freshContextFetch(original,{wait=ms=>new Promise(resolve=>setTimeout(resolve,ms)),now=Date.now}={}){
return async function(input,init){
 const url=new URL(typeof input==='string'?input:input.url||input.href);
 const method=init?.method||input?.method||'GET';
 let response=await original(input,init);
 if(method!=='GET'||url.protocol!=='https:'||url.pathname!=='/context'||![200,409].includes(response.status))return response;
 const first=response.status===200?await response.clone().json().catch(()=>null):null;
 const epoch=first?.epoch;
 const deadline=now()+20000;
 while(now()<deadline){
  await wait(700);
  response=await original(input,init);
  if(response.status===200){
   const context=await response.clone().json().catch(()=>null);
   if(context?.epoch&&(!epoch||context.epoch!==epoch))return response;
  }else if(response.status!==409)return response;
 }
 return response;
};
}
globalThis.fetch=freshContextFetch(globalThis.fetch);
