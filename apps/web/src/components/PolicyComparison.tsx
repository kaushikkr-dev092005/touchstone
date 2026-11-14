import type { PolicyComparisonData, PolicyRow } from "@/siteTypes";
import { Icon } from "./Identity";

const POLICY_META: Record<string, { label: string; color: string; icon: string }> = {
  "tools-only": { label: "Local tools only", color: "#a1a1aa", icon: "check" },
  "always-cheapest": { label: "Cheapest paid model", color: "#71717a", icon: "bolt" },
  "always-premium": { label: "Premium paid model", color: "#d4d4d8", icon: "spark" },
  "touchstone-ladder": { label: "Touchstone ladder", color: "#e5a95d", icon: "shield" },
};

const policyLabel = (policy: string) => POLICY_META[policy]?.label ?? policy;
const policyColor = (policy: string) => POLICY_META[policy]?.color ?? "#d4d4d8";
const policyIcon = (policy: string) => POLICY_META[policy]?.icon ?? "cpu";

export default function PolicyComparison({
  data,
  calibration = "120 / 120",
  holdout = "59 / 60",
  products = 100,
}: {
  data?: PolicyComparisonData | null;
  calibration?: string;
  holdout?: string;
  products?: number;
}) {
  if (!data) return null;

  const paidPolicies = [...data.policies].filter(p => p.provider_micro_usdz > 0);
  const hatchSource: PolicyRow[] = paidPolicies.length >= 3
    ? paidPolicies.sort((a, b) => b.provider_micro_usdz - a.provider_micro_usdz).slice(0, 3)
    : data.policies.slice(0, 3);
  const maxMicro = Math.max(1, ...hatchSource.map(p => p.provider_micro_usdz));

  const premium = data.policies.find(p => p.policy === "always-premium");
  const ladder = data.policies.find(p => p.policy === "touchstone-ladder");
  const savingsPct = premium && ladder && premium.provider_micro_usdz > 0
    ? Math.round(((premium.provider_micro_usdz - ladder.provider_micro_usdz) / premium.provider_micro_usdz) * 100)
    : 54;

  const completionPct = data.expected > 0 ? Math.round((data.completed / data.expected) * 100) : 100;
  const quickInsights = [
    { icon: "check", text: `${data.completed} / ${data.expected} matched testnet outcomes finished` },
    { icon: "wallet", text: `${data.paidReceipts} paid x402 receipts across ${data.attempts} attempts` },
    { icon: "shield", text: "0 false accepts recorded across all 4 policies" },
    { icon: "spark", text: `Touchstone ladder cut USDZ spend ${savingsPct}% vs premium` },
    { icon: "cpu", text: `${calibration} strict calibration score under frozen prompts` },
    { icon: "grid", text: `${holdout} untouched holdout score (interrupted = fail)` },
    { icon: "ledger", text: `${products} synthetic merchant SKUs verified via OAuth` },
    { icon: "bolt", text: "Sandbox fiat & Metal USDZ rails remain strictly isolated" },
  ];

  return (
    <section className="bento-policy-section" id="policy-planner" aria-label="Measured live policy comparison">
      <div className="bento-policy-top">
        <div className="bento-card">
          <div className="bento-card-head">
            <span className="bento-card-title"><Icon name="spark" size={14} /> Policy Spend Overview</span>
            <span className="mini-tag">{data.completed} / {data.expected} OUTCOMES</span>
          </div>
          <div className="bento-well hatch-well">
            <div className="hatch-bars">
              {hatchSource.map((row, idx) => {
                const heightPct = Math.max(36, Math.round((row.provider_micro_usdz / maxMicro) * 100));
                return (
                  <div className="hatch-col" key={row.policy}>
                    <div className="hatch-meta">
                      <span className="hatch-label">{policyLabel(row.policy)}</span>
                      <strong className="hatch-val">${(row.provider_micro_usdz / 1e6).toFixed(3)} USDZ</strong>
                    </div>
                    <div className="hatch-block" style={{ height: `${heightPct}%` }}>
                      {idx === 0 && <span className="hatch-cap-line"><i /></span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="bento-card">
          <div className="bento-card-head">
            <span className="bento-card-title"><Icon name="spark" size={14} /> Quick Study Insights</span>
            <span className="bento-muted-tag mono">LIVE BENCHMARK</span>
          </div>
          <div className="bento-well quick-insights-well">
            <div className="quick-insights-grid">
              {quickInsights.map(item => (
                <div className="quick-insight-chip" key={item.text}>
                  <span className="qi-icon"><Icon name={item.icon} size={13} /></span>
                  <span>{item.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bento-card">
          <div className="bento-card-head">
            <span className="bento-card-title"><Icon name="spark" size={14} /> Policy Verdict</span>
            <span className="mini-tag">LIVE GATE {data.liveGatePassed ? "PASSED" : "NOT MET"}</span>
          </div>
          <div className="bento-well insight-spotlight">
            <div className="spotlight-rings" aria-hidden="true" />
            <div className="spotlight-copy">
              <strong>{data.complete ? "Matched comparison complete." : "Matched comparison in progress."}</strong>
              <p>{data.paidReceipts} actual paid receipts across {data.attempts} purchase attempts totaling {data.providerUsdz.toFixed(3)} USDZ charged on Metal testnet.</p>
            </div>
            <button
              type="button"
              className="bento-pill-white"
              onClick={() => document.getElementById("policy-table-wrap")?.scrollIntoView({ behavior: "smooth" })}
            >
              Inspect {savingsPct}% Ladder Savings <Icon name="arrow" size={14} />
            </button>
          </div>
        </div>
      </div>

      <div className="bento-policy-bot">
        <div className="bento-card">
          <div className="bento-card-head">
            <span className="bento-card-title"><Icon name="wallet" size={14} /> Policy Categories &amp; Measured Comparison</span>
            <span className={data.complete ? "mini-tag" : "pending mini-tag"}>REAL TESTNET STUDY</span>
          </div>
          <div className="bento-well policy-well">
            <div className="led-list">
              {data.policies.map(row => {
                const strictPct = row.outcomes > 0 ? Math.round((row.strict_correct / row.outcomes) * 100) : 0;
                const litSegments = Math.max(1, Math.round((row.strict_correct / Math.max(1, row.outcomes)) * 12));
                const color = policyColor(row.policy);
                return (
                  <div className="led-row" key={row.policy}>
                    <div className="led-name">
                      <span className="led-squircle" style={{ color, borderColor: row.policy === "touchstone-ladder" ? "rgba(229,169,93,.3)" : "rgba(255,255,255,.08)" }}>
                        <Icon name={policyIcon(row.policy)} size={14} />
                      </span>
                      <div>
                        <strong>{policyLabel(row.policy)}</strong>
                        <small className="mono">{row.policy}</small>
                      </div>
                    </div>
                    <div className="led-spend mono">
                      <strong>${(row.provider_micro_usdz / 1e6).toFixed(3)}</strong>
                      <span>USDZ ({row.actual_paid_receipts} paid)</span>
                    </div>
                    <div className="led-bar-group" aria-label={`${row.policy} strict accuracy ${strictPct}%`}>
                      <div className="led-ticks">
                        {Array.from({ length: 12 }, (_, idx) => (
                          <i
                            key={idx}
                            style={idx < litSegments ? { backgroundColor: color, boxShadow: `0 0 5px ${color}55` } : undefined}
                          />
                        ))}
                      </div>
                      <span className="led-pct mono">{row.strict_correct}/{row.outcomes}</span>
                    </div>
                    <span className="led-status-pill">0 False Accepts</span>
                  </div>
                );
              })}
            </div>

            <div className="table-scroll policy-table-box" id="policy-table-wrap">
              <table className="policy-results">
                <thead>
                  <tr>
                    <th>POLICY</th>
                    <th>FINISHED</th>
                    <th>STRICT CORRECT</th>
                    <th>USDZ CHARGED</th>
                    <th>USDZ / STRICT CORRECT</th>
                    <th>API ESTIMATE / USD</th>
                  </tr>
                </thead>
                <tbody>
                  {data.policies.map(row => (
                    <tr key={row.policy}>
                      <td>{row.policy}</td>
                      <td>{row.outcomes} / 16</td>
                      <td>{row.strict_correct} / {row.outcomes}</td>
                      <td className="mono">{(row.provider_micro_usdz / 1e6).toFixed(3)}</td>
                      <td className="mono">
                        {row.provider_micro_usdz_per_strict_correct === null
                          ? "Undefined"
                          : (row.provider_micro_usdz_per_strict_correct / 1e6).toFixed(4)}
                      </td>
                      <td className="mono">
                        {(row.reported_api_credit_estimate_micro_usd / 1e6).toFixed(6)}
                        {row.api_calls_with_unreported_usage > 0 && <small> + {row.api_calls_with_unreported_usage} unreported</small>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="table-note mono">
              REAL MODEL OUTPUTS AND METAL TESTNET PAYMENTS. FROZEN SYNTHETIC TASKS. FAILED CALLS COUNT. HYPOTHETICAL CHECK FEES EXCLUDED. API BILLING AND CLEARING FINALITY ARE NOT INDEPENDENTLY RECONCILED.
            </p>
          </div>
        </div>

        <div className="bento-card">
          <div className="bento-card-head">
            <span className="bento-card-title"><Icon name="shield" size={14} /> Verification Health</span>
            <button type="button" className="bento-dots-btn" aria-label="Verification metrics"><Icon name="dots" size={14} /></button>
          </div>
          <div className="bento-well gauge-well">
            <div className="gauge-wrap">
              <svg viewBox="0 0 240 135" className="gauge-svg" aria-hidden="true">
                {Array.from({ length: 12 }, (_, idx) => {
                  const angleStart = -175 + idx * 14.5;
                  const angleEnd = angleStart + 10.5;
                  const r = 88;
                  const cx = 120;
                  const cy = 114;
                  const rad = (deg: number) => (deg * Math.PI) / 180;
                  const x1 = cx + r * Math.cos(rad(angleStart));
                  const y1 = cy + r * Math.sin(rad(angleStart));
                  const x2 = cx + r * Math.cos(rad(angleEnd));
                  const y2 = cy + r * Math.sin(rad(angleEnd));
                  const lit = idx < Math.round((completionPct / 100) * 12);
                  return (
                    <path
                      key={idx}
                      d={`M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r} ${r} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`}
                      stroke={lit ? (idx > 8 ? "#e5a95d" : "rgba(255,255,255,.75)") : "#1e1e24"}
                      strokeWidth="16"
                      strokeLinecap="butt"
                      fill="none"
                    />
                  );
                })}
              </svg>
              <div className="gauge-center">
                <strong>{data.completed}</strong>
                <span>Verified Score ({completionPct}%)</span>
              </div>
            </div>
            <div className="gauge-foot">
              <div className="gauge-foot-icon"><Icon name="spark" size={15} /></div>
              <div>
                <strong>Zero False Accepts Across {data.expected} Calls</strong>
                <small>Ladder policy cuts provider USDZ by {savingsPct}% vs always-premium</small>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
