import type { PolicyComparisonData, PolicyRow } from "@/siteTypes";
import { Icon } from "./DashboardIcons";

const POLICY_META: Record<string, { label: string; shortLabel: string; color: string; icon: string }> = {
  "tools-only": { label: "Local tools only", shortLabel: "Tools only", color: "#a1a1aa", icon: "check" },
  "always-cheapest": { label: "Cheapest paid model", shortLabel: "Cheapest", color: "#71717a", icon: "bolt" },
  "always-premium": { label: "Premium paid model", shortLabel: "Premium", color: "#e4e4e7", icon: "spark" },
  "touchstone-ladder": { label: "Touchstone ladder", shortLabel: "Ladder", color: "#34d399", icon: "shield" },
};

const policyLabel = (policy: string) => POLICY_META[policy]?.label ?? policy;
const policyShortLabel = (policy: string) => POLICY_META[policy]?.shortLabel ?? policyLabel(policy);
const policyColor = (policy: string) => POLICY_META[policy]?.color ?? "#d4d4d8";
const policyIcon = (policy: string) => POLICY_META[policy]?.icon ?? "cpu";

export default function PolicyComparison({
  data,
  calibration = "Unreported",
  holdout = "Unreported",
}: {
  data?: PolicyComparisonData | null;
  calibration?: string;
  holdout?: string;
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
    : null;

  const falseAccepts = (row: PolicyRow) => { const value = (row as PolicyRow & {false_accepts?: number}).false_accepts; return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : undefined; };
  const reportedFalseAccepts = data.policies.length > 0 && data.policies.every(row => typeof falseAccepts(row) === "number") ? data.policies.reduce((sum, row) => sum + falseAccepts(row)!, 0) : null;
  return (
    <section className="bento-policy-section" id="policy-planner" aria-label="Measured live policy comparison">
      <div className="bento-policy-top bento-policy-top-2">
        <div className="bento-card">
          <div className="bento-card-head">
            <span className="bento-card-title"><Icon name="wallet" size={14} /> Policy Spend Overview</span>
            <span className="mini-tag">{savingsPct === null ? "SPEND COMPARISON UNAVAILABLE" : savingsPct === 0 ? "SAME PROVIDER SPEND AS PREMIUM" : `${Math.abs(savingsPct)}% ${savingsPct > 0 ? "LOWER" : "HIGHER"} LADDER PROVIDER SPEND`}</span>
          </div>
          <div className="bento-well hatch-well">
            <div className="hatch-bars">
              {hatchSource.map((row, idx) => {
                const heightPct = Math.max(0, Math.round((row.provider_micro_usdz / maxMicro) * 100));
                const isLadder = row.policy === "touchstone-ladder";
                return (
                  <div className={"hatch-col" + (isLadder ? " is-ladder" : "")} key={row.policy}>
                    <div className="hatch-meta">
                      <span className="hatch-label">{policyShortLabel(row.policy)}</span>
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
            <span className="bento-card-title"><Icon name="spark" size={14} /> Policy Verdict</span>
            <span className="mini-tag">LIVE GATE {data.liveGatePassed ? "PASSED" : "NOT MET"}</span>
          </div>
          <div className="bento-well insight-spotlight">
            <div className="spotlight-rings" aria-hidden="true" />
            <div className="spotlight-copy">
              <h2 className="bento-verdict-heading">Four policies. One frozen task set.</h2>
              <p>
                {data.paidReceipts} paid x402 receipts across {data.attempts} attempts totaling {data.providerUsdz.toFixed(3)} USDZ charged on Metal testnet. Provider spend and strict correctness are separate outcomes; compare both below. Hosted API-credit exposure remains separate from USDZ.
              </p>
            </div>
            <div className="verdict-stats-row">
              <span className="verdict-stat mono"><b>{data.completed}/{data.expected}</b> Completed</span>
              <span className="verdict-stat mono"><b>{reportedFalseAccepts ?? "Unreported"}</b> False Accepts</span>
              <span className="verdict-stat mono"><b>{calibration}</b> Calibration</span>
              <span className="verdict-stat mono"><b>{holdout}</b> Holdout</span>
            </div>
          </div>
        </div>
      </div>

      <div className="bento-card">
        <div className="bento-card-head">
          <span className="bento-card-title"><Icon name="shield" size={14} /> Measured Policy Benchmark</span>
          <span className={data.complete ? "mini-tag" : "pending mini-tag"}>HISTORICAL TESTNET STUDY · {data.completed} / {data.expected} OUTCOMES</span>
        </div>
        <div className="bento-well policy-well">
          <div className="table-scroll" id="policy-table-wrap">
            <table className="policy-results">
              <thead>
                <tr>
                  <th>POLICY</th>
                  <th>FINISHED</th>
                  <th>STRICT ACCURACY</th>
                  <th>USDZ CHARGED</th>
                  <th>USDZ / STRICT CORRECT</th>
                  <th>API ESTIMATE / USD</th>
                  <th>FALSE ACCEPTS</th>
                </tr>
              </thead>
              <tbody>
                {data.policies.map(row => {
                  const litSegments = Math.max(0, Math.round((row.strict_correct / Math.max(1, row.outcomes)) * 12));
                  const color = policyColor(row.policy);
                  return (
                    <tr key={row.policy}>
                      <td>
                        <div className="policy-cell-id">
                          <span
                            className="led-squircle"
                            style={{
                              color,
                              borderColor: row.policy === "touchstone-ladder" ? "rgba(52,211,153,.32)" : "rgba(255,255,255,.08)",
                            }}
                          >
                            <Icon name={policyIcon(row.policy)} size={14} />
                          </span>
                          <div>
                            <strong>{policyLabel(row.policy)}</strong>
                            <small className="mono">{row.policy}</small>
                          </div>
                        </div>
                      </td>
                      <td className="mono">{row.outcomes} / 16</td>
                      <td>
                        <div className="policy-acc-cell">
                          <span className="mono">{row.strict_correct} / {row.outcomes}</span>
                          <div className="led-ticks" aria-hidden="true">
                            {Array.from({ length: 12 }, (_, idx) => (
                              <i
                                key={idx}
                                style={idx < litSegments ? { backgroundColor: color } : undefined}
                              />
                            ))}
                          </div>
                        </div>
                      </td>
                      <td className="mono">${(row.provider_micro_usdz / 1e6).toFixed(3)}</td>
                      <td className="mono">
                        {row.provider_micro_usdz_per_strict_correct === null
                          ? "Undefined"
                          : `$${(row.provider_micro_usdz_per_strict_correct / 1e6).toFixed(4)}`}
                      </td>
                      <td className="mono">
                        {(row.reported_api_credit_estimate_micro_usd / 1e6).toFixed(6)}
                        {row.api_calls_with_unreported_usage > 0 && <small>+ {row.api_calls_with_unreported_usage} unreported</small>}
                      </td>
                      <td>
                        <span className="led-status-pill">{falseAccepts(row) ?? "Unreported"}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="table-note mono">
            REAL MODEL OUTPUTS AND METAL TESTNET PAYMENTS. FROZEN SYNTHETIC TASKS. FAILED CALLS COUNT. HYPOTHETICAL CHECK FEES EXCLUDED. API BILLING AND CLEARING FINALITY ARE NOT INDEPENDENTLY RECONCILED.
          </p>
        </div>
      </div>
    </section>
  );
}
