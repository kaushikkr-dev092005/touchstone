/* Private loopback UI. No private key, trusted-address enrollment or auto-signing. */
(() => {
  'use strict';
  const node = id => document.getElementById('approval-' + id);
  const token = document.querySelector('meta[name="touchstone-token"]').content;
  let approvals = [], current = null;
  const short = s => s ? s.slice(0, 10) + '…' + s.slice(-8) : '—';
  async function api(path, body) {
    const response = await fetch('/api/procurement/' + path, {
      method: body ? 'POST' : 'GET',
      headers: {'Content-Type':'application/json','X-Touchstone-Token':token},
      ...(body ? {body:JSON.stringify(body)} : {})
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.code || result.error || 'APPROVAL_REQUIRED');
    return result;
  }
  function render() {
    const t = current?.terms;
    node('fields').replaceChildren();
    node('state').textContent = current?.state || 'UNSIGNED · BLOCKED';
    node('state').className = 'badge ' + (current?.state === 'SIGNED' ? 'measured' : 'blocked');
    node('digest').textContent = short(current?.digest);
    if (t) {
      const fields = [
        ['Task', t.step_id], ['Task description', current.task ? current.task.kind+' · '+JSON.stringify(current.task.source) : 'See canonical task hash'], ['Task hash', short(t.task_hash)], ['Provider', t.provider_id + ' · ' + t.provider_origin],
        ['Quote', t.quote_id], ['Quoted amount', (t.quoted_amount/1e6).toFixed(6)+' '+t.currency],
        ['Maximum purchase', (t.max_amount/1e6).toFixed(6)+' '+t.currency],
        ['Remaining job budget', (t.job_ceiling-t.spent)+' micro-USD (ledger accounting)'],
        ['Allocation', (t.allocation/1e6).toFixed(6)+' '+t.allocation_currency],
        ['API-credit limit', (t.api_credit_max/1e6).toFixed(6)+' '+t.api_credit_currency],
        ['Checking fee', t.fee_max+' micro-USD (ledger accounting)'],
        ['Verifier criteria', t.verifier_version+' · min quality '+(current.task?.min_quality ?? 'see policy')+' · '+short(t.verifier_policy_digest)],
        ['Approval expires', new Date(t.expires_at*1000).toLocaleString()], ['Trusted signer', short(current.expected_signer)]
      ];
      for (const [label,value] of fields) {
        const dl=document.createElement('dl'), dt=document.createElement('dt'), dd=document.createElement('dd');
        dt.textContent=label; dd.textContent=value; dl.append(dt,dd);node('fields').append(dl);
      }
      node('scope').textContent = t.currency === 'MOCK_USD'
        ? 'MOCK / LOCAL TEST · No external payment or inference. Human wallet signing is real. Review the task and exact terms below.'
        : 'LIVE PROPOSAL · Review the complete typed data in your separate wallet. Signing does not waive existing funding and spending restrictions.';
    }
    node('sign').disabled = !current || current.state !== 'PENDING_APPROVAL';
    node('verify').disabled = !current?.signature;
    node('reject').disabled = !current || !['PENDING_APPROVAL','SIGNED'].includes(current.state);
    node('dispatch').disabled = !t || t.currency !== 'MOCK_USD' || current.state !== 'SIGNED';
    node('tamper').disabled = !current?.signature;
  }
  async function refresh(id) {
    const result = await api('approvals');
    approvals = result.approvals;
    node('select').replaceChildren();
    for (const a of approvals) {
      const option=document.createElement('option');option.value=a.id;
      option.textContent=a.terms.step_id+' · '+a.state+' · '+short(a.digest);node('select').append(option);
    }
    current=approvals.find(a=>a.id===(id || current?.id)) || approvals[0] || null;
    if (current) node('select').value=current.id;
    render();
  }
  async function action(callback) {
    try { await callback(); }
    catch(error) { node('message').textContent='BLOCKED · '+error.message; }
  }
  node('select').onchange=()=>{current=approvals.find(a=>a.id===node('select').value);render();};
  node('proposal').onclick=()=>action(async()=>{
    const a=await api('local-proposal',{});await refresh(a.id);
    node('message').textContent='UNSIGNED · APPROVAL_REQUIRED. No payment dispatched. Review exact terms before signing.';
  });
  node('sign').onclick=()=>action(async()=>{
    if (!current || !window.ethereum?.request) throw Error('Connect an EIP-1193 human wallet; keys stay in the wallet.');
    const a=current, accounts=await window.ethereum.request({method:'eth_requestAccounts'});
    if (!accounts.some(x=>x.toLowerCase()===a.expected_signer.toLowerCase())) throw Error('SIGNER_UNTRUSTED');
    const chain=await window.ethereum.request({method:'eth_chainId'});
    if (BigInt(chain)!==BigInt(a.typed_data.domain.chainId)) throw Error('Wallet network differs from the signed domain. Select the configured network.');
    // Wallet receives the entire backend-generated message, never a display-only digest.
    const data={...a.typed_data,types:{...a.typed_data.types,EIP712Domain:[
      {name:'name',type:'string'},{name:'version',type:'string'},{name:'chainId',type:'uint256'},{name:'salt',type:'bytes32'}]}};
    const signature=await window.ethereum.request({method:'eth_signTypedData_v4',params:[a.expected_signer,JSON.stringify(data)]});
    await api('submit-signature',{id:a.id,signature});await refresh(a.id);
    node('message').textContent='SIGNED · Backend EIP-712 verification passed. Existing financial controls still apply.';
  });
  node('verify').onclick=()=>action(async()=>{
    const proof=await api('verify-terms',{id:current.id,terms:current.terms});
    node('message').textContent='SIGNED · Signature and exact terms verified; no payment dispatched.';
    node('proof').hidden=false;node('proof').textContent=JSON.stringify(proof,null,2);
  });
  node('reject').onclick=()=>action(async()=>{await api('revoke-approval',{id:current.id});await refresh();node('message').textContent='REVOKED · New dispatch blocked.';});
  node('copy').onclick=()=>action(async()=>{if(current)await navigator.clipboard.writeText(current.digest);});
  node('audit').onclick=()=>action(async()=>{
    const response=await fetch('/api/audit'), audit=await response.json();
    node('proof').hidden=false;node('proof').textContent=JSON.stringify({approval:current,audit},null,2);
  });
  node('tamper').onclick=()=>action(async()=>{
    const terms={...current.terms,provider_id:'tampered-provider'};
    try { await api('verify-terms',{id:current.id,terms});throw Error('Unexpected acceptance'); }
    catch(error) {
      if(error.message!=='TERMS_MISMATCH')throw error;
      node('state').textContent='TAMPERED · BLOCKED';
      node('message').textContent='TAMPERED · TERMS_MISMATCH. Original approval and purchase remain unchanged; no payment dispatched.';
    }
  });
  node('dispatch').onclick=()=>action(async()=>{
    const result=await api('dispatch-mock',{id:current.id});await refresh();
    node('message').textContent=result.mode+' · '+result.job_status+' · '+result.external_financial_calls+' external financial calls.';
  });
  refresh().catch(error=>{node('message').textContent='BLOCKED · '+error.message;render();});
})();
