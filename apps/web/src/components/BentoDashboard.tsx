import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./DashboardIcons";
import "./dashboard.css";
import PolicyComparison from "./PolicyComparison";
import type { Evidence, Go, RecordRow, View } from "@/siteTypes";

function SplitMetric({ value, prefix = "", decimals = 2 }: { value: number; prefix?: string; decimals?: number }) {
  const formatted = value.toFixed(decimals);
  const [whole, frac] = formatted.split(".");
  return (
    <span className="split-num">
      {prefix}{whole}
      {frac !== undefined && <span className="split-dec">.{frac}</span>}
    </span>
  );
}

function KpiMeter({ pct, tone = "neutral" }: { pct: number; tone?: "neutral" | "emerald" | "amber" }) {
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  return (
    <div className="kpi-meter" aria-hidden="true">
      <i className={"is-" + tone} style={{ width: `${clamped}%` }} />
    </div>
  );
}

function RingProgress({ pct, color }: { pct: number; color: string }) {
  const r = 15;
  const c = 2 * Math.PI * r;
  const dash = Math.max(0, Math.min(c, (pct / 100) * c));
  return (
    <div className="ring-wrap" aria-label={`${pct}%`}>
      <svg width="38" height="38" viewBox="0 0 38 38" aria-hidden="true">
        <circle cx="19" cy="19" r={r} fill="none" stroke="#222228" strokeWidth="3.2" />
        <circle
          cx="19"
          cy="19"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="3.2"
          strokeDasharray={`${dash.toFixed(1)} ${c.toFixed(1)}`}
          strokeLinecap="round"
          transform="rotate(-90 19 19)"
        />
      </svg>
      <span className="mono">{pct}%</span>
    </div>
  );
}

function providerBadge(provider: string) {
  const p = provider.toLowerCase();
  if (p.includes("local")) return { icon: "cpu", label: "Local GPU" };
  if (p.includes("premium") || p.includes("sonnet")) return { icon: "spark", label: "Hosted Premium" };
  return { icon: "bolt", label: "Hosted Route" };
}

export default function BentoDashboard({
  view,
  evidence,
  go,
}: {
  view: View;
  evidence: Evidence | null;
  go: Go;
}) {
  const [filter, setFilter] = useState("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("recorded");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [selected, setSelected] = useState<RecordRow | null>(null);
  const [activeBarIdx, setActiveBarIdx] = useState<number | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (selected) dialog.current?.showModal();
  }, [selected]);

  const records = evidence?.records || [];
  function exportCsv() {
    const cells = (value: unknown) => {
      const text = String(value ?? "");
      return '"' + (/^[=+@\-\t\r]/.test(text) ? "'" + text : text).replaceAll('"', '""') + '"';
    };
    const lines = [["Task", "Provider", "State", "Cost / micro-USDZ", "API estimate / micro-USD", "Receipt", "Verification"], ...rows.map(row => [row.task, row.provider, row.state, row.costMicro, row.apiCreditMicro, row.receipt, row.verification])];
    const url = URL.createObjectURL(new Blob([lines.map(line => line.map(cells).join(",")).join("\r\n")], {type: "text/csv;charset=utf-8"}));
    const link = document.createElement("a"); link.href = url; link.download = "touchstone-saved-attempts.csv"; link.click(); URL.revokeObjectURL(url);
  }
  const rows = useMemo(
    () =>
      records.filter(
        row =>
          (filter === "all" || (filter === "charged" ? (row.costMicro || 0) > 0 : filter === "unresolved" ? row.costMicro === null : row.state === "Confirmed unpaid")) &&
          (row.task + row.provider + (row.receipt || "") + row.state).toLowerCase().includes(query.toLowerCase()),
      ).sort((a, b) => sort === "task" ? a.task.localeCompare(b.task) : sort === "cost" ? (b.costMicro ?? -1) - (a.costMicro ?? -1) : 0),
    [records, filter, query, sort],
  );

  const capsuleBars = useMemo(() => {
    const source = records.slice(0, 28);
    return source.map((rec, i) => {
      const costMicro = rec?.costMicro ?? 0;
      const isCharged = rec?.state === "Charged";
      const primaryPct = costMicro > 0 ? Math.min(100, Math.round((costMicro / Math.max(1, ...source.map(r => r.costMicro ?? 0))) * 100)) : 0;
      const upperPct = 0; // API-credit estimates are a separate currency, never stacked into USDZ.
      return {
        index: i,
        record: rec ?? null,
        primaryPct,
        upperPct,
        amountUsd: rec?.costMicro === null ? "Unresolved" : (costMicro / 1e6).toFixed(4),
        label: rec ? rec.task : `Slot ${i + 1}`,
        state: rec ? rec.state : "Unpaid",
        isCharged,
      };
    });
  }, [records]);

  const defaultPaidIdx = useMemo(() => {
    const firstPaid = capsuleBars.findIndex(b => b.isCharged);
    return firstPaid >= 0 ? firstPaid : 0;
  }, [capsuleBars]);

  const effectiveActiveIdx = activeBarIdx ?? defaultPaidIdx;
  const chargedCount = records.filter(r => (r.costMicro || 0) > 0).length;
  const unpaidCount = records.filter(r => r.state === "Confirmed unpaid").length;
  const activeBar = capsuleBars[Math.min(effectiveActiveIdx, Math.max(0, capsuleBars.length - 1))];

  const providerRows = [
    { name: "Historical Local GPU", sub: "Profiled; not a current eligible quote", price: "Not qualified", icon: "cpu" },
    { name: "Hosted Premium Drafts", sub: "Saved qualification; human review required", price: "Historical", icon: "spark" },
    { name: "Deterministic Tools", sub: "Arithmetic & role checks", price: "$0.0000", icon: "check" },
    { name: "Airwallex Sandbox Hold", sub: "Historical authorization; not an active hold", price: evidence ? `$${evidence.holdUsd.toFixed(2)}` : "$1.00", icon: "wallet" },
    { name: "Airwallex Capture", sub: "Customer closed · retained", price: evidence ? `$${evidence.captureUsd.toFixed(2)}` : "$0.01", icon: "shield" },
    { name: "Merchant MCP Catalog", sub: evidence?.oauthVerified ? "Saved guest OAuth verification" : "OAuth verification unavailable", price: evidence ? `${evidence.products} SKUs` : "Unavailable", icon: "grid" },
  ];

  const ledgerToolbarAndTable = (
    <div className="bento-card bento-ledger-card" id="attempt-ledger">
      <div className="bento-card-head">
        <span className="bento-card-title"><Icon name="ledger" size={14} /> Attempt History &amp; Settlement Receipts</span>
        {view === "dashboard" ? (
          <button type="button" className="bento-viewall-btn" onClick={() => go("ledger")}>
            Open Full Ledger ({records.length}) <Icon name="arrow" size={12} />
          </button>
        ) : (
          <span className="bento-muted-tag mono">{rows.length} / {records.length} SHOWN</span>
        )}
      </div>
      <div className="bento-well ledger-well">
        <div className="ledger-toolbar bento-ledger-toolbar">
          <button type="button" className="bento-viewall-btn" onClick={exportCsv}>Export CSV</button>
          <label className="mono">Sort <select aria-label="Sort ledger" value={sort} onChange={e => setSort(e.target.value)}><option value="recorded">Recorded order</option><option value="task">Task</option><option value="cost">Highest charge</option></select></label>
          <div className="filter-group bento-filter-pills" aria-label="Filter attempts">
            {["all", "charged", "unpaid", "unresolved"].map(f => (
              <button key={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>
                {f === "all" ? "All attempts" : f === "charged" ? "Charged" : f === "unresolved" ? "Unresolved" : "Confirmed unpaid"}
              </button>
            ))}
          </div>
          <label className="bento-search-label">
            <span className="sr-only">Search ledger</span>
            <Icon name="search" size={13} />
            <input
              aria-label="Search ledger"
              placeholder="Search task, provider or receipt…"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </label>
        </div>

        <div className={"table-scroll" + (view === "dashboard" ? " ledger-scroll-frame" : "")}>
          <table className="record-table bento-record-table">
            <thead>
              <tr>
                <th>TASK / SCOPE</th>
                <th>PROVIDER</th>
                <th>STATE</th>
                <th>PROVIDER COST / USDZ</th>
                <th>API ESTIMATE / USD</th>
                <th>RECEIPT</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const badge = providerBadge(row.provider);
                const isCharged = row.state === "Charged";
                const formattedCost = row.costMicro === null ? "Unresolved" : (row.costMicro / 1e6).toFixed(4);
                return (
                  <tr key={row.id}>
                    <td>
                      <div className="tx-cell-main">
                        <span className="tx-icon-sq">
                          <Icon name={badge.icon} size={13} />
                        </span>
                        <div className="tx-task-wrap">
                          <button className="record-link" onClick={() => setSelected(row)}>{row.task}</button>
                          <span className="tx-mobile-meta mono">
                            {row.provider} · {row.state} · {formattedCost === "Unresolved" ? "Unresolved" : `$${formattedCost}`}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td><span className="tx-cat-pill">{row.provider}</span></td>
                    <td>
                      <span className={"state-tag " + (isCharged ? "charged" : "")}>
                        <i className={"state-dot " + (isCharged ? "is-live" : "")} />
                        {row.state}
                      </span>
                    </td>
                    <td className={"mono " + (isCharged ? "tx-neg" : "tx-zero")}>{formattedCost}</td>
                    <td className="mono">
                      {row.apiCreditMicro == null ? "Unreported" : (row.apiCreditMicro / 1e6).toFixed(6)}
                    </td>
                    <td>
                      <button className="receipt-link mono" onClick={() => setSelected(row)}>
                        {row.receipt ? row.receipt.slice(0, 12) + "… ↗" : "Inspect outcome ↗"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {rows.length === 0 && <p className="workspace-empty">No attempts match these filters.</p>}
        </div>
        <p className="table-note mono">
          FAILED CALLS RETAIN THEIR ACTUAL COST. PRECONFIRMATION IS NOT FINAL CLEARING. API CREDIT COSTS ARE ACCOUNTED SEPARATELY.
        </p>
      </div>
    </div>
  );

  const modelSpendUsdz = evidence ? (evidence.comparison ? evidence.comparison.providerUsdz : evidence.modelUsdz) : 0;
  const exposurePct = evidence && evidence.creditCeilingUsd > 0 ? Math.min(100, (evidence.creditUsd / evidence.creditCeilingUsd) * 100) : 0;
  const holdoutPct = evidence ? Math.round((evidence.holdoutCorrect / Math.max(1, evidence.holdoutTotal)) * 100) : 98;

  return (
    <div className="bento-shell section-width">
      <aside className="bento-rail" aria-label="Workspace quick rail">
        <button type="button" className="rail-brand" onClick={() => go("home", "top")} aria-label="Back to landing">
          <span className="rail-logo-mark"><i /></span>
        </button>
        <div className="rail-nav">
          <button
            type="button"
            className={"rail-btn" + (view === "dashboard" ? " is-active" : "")}
            onClick={() => go("dashboard")}
            aria-label="Control Room Overview"
          >
            <Icon name="dashboard" size={18} />
          </button>
          <button
            type="button"
            className={"rail-btn" + (view === "ledger" ? " is-active" : "")}
            onClick={() => go("ledger")}
            aria-label="Transaction Ledger"
          >
            <Icon name="ledger" size={18} />
          </button>
          <button
            type="button"
            className="rail-btn"
            onClick={() => {
              if (view !== "dashboard") go("dashboard", "policy-planner");
              else document.getElementById("policy-planner")?.scrollIntoView({ behavior: "smooth" });
            }}
            aria-label="Policy Spend Planner"
          >
            <Icon name="wallet" size={18} />
          </button>
          <button type="button" className="rail-btn" onClick={() => go("home", "providers")} aria-label="Providers Architecture">
            <Icon name="cpu" size={18} />
          </button>
          <button type="button" className="rail-btn" onClick={() => go("home", "top")} aria-label="Home">
            <Icon name="home" size={18} />
          </button>
        </div>
      </aside>

      <div className="bento-main">
        <div className="bento-topbar">
          <nav className="bento-crumb mono" aria-label="Breadcrumb">
            <button type="button" className="crumb-link" onClick={() => go("home", "top")}>Touchstone</button>
            <span aria-hidden="true">/</span>
            <strong className="crumb-current">{view === "ledger" ? "Transaction Ledger" : "Control Room"}</strong>
          </nav>

          <div className="bento-top-status mono">
            <span className="bento-status-item"><i className="status-dot" /> Metal Testnet · x402</span>
            <span className="bento-status-item">Airwallex Sandbox · Isolated</span>
          </div>
        </div>

        <header className="bento-header">
          <div>
            <p className="eyebrow"><i className="status-dot" /> SAVED SANDBOX / TESTNET EVIDENCE</p>
            <h1>{view === "ledger" ? "Every attempt. On record." : "The control room."}</h1>
            <p>Measured project observations · {evidence?.date || "Loading evidence"}. This public view does not dispatch payments or inference.</p>
          </div>

          <div className="bento-header-right">
            <span className="mini-tag">READ ONLY</span>
            <div className="bento-view-switch">
              <button className={view === "dashboard" ? "selected" : ""} onClick={() => go("dashboard")}>Overview</button>
              <button className={view === "ledger" ? "selected" : ""} onClick={() => go("ledger")}>Transaction ledger</button>
              <a className="bento-catalog-pill" href="/merchant">Sandbox catalog <Icon name="arrow" size={13} /></a>
            </div>
          </div>
        </header>

        {!evidence ? (
          <div className="bento-card"><div className="bento-well workspace-empty" role="status">Saved evidence is loading or unavailable. No transaction is being sent.</div></div>
        ) : (
          <>
            {view === "dashboard" ? (
              <>
                {/* Zone 1: Executive Overview */}
                <section aria-label="Executive Overview" className="bento-zone">
                  <div className="bento-zone-header">
                    <span className="bento-zone-title mono"><Icon name="dashboard" size={13} /> ZONE 01 · EXECUTIVE OVERVIEW</span>
                  </div>

                  <div className="bento-kpi-grid">
                    <div className="bento-card kpi-card">
                      <div className="bento-card-head">
                        <span className="bento-card-title"><Icon name="wallet" size={14} /> Historical Hold (USD)</span>
                        <span className="kpi-delta is-up">Historical</span>
                      </div>
                      <div className="bento-well kpi-well">
                        <SplitMetric value={evidence.holdUsd} prefix="$" decimals={2} />
                        <KpiMeter pct={evidence.holdUsd > 0 ? Math.max(8, (evidence.captureUsd / evidence.holdUsd) * 100) : 100} tone="emerald" />
                        <div className="kpi-foot">
                          <span className="muted">Captured ${evidence.captureUsd.toFixed(2)} USD</span>
                          <span className="mono muted">Sandbox</span>
                        </div>
                      </div>
                    </div>

                    <div className="bento-card kpi-card">
                      <div className="bento-card-head">
                        <span className="bento-card-title"><Icon name="ledger" size={14} /> Model Spend (USDZ)</span>
                        <span className="kpi-delta is-up">x402 Rail</span>
                      </div>
                      <div className="bento-well kpi-well">
                        <SplitMetric value={modelSpendUsdz} prefix="$" decimals={3} />
                        <KpiMeter pct={records.length ? chargedCount / records.length * 100 : 0} tone="neutral" />
                        <div className="kpi-foot">
                          <span className="muted">{evidence.comparison?.paidReceipts ?? chargedCount} paid receipts</span>
                          <span className="mono muted">Provider charges only</span>
                        </div>
                      </div>
                    </div>

                    <div className="bento-card kpi-card">
                      <div className="bento-card-head">
                        <span className="bento-card-title"><Icon name="check" size={14} /> Strict Draft Quality</span>
                        <span className="kpi-delta is-up">{holdoutPct}% Holdout</span>
                      </div>
                      <div className="bento-well kpi-well">
                        <span className="split-num">
                          {evidence.calibrationCorrect}
                          <span className="split-dec">/{evidence.calibrationTotal}</span>
                        </span>
                        <KpiMeter pct={(evidence.calibrationCorrect / Math.max(1, evidence.calibrationTotal)) * 100} tone="emerald" />
                        <div className="kpi-foot">
                          <span className="muted">Holdout {evidence.holdoutCorrect}/{evidence.holdoutTotal}</span>
                          <span className="mono muted">Human review required</span>
                        </div>
                      </div>
                    </div>

                    <div className="bento-card kpi-card">
                      <div className="bento-card-head">
                        <span className="bento-card-title"><Icon name="shield" size={14} /> API Exposure</span>
                        <span className="kpi-delta is-warn">Capped</span>
                      </div>
                      <div className="bento-well kpi-well">
                        <SplitMetric value={evidence.creditUsd} prefix="$" decimals={3} />
                        <KpiMeter pct={exposurePct} tone="amber" />
                        <div className="kpi-foot">
                          <span className="muted">Ceiling ${evidence.creditCeilingUsd.toFixed(2)} USD</span>
                          <span className="mono muted">{Math.round(exposurePct)}% used</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bento-row-mid bento-row-2">
                    <div className="bento-card">
                      <div className="bento-card-head">
                        <span className="bento-card-title"><Icon name="dashboard" size={14} /> Attempt &amp; Settlement Flow</span>
                        <div className="capsule-legend mono">
                          <span><i className="leg-dot is-paid" /> Paid USDZ</span>
                          <span>First {Math.min(28, records.length)} attempts</span>
                          <span><i className="leg-dot is-held" /> Unpaid</span>
                        </div>
                      </div>
                      <div className="bento-well capsule-well">
                        <div className="capsule-stage">
                          {activeBar && (
                            <div
                              className="capsule-tooltip"
                              style={{ left: `clamp(0px, ${(activeBar.index / 27) * 82}%, calc(100% - 172px))` }}
                            >
                              <div className="cap-tip-head">
                                <span>{activeBar.label}</span>
                                <i className={activeBar.isCharged ? "is-charged" : ""} />
                              </div>
                              <strong>{activeBar.amountUsd} USDZ · {activeBar.state}</strong>
                            </div>
                          )}
                          <div className="capsule-grid" aria-label="Interactive attempt telemetry chart">
                            {capsuleBars.map(bar => (
                              <button
                                type="button"
                                key={bar.index}
                                className={"capsule-col" + (effectiveActiveIdx === bar.index ? " is-active" : "") + (bar.isCharged ? " is-paid" : " is-unpaid")}
                                onMouseEnter={() => setActiveBarIdx(bar.index)}
                                onFocus={() => setActiveBarIdx(bar.index)}
                                onClick={() => bar.record && setSelected(bar.record)}
                                aria-label={`${bar.label}: ${bar.amountUsd}`}
                              >
                                <span className="cap-upper" style={{ height: `${bar.upperPct}%` }} />
                                <span className="cap-lower" style={{ height: `${bar.primaryPct}%` }} />
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="capsule-axis mono">
                          <span>First recorded attempt</span>
                          <span>Recorded order · USDZ only</span>
                        </div>
                      </div>
                    </div>

                    <div className="bento-card">
                      <div className="bento-card-head">
                        <span className="bento-card-title"><Icon name="wallet" size={14} /> Historical Rails &amp; Guardrails</span>
                        <span className="bento-pill-tag mono">{records.length} Attempts</span>
                      </div>
                      <div className="bento-well pill-list-well">
                        {providerRows.map(item => (
                          <div className="pill-list-row" key={item.name}>
                            <span className="pill-row-sq">
                              <Icon name={item.icon} size={14} />
                            </span>
                            <div className="pill-row-copy">
                              <strong>{item.name}</strong>
                              <small>{item.sub}</small>
                            </div>
                            <span className="pill-row-val mono">{item.price}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="bento-row-bot bento-row-2-even">
                    <div className="bento-card">
                      <div className="bento-card-head">
                        <span className="bento-card-title"><Icon name="check" size={14} /> Qualification Benchmarks</span>
                        <span className="mini-tag">UNCHANGED SPECS</span>
                      </div>
                      <div className="bento-well rings-well">
                        <div className="goal-ring-pair">
                          <div className="goal-ring-row">
                            <div>
                              <strong>Calibration Trials</strong>
                              <small className="mono">{evidence.calibrationCorrect} / {evidence.calibrationTotal} strict</small>
                            </div>
                            <RingProgress pct={Math.round(evidence.calibrationCorrect / Math.max(1, evidence.calibrationTotal) * 100)} color="#34d399" />
                          </div>
                          <div className="goal-ring-row">
                            <div>
                              <strong>Untouched Holdout</strong>
                              <small className="mono">{evidence.holdoutCorrect} / {evidence.holdoutTotal} strict; reviewed drafts</small>
                            </div>
                            <RingProgress pct={holdoutPct} color="#e5a95d" />
                          </div>
                        </div>
                        <div className="trial-grid bento-trial-grid" aria-hidden="true">
                          {Array.from({ length: evidence.holdoutTotal }, (_, i) => (
                            <i className={i >= evidence.holdoutCorrect ? "interrupted" : ""} key={i} />
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="bento-card">
                      <div className="bento-card-head">
                        <span className="bento-card-title"><Icon name="ledger" size={14} /> Recent Attempts</span>
                        <button type="button" className="bento-viewall-btn" onClick={() => go("ledger")}>View All {records.length} <Icon name="arrow" size={12} /></button>
                      </div>
                      <div className="bento-well recent-well">
                        <div className="recent-tx-grid">
                          {records.slice(0, 6).map(rec => {
                            const badge = providerBadge(rec.provider);
                            const isCharged = rec.state === "Charged";
                            return (
                              <button type="button" className="recent-tx-chip" key={rec.id} onClick={() => setSelected(rec)}>
                                <span className="tx-icon-sq">
                                  <Icon name={badge.icon} size={13} />
                                </span>
                                <div className="recent-tx-copy">
                                  <strong>{rec.task}</strong>
                                  <small>{rec.provider} · {rec.state}</small>
                                </div>
                                <span className={"recent-tx-amt mono" + (isCharged ? "" : " tx-zero")}>
                                  {rec.costMicro === null ? "Unresolved" : `${(rec.costMicro / 1e6).toFixed(4)} USDZ`}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                {/* Zone 2: Policy Studio */}
                <div className="bento-zone">
                  <div className="bento-zone-header">
                    <span className="bento-zone-title mono"><Icon name="spark" size={13} /> ZONE 02 · POLICY STUDIO &amp; MODEL BENCHMARK</span>
                  </div>
                  <PolicyComparison
                    data={evidence.comparison}
                    calibration={`${evidence.calibrationCorrect} / ${evidence.calibrationTotal}`}
                    holdout={`${evidence.holdoutCorrect} / ${evidence.holdoutTotal}`}
                  />
                </div>

                {/* Zone 3: Settlement Ledger */}
                <div className="bento-zone">
                  <div className="bento-zone-header">
                    <span className="bento-zone-title mono"><Icon name="ledger" size={13} /> ZONE 03 · SETTLEMENT LEDGER &amp; VERIFIED RECEIPTS</span>
                  </div>
                  {ledgerToolbarAndTable}
                </div>
              </>
            ) : (
              <div className="bento-ledger-hero-view">
                {ledgerToolbarAndTable}

                <div className="bento-ledger-supporting-grid">
                  <div className="bento-card">
                    <div className="bento-card-head">
                      <span className="bento-card-title"><Icon name="spark" size={14} /> Settlement Audit</span>
                      <span className="bento-pill-tag mono">{records.length} TOTAL</span>
                    </div>
                    <div className="bento-well insight-spotlight">
                      <div className="spotlight-rings" aria-hidden="true" />
                      <div className="spotlight-copy">
                        <strong>{chargedCount} Paid · {unpaidCount} Confirmed Unpaid</strong>
                        <p>Every attempt retains its real provider cost and verification state. Rejected outputs can still carry an expense on the ledger.</p>
                      </div>
                      <button type="button" className="ask-ai-btn" onClick={() => go("dashboard", "policy-planner")}>
                        View Policy Analysis <Icon name="arrow" size={14} />
                      </button>
                    </div>
                  </div>

                  <div className="bento-card">
                    <div className="bento-card-head">
                      <span className="bento-card-title"><Icon name="wallet" size={14} /> Rail Separation Proof</span>
                      <span className="mini-tag">METAL + FIAT</span>
                    </div>
                    <div className="bento-well saving-well">
                      <p>Integrated sandbox payment authorized ${evidence.holdUsd.toFixed(2)} USD and captured ${evidence.captureUsd.toFixed(2)} USD, completely separate from x402 testnet spend.</p>
                      <div className="saving-big">
                        <strong>${evidence.modelUsdz.toFixed(2)}</strong>
                        <span>/ USDZ recorded integrated purchase</span>
                      </div>
                      <a className="bento-link-subtle" href="/merchant">
                        Inspect {evidence.products}-SKU Sandbox Catalog <Icon name="arrow" size={13} />
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <details className="bento-card saved-evidence-details" onToggle={e => setDetailsOpen(e.currentTarget.open)}>
              <summary className="bento-card-head">Detailed evidence, benchmarks &amp; transaction explorer</summary>
              <p className="table-note">All existing transaction fields, benchmarks and integration evidence remain available below. Saved evidence only; payment and signing controls stay disabled.</p>
              {detailsOpen && <iframe key={view} src={"/site/dashboard/index.html" + (view === "ledger" ? "#transactions" : "#v-overview")} title={view === "ledger" ? "Touchstone saved transaction ledger" : "Touchstone saved dashboard"} sandbox="allow-scripts allow-same-origin allow-downloads" />}
            </details>
          </>
        )}

        <dialog
          ref={dialog}
          className="receipt-dialog"
          onClose={() => setSelected(null)}
          onClick={e => {
            if (e.target === e.currentTarget) dialog.current?.close();
          }}
        >
          <div className="receipt-dialog-heading">
            <p className="eyebrow">SAVED ATTEMPT / RECEIPT</p>
            <button aria-label="Close receipt" onClick={() => dialog.current?.close()}><Icon name="close" /></button>
          </div>
          {selected && (
            <>
              <div className="receipt-title-row">
                <h2>{selected.task}</h2>
                <span className={"state-tag " + (selected.state === "Charged" ? "charged" : "")}>
                  <i className={"state-dot " + (selected.state === "Charged" ? "is-live" : "")} />
                  {selected.state}
                </span>
              </div>
              <dl className="receipt-kv-grid">
                <div><dt>Provider</dt><dd className="mono">{selected.provider}</dd></div>
                <div><dt>State</dt><dd className="mono">{selected.state}</dd></div>
                <div><dt>Cost / USDZ</dt><dd className="mono">{selected.costMicro === null ? "Unresolved" : (selected.costMicro / 1e6).toFixed(6)}</dd></div>
                <div><dt>API estimate / USD</dt><dd className="mono">{selected.apiCreditMicro == null ? "Unreported; allowance retained" : (selected.apiCreditMicro / 1e6).toFixed(6)}</dd></div>
              </dl>
              <div className="receipt-hash-label mono">RECORDED RECEIPT REFERENCE</div>
              <p className="receipt-id mono">{selected.receipt || "No paid receipt recorded"}</p>
              <p className="receipt-note">{selected.verification}. No refund or invoice payment is inferred.</p>
            </>
          )}
        </dialog>
      </div>
    </div>
  );
}
