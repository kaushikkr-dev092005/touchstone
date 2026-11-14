import { Icon } from "./Identity";
import type { Go } from "@/siteTypes";

export const GITHUB_URL = "https://github.com/kaushikkr-dev092005/touchstone";

const proofStats = [
  { metric: "120 / 120", label: "Strict Calibration", note: "100% deterministic pass rate under frozen task specs" },
  { metric: "59 / 60", label: "Untouched Holdout", note: "Zero false accepts · 1 provider timeout isolated" },
  { metric: "−54%", label: "Ladder Spend Cut", note: "$0.060 vs $0.130 USDZ across 64 matched runs" },
  { metric: "$1.00", label: "Sandbox Hold", note: "$0.01 USD captured · strictly separate from x402 rail" },
];

const steps = [
  {
    n: "STEP 01",
    icon: "wallet",
    title: "Source",
    text: "Reserve the per-call ceiling under an EIP-712 budget key before buying one call over x402 from an allowlisted provider.",
    spec: "EIP-712 Budget Hold · x402",
  },
  {
    n: "STEP 02",
    icon: "shield",
    title: "Verify",
    text: "Check every response against cited spans, field roles and deterministic arithmetic. Candidate, review and rejected stay separate.",
    spec: "Cited Spans · Field Roles · Math",
  },
  {
    n: "STEP 03",
    icon: "ledger",
    title: "Settle",
    text: "Commit the cryptographic receipt, provider USDZ cost and verdict to a hash-chained integer micro-unit ledger — even on failure.",
    spec: "Hash-Chained Micro-Unit Ledger",
  },
];

const sampleRows = [
  ["job-07 / req-01", "local-gpu", "Charged", "0.0100", "Candidate verified"],
  ["job-07 / req-01 (retry)", "—", "Replayed", "0.0000", "Original receipt returned"],
  ["job-08 / req-01", "hosted", "Charged", "0.0100", "Rejected by verifier"],
  ["job-08 / req-02", "hosted", "Unknown", "reserved", "Held until reconciled"],
];

const providers = [
  {
    tag: "LOCAL GPU",
    icon: "cpu",
    title: "RTX 3050 Laptop GPU",
    text: "Small instruct models served by llama.cpp (Vulkan) on a 4 GB local GPU with conservative thermal supervision behind a unified provider interface.",
    price: "$0.0050 USDZ / call",
    foot: "llama.cpp · Qwen2.5 Q4_K_M",
  },
  {
    tag: "HOSTED",
    icon: "spark",
    title: "Qualified hosted model",
    text: "Escalation routes to a hosted model only after passing calibration and untouched holdout criteria. Drafts remain subject to review.",
    price: "$0.0100 USDZ / call",
    foot: "Explicit escalation · Review drafts",
  },
  {
    tag: "TOOLS",
    icon: "check",
    title: "Deterministic local tools",
    text: "Zero-marginal-cost arithmetic and structural verification tools benchmarked head-to-head against always-cheapest and always-premium policies.",
    price: "$0.0000 USDZ / call",
    foot: "Matched 4-policy study",
  },
];

export default function Landing({ go }: { go: Go }) {
  return <>
    <section className="lp-hero" id="top" aria-labelledby="hero-title">
      <div className="lp-badge" data-reveal="badge"><span>Airwallex Agentic Banking Hackathon 2026 · Kit 12</span></div>
      <h1 id="hero-title" className="lp-title">
        <span className="lp-line"><span data-reveal="line">Buy inference.</span></span>
        <span className="lp-line"><span data-reveal="line">Prove it passes.</span></span>
      </h1>
      <p className="lp-sub" data-reveal="sub">Touchstone buys LLM inference per call over x402 within an approved budget, checks every answer against its source, and records each attempt in a durable ledger, whether it was paid, failed or rejected.</p>
      <div className="lp-ctas">
        <button className="lp-btn lp-btn-primary" data-reveal="cta" onClick={() => go("dashboard")}>Open Dashboard</button>
        <a className="lp-btn lp-btn-secondary" data-reveal="cta" href={GITHUB_URL} target="_blank" rel="noreferrer">View on GitHub</a>
      </div>
      <div className="lp-built" data-reveal="built"><span>Built with</span><ul><li>Airwallex</li><li>x402</li><li>Metal testnet</li></ul></div>
    </section>

    <div className="lp-below" data-reveal="below">
      <section className="lp-section lp-proof-wrap" aria-label="Verified benchmark highlights">
        <div className="lp-proof-strip">
          {proofStats.map(s => (
            <div className="bento-card lp-proof-card" key={s.label}>
              <div className="bento-well lp-proof-well">
                <strong className="mono">{s.metric}</strong>
                <span>{s.label}</span>
                <small>{s.note}</small>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section" id="how" aria-labelledby="how-title">
        <p className="lp-kicker mono">HOW IT WORKS</p>
        <h2 id="how-title">Source. Verify. Settle.</h2>
        <ol className="lp-steps">
          {steps.map(s => (
            <li className="bento-card lp-step-card" key={s.n}>
              <div className="bento-well lp-step-well">
                <div className="lp-step-top">
                  <span className="mono lp-step-num">{s.n}</span>
                  <span className="tx-icon-sq"><Icon name={s.icon} size={14} /></span>
                </div>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
                <div className="lp-step-spec mono">{s.spec}</div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="lp-section lp-ledger" id="ledger-guarantee" aria-labelledby="ledger-title">
        <div>
          <p className="lp-kicker mono">THE LEDGER</p>
          <h2 id="ledger-title">One request.<br />One record.</h2>
          <p>Each purchase reserves its cost under an idempotency key before dispatch. A retried key finds the original receipt instead of buying again. An unknown outcome stays reserved until it is reconciled. Amounts are integer micro-units, and the audit history is hash-chained.</p>
          <p className="lp-boundary">These are local ledger guarantees. External rails keep their own replay semantics; Touchstone does not claim exactly-once effects on them.</p>
          <button className="lp-link" onClick={() => go("ledger")}>Inspect the recorded ledger <Icon name="arrow" size={15} /></button>
        </div>
        <figure className="bento-card lp-sample">
          <figcaption className="bento-card-head">
            <span className="mono lp-sample-title">IDEMPOTENT STATE TRANSITIONS</span>
            <span className="mini-tag">PROTOCOL MODEL</span>
          </figcaption>
          <div className="bento-well lp-sample-well">
            <div className="lp-table-scroll">
              <table>
                <thead><tr><th>Key</th><th>Provider</th><th>State</th><th>USDZ</th><th>Outcome</th></tr></thead>
                <tbody>
                  {sampleRows.map(r => (
                    <tr key={r[0]}>
                      {r.map((c, i) => (
                        <td
                          key={i}
                          className={
                            i === 3 ? "mono"
                              : i === 2 ? "lp-state lp-state-" + c.toLowerCase()
                                : ""
                          }
                        >
                          {c}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mono lp-sample-note">REPRESENTATIVE STATE TRANSITIONS · FULL 43-ATTEMPT RECORDED EVIDENCE IN LEDGER VIEW.</p>
          </div>
        </figure>
      </section>

      <section className="lp-section" id="providers" aria-labelledby="providers-title">
        <p className="lp-kicker mono">PROVIDERS</p>
        <h2 id="providers-title">Real providers, bought one call at a time.</h2>
        <div className="lp-providers">
          {providers.map(p => (
            <article className="bento-card" key={p.tag}>
              <div className="bento-well lp-provider-well">
                <div className="lp-provider-head">
                  <span className="mono lp-provider-tag">{p.tag}</span>
                  <span className="tx-icon-sq"><Icon name={p.icon} size={14} /></span>
                </div>
                <h3>{p.title}</h3>
                <p>{p.text}</p>
                <div className="lp-provider-meta">
                  <strong className="mono">{p.price}</strong>
                  <span className="mono lp-provider-foot">{p.foot}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-section lp-closing-section" aria-label="Open Control Room">
        <div className="bento-card lp-closing-card">
          <div className="bento-well lp-closing-well">
            <div>
              <p className="lp-kicker mono">CONTROL ROOM</p>
              <h2>Every call verified.<br />Every cent on record.</h2>
              <p>Inspect live 4-policy benchmarks, calibration trials, and cryptographic payment receipts in the Control Room.</p>
            </div>
            <div className="lp-closing-actions">
              <button className="lp-btn lp-btn-primary" onClick={() => go("dashboard")}>Open Control Room</button>
              <button className="lp-btn lp-btn-secondary" onClick={() => go("ledger")}>Explore 43 Receipts</button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </>;
}
