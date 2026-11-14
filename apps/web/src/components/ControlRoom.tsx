import { useEffect, useRef, useState } from 'react';
import './control-room.css';

type Job = {id:string; state:string; reason:string|null; policy:string; task:{kind:string;source:object};
  output:object|null; verdict:object|null; updated_at:number; budget_micro_usdz:number;
  max_call_micro_usdz:number; charged_micro_usdz:number; charged_micro_usd:number; api_credit_micro_usd:number};
type Session = {username:string;csrf:string;expires_at:number;environment:string;revision:string};
type Event = {id:number;kind:string;ts:number;payload:{job_id?:string;reason?:string}};
const SAMPLE = JSON.stringify({amounts_cents:[1250,900],discount_cents:150},null,2);

export default function ControlRoom() {
  const [ready,setReady]=useState<boolean|null>(null),[session,setSession]=useState<Session|null>(null);
  const [message,setMessage]=useState(''),[busy,setBusy]=useState(false),[jobs,setJobs]=useState<Job[]>([]);
  const [events,setEvents]=useState<Event[]>([]),[connected,setConnected]=useState(false),[audit,setAudit]=useState(false);
  const [username,setUsername]=useState('operator'),[password,setPassword]=useState('');
  const [kind,setKind]=useState('arithmetic'),[source,setSource]=useState(SAMPLE),[policy,setPolicy]=useState('tools-only');
  const [budget,setBudget]=useState('0'),[cap,setCap]=useState('0'),[selected,setSelected]=useState<Job|null>(null);
  const [quotes,setQuotes]=useState<object|null>(null);
  const [integrations,setIntegrations]=useState<object|null>(null);
  const key=useRef(crypto.randomUUID()),cursor=useRef(0);
  async function api(path:string,body?:object,extra:Record<string,string>={}) {
    const r=await fetch('/operator-api/'+path,{credentials:'same-origin',cache:'no-store',
      ...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json',
        'X-Touchstone-CSRF':session?.csrf||'',...extra},body:JSON.stringify(body)})});
    const value=await r.json();
    if(!r.ok){if(r.status===401)setSession(null);throw Error(value.error||'REQUEST_REJECTED');}
    return value;
  }
  async function refresh() {
    const value=await api('jobs');setJobs(value.jobs);setAudit(value.audit.valid===true);
    setSelected(previous=>previous?value.jobs.find((j:Job)=>j.id===previous.id)||null:null);
  }
  useEffect(()=>{
    let live=true;
    fetch('/healthz',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(async health=>{
      if(!live)return;
      if(health?.service!=='touchstone-operator'){setReady(false);return;}
      setReady(true);
      try{const s=await api('session');if(live)setSession(s);}catch{/* Login required. */}
    }).catch(()=>{if(live)setReady(false);});
    return()=>{live=false;};
  },[]);
  useEffect(()=>{
    if(!session){setJobs([]);setEvents([]);cursor.current=0;setSelected(null);setQuotes(null);return;}
    refresh().catch(e=>setMessage(e.message));
    // EventSource reconnects with Last-Event-ID; duplicates are ignored and state is refetched.
    const stream=new EventSource('/operator-api/events');
    stream.onopen=()=>{setConnected(true);refresh().catch(e=>setMessage(e.message));};
    stream.onerror=()=>{setConnected(false);api('session').catch(e=>setMessage(e.message));};
    stream.addEventListener('operation',raw=>{
      const event=JSON.parse((raw as MessageEvent).data) as Event;
      if(event.id<=cursor.current)return;
      cursor.current=event.id;setEvents(previous=>[event,...previous].slice(0,100));
      refresh().catch(e=>setMessage(e.message));
    });
    return()=>{stream.close();setConnected(false);};
  },[session?.csrf]);
  async function perform(work:()=>Promise<void>) {
    setBusy(true);setMessage('');
    try{await work();}catch(e){setMessage(e instanceof Error?e.message:'REQUEST_FAILED');}finally{setBusy(false);}
  }
  async function login() {
    try{await api('login',{username,password});setPassword('');setSession(await api('session'));}
    finally{setPassword('');}
  }
  async function create() {
    if(!/^\d+$/.test(budget)||!/^\d+$/.test(cap))throw Error('Use integer micro-USDZ limits');
    const job=await api('jobs',{kind,source:JSON.parse(source),policy,
      budget_micro_usdz:Number(budget),max_call_micro_usdz:Number(cap)}, {'Idempotency-Key':key.current});
    key.current=crypto.randomUUID();setSelected(job);await refresh();
  }
  async function action(job:Job,action:string) {
    const result=await api('jobs/'+job.id+'/'+action,{});
    if(action==='quotes')setQuotes(result);else setSelected(result);
    await refresh();
  }
  return <div className="control-room">
    <header><a href="/site/" className="brand">TOUCHSTONE</a><span className="mono">AUTHENTICATED WORKSPACE</span><a href="/dashboard">Saved evidence &amp; dashboard</a></header>
    <main>
      <p className="eyebrow">Actual backend · persistent jobs · zero external charges</p>
      <h1>Operator control room</h1>
      <p className="cr-intro">Run supported source checks, inspect exact results, and follow the durable audit trail. Financial procurement stays behind its separate approval boundary.</p>
      <div role="status" aria-live="polite" className="cr-message">{message}</div>
      {ready===null?<p>Checking operational backend…</p>:!ready?<section className="cr-panel"><h2>BLOCKED · Backend not connected</h2><p>This origin has no authenticated operational Python service. Historical evidence remains available. Deploy the separate operator backend with TLS and persistent storage using docs/LIVE_DEPLOYMENT.md. No password or task is submitted here.</p></section>:!session?
        <form className="cr-panel cr-login" onSubmit={e=>{e.preventDefault();perform(login);}}>
          <h2>Operator sign in</h2><label>Username<input autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required maxLength={64}/></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required maxLength={256}/></label>
          <button disabled={busy} type="submit">Sign in</button><p>Provision the operator offline with tools/run_operator.py init. This login never grants financial spending authority.</p>
        </form>:<>
        <div className="cr-session mono"><span>{session.environment} · {session.username} · {connected?'EVENTS CONNECTED':'EVENTS RECONNECTING'} · AUDIT {audit?'VALID':'CHECKING'}</span>
          <button onClick={()=>perform(async()=>{await api('logout',{});setSession(null);})}>Sign out</button></div>
        <div className="cr-grid">
          <form className="cr-panel" onSubmit={e=>{e.preventDefault();perform(create);}}>
            <h2>Create a task</h2><label>Task type<select value={kind} onChange={e=>{setKind(e.target.value);key.current=crypto.randomUUID();}}>
              {['arithmetic','invoice','classification','invoice_extraction','invoice_consistency'].map(k=><option key={k}>{k}</option>)}</select></label>
            <label>Source JSON<textarea rows={8} value={source} onChange={e=>{setSource(e.target.value);key.current=crypto.randomUUID();}} required/></label>
            <label>Policy<select value={policy} onChange={e=>setPolicy(e.target.value)}><option value="tools-only">Bounded local tools only</option><option value="real-touchstone">Local first · external approval required</option></select></label>
            <div className="cr-limits"><label>Budget · integer micro-USDZ<input value={budget} inputMode="numeric" onChange={e=>setBudget(e.target.value)}/></label>
              <label>Per-call cap · integer micro-USDZ<input value={cap} inputMode="numeric" onChange={e=>setCap(e.target.value)}/></label></div>
            <p>These are proposed limits, not allocated funds. Creating or starting a task cannot purchase inference. USD, USDZ, API credits and fees are separate.</p>
            <button disabled={busy} type="submit">Create backend job</button>
          </form>
          <section className="cr-panel"><h2>Execution &amp; reconciliation</h2>
            {selected?<><p className="mono">{selected.id}</p><strong>{selected.state}</strong><p>{selected.reason}</p>
              <div className="cr-actions">{['start','pause','resume','quotes'].map(action=><button key={action} disabled={busy} onClick={()=>perform(()=>actionFn(action))}>{action==='quotes'?'Get actual provider quotes':action==='start'?'Start zero-charge processing':action}</button>)}</div>
              <pre>{JSON.stringify({output:selected.output,verification:selected.verdict,
                USD:selected.charged_micro_usd,USDZ:selected.charged_micro_usdz,prepaid_credit_USD:selected.api_credit_micro_usd,receipt:null},null,2)}</pre>
              {quotes&&<pre aria-label="Provider quote results">{JSON.stringify(quotes,null,2)}</pre>}
              <p>External dispatch is disabled in this service. Fresh qualification, allocated funds, exact EIP-712 human approval and an approved private payer are required. No invoice payment is authorized by extraction success.</p>
            </>:<p>Select a job to inspect its source, output, verification and actual charges.</p>}</section>
        </div>
        <section className="cr-panel"><h2>Airwallex &amp; Metal readiness</h2><p>Read-only observations are produced by the private operator and expire after five minutes. A past capture is saved evidence, not a current authorization or permission to spend. This service has no bank or payer credentials.</p>
          <button disabled={busy} onClick={()=>perform(async()=>setIntegrations(await api('integrations')))}>Read integration snapshot</button>
          {integrations&&<pre>{JSON.stringify(integrations,null,2)}</pre>}
        </section>
        <section className="cr-panel"><h2>Persistent transaction &amp; job ledger</h2><div className="cr-scroll"><table><thead><tr><th>Task</th><th>State</th><th>Provider / rail</th><th>Charged USDZ</th><th>API credit USD</th><th>Updated</th></tr></thead><tbody>
          {jobs.map(job=><tr key={job.id}><td><button onClick={()=>{setSelected(job);setQuotes(null);}}>{job.task.kind} · {job.id.slice(-8)}</button></td><td>{job.state}</td><td>{job.output?'local-tool / none':'not dispatched'}</td><td>{job.charged_micro_usdz}</td><td>{job.api_credit_micro_usd}</td><td>{new Date(job.updated_at*1000).toLocaleString()}</td></tr>)}
        </tbody></table></div>{jobs.length===0&&<p>No backend jobs yet.</p>}</section>
        <section className="cr-panel"><h2>Backend event stream</h2><ol className="cr-events">{events.map(e=><li key={e.id}><span className="mono">#{e.id} · {e.kind}</span> {e.payload.job_id?.slice(-8)} {e.payload.reason}</li>)}</ol></section>
        <p className="mono">REVISION {session.revision} · FINANCIAL DISPATCH DISABLED · VISA BLOCKED_EXTERNAL_APPROVAL</p>
      </>}
    </main>
  </div>;
  function actionFn(name:string){return selected?action(selected,name):Promise.resolve();}
}
