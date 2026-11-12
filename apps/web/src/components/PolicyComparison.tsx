import type { PolicyComparisonData } from "@/siteTypes";

export default function PolicyComparison({ data }: { data?: PolicyComparisonData | null }) {
  if (!data) return null;
  return <section className="workspace-panel policy-comparison" aria-label="Measured live policy comparison">
    <div className="panel-top mono"><span>REAL TESTNET POLICY COMPARISON</span><span className={data.complete ? "mint" : "pending"}>{data.completed} / {data.expected} OUTCOMES</span></div>
    <div className="policy-summary"><strong>{data.complete ? "Matched comparison complete." : "Matched comparison in progress."}</strong><p>{data.paidReceipts} actual paid receipts · {data.attempts} purchase attempts · {data.providerUsdz.toFixed(3)} USDZ charged</p><span className="mini-tag">LIVE GATE {data.liveGatePassed ? "PASSED" : "NOT MET"}</span></div>
    <div className="table-scroll"><table className="policy-results"><thead><tr><th>POLICY</th><th>FINISHED</th><th>STRICT CORRECT</th><th>USDZ CHARGED</th><th>USDZ / STRICT CORRECT</th><th>API ESTIMATE / USD</th></tr></thead><tbody>{data.policies.map(row => <tr key={row.policy}><td>{row.policy}</td><td>{row.outcomes} / 16</td><td>{row.strict_correct} / {row.outcomes}</td><td className="mono">{(row.provider_micro_usdz / 1e6).toFixed(3)}</td><td className="mono">{row.provider_micro_usdz_per_strict_correct === null ? "Undefined" : (row.provider_micro_usdz_per_strict_correct / 1e6).toFixed(4)}</td><td className="mono">{(row.reported_api_credit_estimate_micro_usd / 1e6).toFixed(6)}{row.api_calls_with_unreported_usage > 0 && <small> + {row.api_calls_with_unreported_usage} unreported</small>}</td></tr>)}</tbody></table></div>
    <p className="table-note mono">REAL MODEL OUTPUTS AND METAL TESTNET PAYMENTS. FROZEN SYNTHETIC TASKS. FAILED CALLS COUNT. HYPOTHETICAL CHECK FEES EXCLUDED. API BILLING AND CLEARING FINALITY ARE NOT INDEPENDENTLY RECONCILED.</p>
  </section>;
}
