import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
let cached=null, observed=0;

function stable(value){
  if(Array.isArray(value)) return '['+value.map(stable).join(',')+']';
  if(value&&typeof value==='object') return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stable(value[k])).join(',')+'}';
  return JSON.stringify(value);
}

// A calibration is trusted only if its digest matches, it has not expired and it names the served model.
export function loadCalibration(path, modelSha256, now=Date.now()) {
  try {
    const calibration=JSON.parse(readFileSync(path,'utf8')), body=calibration.body;
    if (body.version!=='touchstone-capacity-calibration-v1' || body.model_sha256!==modelSha256 ||
        calibration.digest!==createHash('sha256').update(stable(body)).digest('hex') ||
        now/1000>body.valid_until || !(body.baseline_tps>0) || !(body.max_multiplier>1 && body.max_multiplier<=1.5)) return null;
    return calibration;
  } catch { return null; }
}

// Multiplier comes only from measured live decode throughput. Temperature never prices a quote.
export function capacityMultiplier(calibration, recentTps) {
  const body=calibration?.body;
  if (!body || recentTps.length<body.minimum_live_samples) return 1;
  const sorted=[...recentTps].sort((a,b)=>a-b), mid=sorted.length>>1;
  const median=sorted.length%2?sorted[mid]:(sorted[mid-1]+sorted[mid])/2;
  return median>0 ? Math.min(body.max_multiplier, Math.max(1, body.baseline_tps/median)) : 1;
}
export async function localCapacity(fetcher=fetch, now=Date.now()) {
  if (now-observed<5000) return cached;
  observed=now;
  try {
    const response=await fetcher('http://127.0.0.1:8088/api/telemetry',{redirect:'error',signal:AbortSignal.timeout(700)});
    const result=await response.json();
    if (!response.ok || result.label!=='MEASURED' || !/^[a-f0-9]{24}$/.test(result.sample_id) ||
        typeof result.observed_at!=='number' || Math.abs(now/1000-result.observed_at)>15) throw Error('Stale telemetry');
    cached={sample_id:result.sample_id,observed_at:result.observed_at,
      thermal_throttling_active:result.thermal_throttling_active, label:'MEASURED'};
  } catch {cached=null;}
  return cached;
}

export function capacityQuote(base, queue, samples, observation, calibration=null, recentTps=[], ceiling=null) {
  const sorted=[...samples].sort((a,b)=>a-b);
  const p95=sorted.length ? sorted[Math.max(0,Math.ceil(sorted.length*.95)-1)] : null;
  const multiplier=capacityMultiplier(calibration, recentTps);
  let price=base;
  if (multiplier>1) {
    price=(base*BigInt(Math.ceil(multiplier*1000))+999n)/1000n;
    if (ceiling!==null && price>ceiling) price=ceiling;
  }
  return {price,quote_allowed:observation?.thermal_throttling_active!==true,
    latency_ms:p95===null?null:Math.ceil(p95*(queue+1)),recent_p95_ms:p95,
    latency_samples:samples.length,telemetry_ref:observation?.sample_id||null,
    telemetry_observed_at:observation?.observed_at||null,
    capacity_multiplier:multiplier, recent_throughput_samples:recentTps.length,
    calibration_digest:calibration?calibration.digest:null,
    pricing_policy:calibration?'MEASURED_THROUGHPUT_CALIBRATION_BOUNDED_MULTIPLIER':'FIXED_BASE_UNCALIBRATED_CAPACITY_MARKUP_DISABLED'};
}
