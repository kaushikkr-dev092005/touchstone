import { Icon } from "./Identity";
import type { Go } from "@/siteTypes";

export const GITHUB_URL = "https://github.com/kaushikkr-dev092005/touchstone";

const steps = [
  { n: "01", title: "Source", text: "The agent reserves the cost against an approved budget, then buys one call over x402 from an allowlisted provider. Per-call and aggregate caps apply before dispatch." },
  { n: "02", title: "Verify", text: "Each answer is checked against its source: cited spans, field roles and arithmetic. Candidate, review and rejected stay separate outcomes." },
  { n: "03", title: "Settle", text: "The receipt, actual cost and verdict go to the ledger. A rejected answer can still cost money, so it stays on the record too." },
];

const sampleRows = [
  ["job-07 / req-01", "local-gpu", "Charged", "0.0100", "Candidate"],
  ["job-07 / req-01 (retry)", "—", "Replayed", "0.0000", "Original receipt returned"],
  ["job-08 / req-01", "hosted", "Charged", "0.0100", "Rejected"],
  ["job-08 / req-02", "hosted", "Unknown", "reserved", "Held until reconciled"],
];

const providers = [
  { tag: "LOCAL GPU", title: "RTX 3050 Laptop GPU", text: "A small instruct model served by llama.cpp (Vulkan) on a 4 GB laptop GPU, with conservative temperature supervision. It runs on the project machine behind the same provider interface as hosted models.", foot: "llama.cpp · Qwen2.5 Q4_K_M profiles" },
  { tag: "HOSTED", title: "Qualified hosted model", text: "Escalation goes to a hosted model only after it passes unchanged qualification criteria on calibration and untouched holdout sets. Its drafts still go to review.", foot: "Explicit escalation · review drafts" },
  { tag: "TOOLS", title: "Deterministic local tools", text: "Arithmetic and source checks that cost nothing per call. The tools-only, cheapest, premium and ladder policies are compared on matched tasks.", foot: "Matched policy comparison" },
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
      <section className="lp-section" id="how" aria-labelledby="how-title">
        <p className="lp-kicker mono">HOW IT WORKS</p>
        <h2 id="how-title">Source. Verify. Settle.</h2>
        <ol className="lp-steps">{steps.map((s, i) => <li key={s.n}><span className="mono">{s.n}</span><h3>{s.title}</h3><p>{s.text}</p>{i < steps.length - 1 && <i className="lp-step-arrow" aria-hidden="true" />}</li>)}</ol>
      </section>

      <section className="lp-section lp-ledger" id="ledger-guarantee" aria-labelledby="ledger-title">
        <div>
          <p className="lp-kicker mono">THE LEDGER</p>
          <h2 id="ledger-title">One request.<br />One record.</h2>
          <p>Each purchase reserves its cost under an idempotency key before dispatch. A retried key finds the original receipt instead of buying again. An unknown outcome stays reserved until it is reconciled. Amounts are integer micro-units, and the audit history is hash-chained.</p>
          <p className="lp-boundary">These are local ledger guarantees. External rails keep their own replay semantics; Touchstone does not claim exactly-once effects on them.</p>
          <button className="lp-link" onClick={() => go("ledger")}>Inspect the recorded ledger <Icon name="arrow" size={15} /></button>
        </div>
        <figure className="lp-sample">
          <figcaption><span className="mono">IDEMPOTENT ATTEMPTS</span><span className="lp-sample-tag mono">SAMPLE DATA</span></figcaption>
          <div className="lp-table-scroll"><table>
            <thead><tr><th>Key</th><th>Provider</th><th>State</th><th>USDZ</th><th>Outcome</th></tr></thead>
            <tbody>{sampleRows.map(r => <tr key={r[0]}>{r.map((c, i) => <td key={i} className={i === 3 ? "mono" : i === 2 ? "lp-state lp-state-" + c.toLowerCase() : ""}>{c}</td>)}</tr>)}</tbody>
          </table></div>
          <p className="mono lp-sample-note">ILLUSTRATIVE ROWS. RECORDED EVIDENCE LIVES IN THE LEDGER VIEW.</p>
        </figure>
      </section>

      <section className="lp-section" id="providers" aria-labelledby="providers-title">
        <p className="lp-kicker mono">PROVIDERS</p>
        <h2 id="providers-title">Real providers, bought one call at a time.</h2>
        <div className="lp-providers">{providers.map((p, i) => <article key={p.tag} className={i === 0 ? "is-local" : ""}><span className="mono lp-provider-tag">{p.tag}</span><h3>{p.title}</h3><p>{p.text}</p><span className="mono lp-provider-foot">{p.foot}</span></article>)}</div>
      </section>
    </div>
  </>;
}
