// Anonymous saved-evidence renderer. No operator API, wallet, SSE or mutation code.
const $ = id => document.getElementById(id);
const text = (id, value) => { if ($(id)) $(id).textContent = value; };
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const amount = (value, currency = 'USDZ') => Number.isFinite(value) ? (value / 1e6).toFixed(6) + ' ' + currency : 'Unreported';
const cell = value => '<td>' + esc(value) + '</td>';
const table = (id, rows, columns = 5) => { if ($(id)) $(id).innerHTML = rows.length ? rows.map(row => '<tr>' + row.map(cell).join('') + '</tr>').join('') : `<tr><td colspan="${columns}">No published evidence for this panel.</td></tr>`; };
const disabled = ['start','halt','resume','close','hero-demo','failed-call-policy','refresh-fx','refresh-issuing','live-quote','live-run',
  'approval-proposal','approval-sign','approval-verify','approval-reject','approval-tamper','approval-dispatch','approval-select','approval-copy'];
for (const id of disabled) if ($(id)) { $(id).disabled = true; $(id).title = 'Read-only public evidence. Use the secured local operator console.'; }
document.querySelectorAll('#mandate-increase-form input,#mandate-increase-form button').forEach(el => el.disabled = true);
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', event => event.preventDefault()));
document.querySelectorAll('[data-mode-tag]').forEach(el => { el.textContent = 'Saved evidence'; el.className = 'tag'; });
text('connection', 'SAVED EVIDENCE · READ ONLY');
document.querySelector('.conn').title='Historical saved evidence; no live event stream';
document.querySelector('.crumbs li').textContent='Saved dashboard';
document.querySelector('#v-overview .page-head p').textContent='Published sandbox / testnet observations · no current private account access';
document.querySelector('#v-integrations .page-head p').textContent='Historical integration evidence · current readiness requires a private read check';
for(const [id,message] of Object.entries({'airwallex-ready':'Saved sandbox hold, capture, FX and card evidence. No current account credentials are exposed.', 'metal-ready':'Saved measured testnet receipts. No public payer key, wallet balance or live provider connection.', 'inference-ready':'Saved model qualification. New purchases require current eligibility and signed authorization.'})) text(id,message);
document.querySelector('.kpi #spent').closest('.kpi').querySelector('.kpi-foot span').textContent='Confirmed provider charges only · USDZ';
document.querySelector('.kpi #accepted').closest('.kpi').querySelector('.kpi-foot span').textContent='Strictly correct drafts · human review required';
document.querySelector('.kpi #unit-cost').closest('.kpi').querySelector('.kpi-foot span').textContent='Historical customer capture · fiat USD';
document.querySelector('#activity').closest('.card').querySelector('.card-head > :last-child').textContent='Saved only';
text('approval-scope', 'Public read-only view. Signing and payment dispatch are available only through the secured operator console. Historical purchases are not relabelled human-signed.');
text('approval-message', 'No approval or payment can be submitted from this public view.');
text('gpu-badge', 'NO LIVE DEVICE CONNECTION');
text('gpu-values', 'Public hosting has no connection to the operator GPU. No current temperature or capacity is inferred.');
text('gpu-calibration', 'Saved model measurements appear under Evidence. They do not qualify a new purchase.');
text('tap-status', 'Visa approval remains pending. Local signed-intent verification is not Visa agent registration.');
text('flow-title', 'Saved receipts at each boundary');
document.querySelector('#flow .tag').textContent = 'Historical · read only';
document.querySelector('#flow > p')?.replaceChildren(document.createTextNode('Inspect saved sandbox and testnet observations. No live event stream or current customer hold is claimed. Fiat USD and token USDZ remain separate.'));
text('run-id', 'SAVED OBSERVATIONS');
text('audit-status', 'NOT A LIVE AUDIT');
text('audit-head', 'Inspect the original hash-chained records in the repository.');
text('float-note', 'Current wallet balance is not published');
text('float', 'Unmeasured');
text('reconciliation', 'Original receipts and measured comparison totals are retained under Evidence. This public view does not reconcile a current private ledger.');
text('pnl-values', 'Public historical observations do not establish current profit, reserves or balances.');
text('jobs', 'The private operator job database is not published. Inspect the recorded attempts under Transactions.');
text('activity', 'Saved evidence only. No live backend event stream is connected.');
text('notice', 'READ ONLY · Saved sandbox/testnet observations. No new inference, bank operation, approval or payment is available here.');
$('notice')?.classList.remove('hidden');
for (const link of document.querySelectorAll('a[href="#intro"]')) link.href = '/site/';

// The layout, cards, icons and navigation come directly from the canonical console.
function route(hash = location.hash) {
  let target;
  try { target = document.getElementById(decodeURIComponent(hash.replace(/^#/, ''))); } catch { return; }
  const view = target?.closest('.view') || $('v-overview');
  document.querySelectorAll('.view').forEach(el => el.classList.toggle('is-active', el === view));
  document.querySelectorAll('[data-nav]').forEach(el => el.dataset.nav === view.dataset.view ? el.setAttribute('aria-current','page') : el.removeAttribute('aria-current'));
  text('crumb-current', view.dataset.title);
}
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  if (!link || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
  event.preventDefault(); history.pushState(null, '', link.hash); route();
});
window.addEventListener('popstate', () => route());
window.addEventListener('hashchange', () => route());
$('nav-back').onclick = () => history.back(); $('nav-forward').onclick = () => history.forward();
const nav = [...document.querySelectorAll('.rail-item[data-nav]')];
document.querySelector('.rail-nav').addEventListener('keydown', event => {
  const index = nav.indexOf(document.activeElement);
  if (index < 0 || !['ArrowDown','ArrowUp','ArrowRight','ArrowLeft'].includes(event.key)) return;
  event.preventDefault(); nav[(index + (['ArrowDown','ArrowRight'].includes(event.key) ? 1 : -1) + nav.length) % nav.length].focus();
});
route();

async function saved(path) {
  const response = await fetch(path, {credentials:'omit'});
  if (!response.ok) throw Error('Saved evidence unavailable');
  return response.json();
}

try {
  const [evidence, reports] = await Promise.all([saved('/site/data/evidence.json'), saved('/site/dashboard/reports.json')]);
  if (reports.scope !== 'SAVED_PUBLIC_EVIDENCE') throw Error('Unsupported evidence scope');
  const records = evidence.records;
  $('approval-audit').onclick=()=>{const proof=$('approval-proof');proof.hidden=false;proof.textContent=JSON.stringify({scope:reports.scope,canonical_console_sha256:reports.console_sha256,source:'docs/SIGNED_MANDATES.md',historical_purchases_relabelled_as_human_signed:false},null,2);};
  let query = '', filter = 'all', run = '', sort = 'seq', direction = -1, limit = 50;
  const outcome = row => row.state === 'Confirmed unpaid' ? 'void' : row.verification === 'candidate' ? 'ok' : row.verification === 'reject' || row.verification === 'rejected' ? 'fail' : 'open';
  const label = row => row.state === 'Confirmed unpaid' ? 'CONFIRMED UNPAID' : row.verification === 'candidate' ? 'CANDIDATE · HUMAN APPROVAL REQUIRED' : row.verification === 'review' ? 'HUMAN REVIEW' : outcome(row) === 'fail' ? 'REJECTED · STILL CHARGED' : row.verification || 'UNRESOLVED';
  const charged = records.reduce((sum, row) => sum + (row.costMicro || 0), 0);
  text('spent', amount(charged)); text('accepted', evidence.holdoutCorrect + ' / ' + evidence.holdoutTotal);
  $('accepted').closest('.kpi').querySelector('h3').textContent = 'Strict holdout drafts';
  $('unit-cost').closest('.kpi').querySelector('h3').textContent = 'Sandbox capture';
  text('unit-cost', evidence.captureUsd.toFixed(2) + ' USD');
  const candidates = records.filter(row => outcome(row) === 'ok').length;
  text('tx-count', records.length); text('tx-spend', amount(charged));
  text('tx-ok', candidates); text('tx-bad', records.length - candidates);
  text('tx-mode', 'SAVED SANDBOX / TESTNET');
  text('ledger-headline', records.length + ' saved purchase attempts');
  text('ledger-sub', 'Confirmed charges: '+amount(charged)+'. API credit estimates remain separate. Review drafts do not authorize invoice payments.');
  text('rejected-spend', amount(records.filter(row => outcome(row) === 'fail').reduce((sum,row) => sum+(row.costMicro || 0),0)));
  text('rejected-note', 'Failed calls retain their actual USDZ charge. Human review and confirmed-unpaid attempts remain distinct.');
  const filtered = () => records.map((row,index) => ({...row,seq:index+1})).filter(row =>
    (filter === 'all' || outcome(row) === filter) && (!run || row.scope === run) &&
    [row.task,row.provider,row.receipt,row.verification,row.state,row.policy].join(' ').toLowerCase().includes(query.toLowerCase()))
    .sort((a,b) => { const key = row => ({seq:row.seq,job:row.task,provider:row.provider,total:row.costMicro ?? -1,state:label(row)})[sort]; return (key(a)<key(b)?-1:key(a)>key(b)?1:0)*direction; });
  function detail(row) {
    const values = [['Task',row.task],['Provider',row.provider],['Payment status',row.state],['Verification',label(row)],
      ['Confirmed provider charge',amount(row.costMicro)],['Hosted API credit estimate',amount(row.apiCreditMicro,'USD API credits')],
      ['Policy',row.policy || 'Integrated proof'],['Receipt',row.receipt || 'No receipt recorded'],
      ['Purchase identity',row.purchaseKey || row.id],['Source',row.evidencePath || 'bench/results/completion-20261110/final-proof-status.json'],
      ['Scope','SAVED / HISTORICAL · no new payment'],['Invoice payment authorization','Not authorized by an extraction result']];
    $('tx-detail').innerHTML = '<dl>'+values.map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd>').join('')+'</dl>';
    text('tx-drawer-title','Saved transaction '+row.id); $('tx-drawer').showModal();
  }
  function draw() {
    const rows = filtered(), shown = rows.slice(0,limit);
    $('tx-rows').innerHTML = shown.map(row => `<tr tabindex="0" data-record="${esc(row.id)}">${[row.seq,row.provider,row.task,amount(row.costMicro),label(row),row.receipt || 'No receipt'].map(cell).join('')}</tr>`).join('') || '<tr><td colspan="6">No attempts match these filters.</td></tr>';
    text('tx-shown', 'Showing '+shown.length+' of '+rows.length+' matching · '+records.length+' total');
    $('tx-more').hidden = rows.length <= limit;
    document.querySelectorAll('.tx-table th[data-sort]').forEach(el => el.dataset.sort === sort ? el.setAttribute('aria-sort', direction>0?'ascending':'descending') : el.removeAttribute('aria-sort'));
  }
  const openRow = event => { const row = event.target.closest('[data-record]'); if(row) detail(records.find(r=>r.id===row.dataset.record)); };
  $('tx-rows').onclick = openRow;
  $('tx-rows').onkeydown = event => { if(['Enter',' '].includes(event.key)){event.preventDefault();openRow(event);} };
  $('tx-close').onclick = () => $('tx-drawer').close();
  $('tx-search').oninput = event => { query=event.target.value;limit=50;draw(); };
  $('tx-run').innerHTML = '<option value="">All saved scopes</option>' + [...new Set(records.map(r=>r.scope).filter(Boolean))].map(s=>'<option>'+esc(s)+'</option>').join('');
  $('tx-run').onchange = event => {run=event.target.value;draw();};
  $('tx-more').onclick = () => {limit+=50;draw();};
  document.querySelectorAll('.tx-chip').forEach(button => button.onclick = () => {filter=button.dataset.f;limit=50;document.querySelectorAll('.tx-chip').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));draw();});
  document.querySelectorAll('.tx-table th[data-sort]').forEach(th=>th.onclick=()=>{direction=sort===th.dataset.sort?-direction:1;sort=th.dataset.sort;draw();});
  $('global-search').onsubmit = event => {event.preventDefault();query=$('global-search-input').value;$('tx-search').value=query;location.hash='transactions';draw();};
  $('ledger-latest').disabled=false; $('ledger-latest').onclick=()=>detail(records[records.length-1]);
  $('show-rejected').onclick=()=>{filter='fail';location.hash='transactions';draw();};
  $('tx-export').onclick = () => {
    const quote = value => '"'+String(value ?? '').replace(/^[=+\-@\t\r]/,"'$&").replace(/"/g,'""')+'"';
    const rows = [['task','provider','payment_status','verification','provider_micro_usdz','api_credit_estimate_micro_usd','receipt','scope'],
      ...filtered().map(r=>[r.task,r.provider,r.state,r.verification,r.costMicro,r.apiCreditMicro,r.receipt,'SAVED_HISTORICAL'])];
    const url=URL.createObjectURL(new Blob([rows.map(r=>r.map(quote).join(',')).join('\n')],{type:'text/csv'}));
    const link=document.createElement('a');link.href=url;link.download='touchstone-saved-transactions.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  draw();
  table('payment-rows', records.map(row=>[row.task,row.provider,amount(row.costMicro),'No external check charge published',label(row),row.receipt || 'No receipt']),6);
  $('recent-tx').innerHTML = records.slice(-6).reverse().map(row=>`<button class="row" data-record="${esc(row.id)}"><span class="row-main"><strong>${esc(row.provider)}</strong><small>${esc(row.task)}</small></span><span class="row-end">${esc(amount(row.costMicro))}</span></button>`).join('');
  $('recent-tx').onclick=openRow;
  const chart=$('spend-chart'), max=Math.max(1,...records.map(r=>r.costMicro || 0));
  $('chart-empty').hidden=true;text('chart-count', records.length+' saved attempts · USDZ');text('chart-mode','SAVED');
  chart.insertAdjacentHTML('afterbegin','<svg viewBox="0 0 800 210" aria-label="Saved provider charges in USDZ">'+records.map((row,i)=>`<rect x="${i*800/records.length+2}" y="${190-(row.costMicro||0)/max*170}" width="${Math.max(2,800/records.length-5)}" height="${Math.max(2,(row.costMicro||0)/max*170)}" rx="3" fill="${outcome(row)==='fail'?'#ff6b7f':'#e6e6eb'}"><title>${esc(row.task+': '+amount(row.costMicro))}</title></rect>`).join('')+'</svg>');
  // Public charges have no reliable wall-clock series in this projection.
  document.querySelectorAll('[data-range]').forEach(el=>{el.disabled=true;el.title='All published attempts; current-run and time-window data are not published.';});
  const comparison=reports.comparison, completion=reports.completion;
  text('completion-quality', evidence.calibrationCorrect+'/'+evidence.calibrationTotal+' calibration · '+evidence.holdoutCorrect+'/'+evidence.holdoutTotal+' holdout');
  text('completion-fiat', evidence.holdUsd.toFixed(2)+' hold / '+evidence.captureUsd.toFixed(2)+' captured USD');
  text('completion-credit','$'+evidence.creditUsd.toFixed(6));text('completion-credit-ceiling','Conservative aggregate API credit exposure; ceiling $'+evidence.creditCeilingUsd.toFixed(2));
  text('completion-comparison',comparison.completed_outcomes+' / '+comparison.expected_outcomes+' · '+(comparison.complete?'Complete':'Incomplete'));
  text('completion-limits',comparison.actual_paid_receipts+' actual paid receipts; '+amount(comparison.provider_micro_usdz)+' provider cost.');
  text('completion-status','SAVED MEASURED EVIDENCE · '+completion.integrated.phase+'. Review drafts never authorize invoice payment.');
  text('real-policy-summary','SAVED matched policy comparison · '+comparison.completed_outcomes+'/'+comparison.expected_outcomes+' outcomes. Strict correctness, review and payment are separate. Includes failed calls.');
  table('real-policy-rows',comparison.summary.map(row=>[row.policy,row.actual_paid_receipts,row.strict_correct+' / '+row.outcomes,amount(row.provider_micro_usdz),amount(row.provider_micro_usdz_per_strict_correct),amount(row.conservative_api_credit_exposure_micro_usd,'USD API exposure'),row.candidates+' candidate / '+row.review+' review / '+row.rejected+' rejected']),7);
  const headers=document.querySelectorAll('#real-policy-rows')?.[0]?.closest('table').querySelectorAll('th');
  ['Policy','Paid receipts','Strictly correct','Provider cost / USDZ','USDZ / strictly correct','API credit exposure / USD','Verification decisions'].forEach((value,i)=>{if(headers?.[i])headers[i].textContent=value;});
  text('measured-cost',(comparison.summary.find(r=>r.policy==='touchstone-ladder')?.provider_micro_usdz_per_strict_correct/1e6).toFixed(4));
  text('measured-unit','USDZ / STRICT CORRECT');text('measured-badge','SAVED MEASURED · FAILED CALLS INCLUDED');
  text('measured-scope','Matched testnet study. API credits are reported separately in the table. This does not establish current provider eligibility or automatic invoice acceptance.');
  const simulated=reports.simulated;
  table('benchmark-rows',(simulated.summary || []).map(r=>[r.policy,amount(r.total_cost_micro_usd,'simulated USD'),(r.true_success_rate*100).toFixed(1)+'%',amount(r.cost_per_true_correct_micro_usd,'simulated USD'),r.estimated_latency_p95_ms+' ms']),5);
  text('benchmark-method','SIMULATED historical stress benchmark · '+simulated.seeds.length+' paired seeds. Kept separate from measured testnet comparison.');
  text('invoice-study-summary', reports.invoice.label==='BLOCKED'?'BLOCKED · Historical invoice profile is missing or stale. Current qualification is shown above.':'Saved invoice study; candidate, review and rejection remain separate.');
  table('invoice-model-rows',(reports.invoice.profiles || []).flatMap(p=>['calibration','holdout'].map(split=>{const m=p[split]||{};return[p.model_id+' / '+split,(m.sources_scored??0)+' / '+(m.strict_correct??0),(m.candidates??0)+' / '+(m.review??0)+' / '+(m.rejected??0),m.false_accepts??0,p.eligible?'OFFLINE ELIGIBLE':'INELIGIBLE'];})),5);
  table('invoice-showcase-rows',(reports.invoice.showcase?.tasks || []).map(r=>[r.task,r.decision,r.label,r.reason]),4);
  text('planning-summary',reports.planning.status==='CURRENT'?'Saved current planning measurements. No live purchase is authorized.':'BLOCKED · Saved planning evidence is stale or incomplete. No eligibility is inferred.');
  for (const [node,label] of Object.entries({hold:'SAVED SANDBOX CAPTURE',reserve:'NOT PUBLISHED',pay:'SAVED TESTNET RECEIPTS',verify:'SAVED REVIEW / CANDIDATE',settle:'SAVED SANDBOX CAPTURE'})) text('node-'+node+'-status',label);
  document.querySelectorAll('.flow-node').forEach(button=>button.onclick=()=>{text('drawer-title','Saved '+button.querySelector('strong').textContent);text('drawer-description','Historical observations only. This is not a current hold, payment or event stream.');text('evidence-content',JSON.stringify({scope:reports.scope,integrated:completion.integrated,comparison:{complete:comparison.complete,outcomes:comparison.completed_outcomes,paid_receipts:comparison.actual_paid_receipts,provider_micro_usdz:comparison.provider_micro_usdz}},null,2));$('evidence-drawer').showModal();});
  $('close-evidence').onclick=()=>$('evidence-drawer').close();
  text('card-status','Saved sandbox card controls verified: '+String(reports.card.controls_verified)+'. No merchant charge or current card validity is inferred. Visa approval pending.');
  text('fx-status','SAVED sandbox FX: '+reports.fx.status+' · '+reports.fx.sell_amount+' '+reports.fx.sell_currency+' → '+reports.fx.buy_amount+' '+reports.fx.buy_currency+'. Separate from USDZ; no current quote.');
  text('fault-summary','Saved seller acknowledgement: '+reports.fault.decision+'. Signature check recorded: '+String(reports.fault.signature_verified)+'. Credit status: '+reports.fault.credit_status+'. No refund.');
  text('fault-root',reports.fault.root);text('fault-badge','SAVED FAULT EVIDENCE');
  table('banked-job-rows',[[completion.integrated.phase, 'SAVED INTEGRATED PROOF',amount(completion.integrated.provider_spend_micro_usdz),amount(completion.integrated.sandbox_capture_micro_usd,'USD'),'Unused float retained']],5);
  for(const id of ['testnet-proof-summary','paid-proof-story']) text(id,'Saved testnet receipts are listed under Transactions. The completed matched comparison is shown below. No new provider call was made.');
  text('proof-headline-main','Real testnet purchase history');text('proof-headline-detail','Inspect the original saved receipts.');
  text('paid-proof-spend',amount(comparison.provider_micro_usdz));text('paid-proof-capture','Separate sandbox rail');
  text('paid-proof-loss','Not a profit measure');text('paid-proof-answer','See verification decisions');text('paid-proof-replay','Historical recovery evidence remains in the repository.');
  document.documentElement.dataset.evidenceLoaded='true';
} catch {
  text('notice','BLOCKED · Saved public evidence could not be loaded. No figures or financial operations are inferred.');
  document.documentElement.dataset.evidenceLoaded='blocked';
}
