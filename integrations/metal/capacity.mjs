let cached=null, observed=0;
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

export function capacityQuote(base, queue, samples, observation) {
  const sorted=[...samples].sort((a,b)=>a-b);
  const p95=sorted.length ? sorted[Math.max(0,Math.ceil(sorted.length*.95)-1)] : null;
  return {price:base,quote_allowed:observation?.thermal_throttling_active!==true,
    latency_ms:p95===null?null:Math.ceil(p95*(queue+1)),recent_p95_ms:p95,
    latency_samples:samples.length,telemetry_ref:observation?.sample_id||null,
    telemetry_observed_at:observation?.observed_at||null,
    pricing_policy:'FIXED_BASE_UNCALIBRATED_CAPACITY_MARKUP_DISABLED'};
}
