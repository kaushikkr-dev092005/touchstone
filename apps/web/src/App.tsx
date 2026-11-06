import { useEffect, useRef, useState } from "react";
import Vault from "@/components/Vault";
import { prefersReduced, useInView } from "@/hooks/useInView";

const DASHBOARD = "/";

function Arrow({ down = false }: { down?: boolean }) {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" className={down ? "arrow-down" : undefined}><path d="M4 12 12 4M4.5 4H12v7.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

function Mark() {
  return <svg width="31" height="33" viewBox="0 0 31 33" fill="none" aria-hidden="true"><path d="m4 5 23-4v27L4 32V5Z" fill="currentColor" /><path d="M11 28 21 4" stroke="white" strokeWidth="1.8" /></svg>;
}

function Navigation() {
  const [menuOpen, setMenuOpen] = useState(false);
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) {
        setMenuOpen(false);
        root.current?.querySelectorAll("details[open]").forEach(node => node.removeAttribute("open"));
      }
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, []);

  return <header className="site-header" ref={root} onKeyDown={event => {
    if (event.key === "Escape") {
      setMenuOpen(false);
      root.current?.querySelectorAll("details[open]").forEach(node => node.removeAttribute("open"));
    }
  }}>
    <div className="header-inner">
      <a className="brand" href="#top" aria-label="Touchstone home"><Mark /><span>touchstone</span></a>
      <nav className={`primary-nav${menuOpen ? " is-open" : ""}`} id="primary-nav" aria-label="Main navigation">
        <details className="nav-disclosure"><summary>Product <span aria-hidden="true">⌄</span></summary><div className="nav-popover">
          <a href="#control-layer" onClick={() => setMenuOpen(false)}><strong>The control layer</strong><span>Mandates, verification and records.</span></a>
          <a href={DASHBOARD}><strong>Interactive dashboard</strong><span>Explore the labelled simulated demo.</span></a>
        </div></details>
        <a href="#how-it-works" onClick={() => setMenuOpen(false)}>How it works</a>
        <a href="#evidence" onClick={() => setMenuOpen(false)}>Evidence</a>
        <a href={`${DASHBOARD}#feature-evidence`}>Developers <Arrow /></a>
      </nav>
      <div className="header-actions"><a className="button button-dark header-cta" href={DASHBOARD}>Open dashboard <Arrow /></a><button className="menu-toggle" aria-controls="primary-nav" aria-expanded={menuOpen} aria-label={menuOpen ? "Close navigation" : "Open navigation"} onClick={() => setMenuOpen(!menuOpen)}><span /><span /></button></div>
    </div>
  </header>;
}

function Hero() {
  const [open, setOpen] = useState(prefersReduced);
  const [figure, visible] = useInView<HTMLElement>("0px", true);
  const touched = useRef(false);

  useEffect(() => {
    if (!visible || touched.current || prefersReduced()) return;
    const timer = setTimeout(() => { if (!touched.current) setOpen(true); }, 950);
    return () => clearTimeout(timer);
  }, [visible]);

  const toggle = (next: boolean) => { touched.current = true; setOpen(next); };

  return <section className="hero section-width" id="top" aria-labelledby="hero-title">
    <div className="hero-copy">
      <p className="eyebrow"><span className="tiny-mark" aria-hidden="true" />THE FINANCIAL TRUST LAYER</p>
      <h1 id="hero-title">Agent spending.<br />Human control<span className="title-period">.</span></h1>
      <p className="hero-description">Give autonomous agents room to work, with clear limits on what they can spend. Touchstone checks the work and keeps a record of every attempt.</p>
      <div className="hero-actions"><a href={DASHBOARD} className="button button-dark">Explore the dashboard <Arrow /></a><a href="#how-it-works" className="text-link">See how it works <Arrow down /></a></div>
      <p className="hero-disclosure"><span className="mode-symbol" aria-hidden="true" />Sandbox banking. Testnet payments. A clearly labelled demo.</p>
    </div>
    <figure className="hero-locker" ref={figure} aria-label="Interactive isometric locker illustration">
      <div className="locker-art">
        <svg className="locker-ground" viewBox="0 0 700 600" aria-hidden="true"><g fill="none" stroke="currentColor" strokeWidth=".65"><path d="m23 366 304 176 347-200M58 432l305 176M104 292l499 288" strokeDasharray="2 6" /><path d="m82 353 6-4 6 4-6 4-6-4Zm527 78 6-4 6 4-6 4-6-4Z" /></g></svg>
        <Vault open={open} onOpenChange={toggle} />
        <span className="art-register art-register-top mono" aria-hidden="true">TS—01 / CONTROL</span>
        <span className="art-register art-register-side" aria-hidden="true">+</span>
      </div>
      <figcaption className="locker-caption"><span className="mono"><i aria-hidden="true" />ILLUSTRATIVE DEMO</span><button className="locker-toggle" onClick={() => toggle(!open)} aria-pressed={open}>{open ? "Close locker" : "Open locker"}<span className={open ? "control-glyph is-open" : "control-glyph"} aria-hidden="true">+</span></button></figcaption>
    </figure>
    <div className="hero-footnote"><span className="mono">01 — A MANDATE BEFORE A PURCHASE</span><span>Built to act within boundaries.</span><a href="#control-layer" aria-label="Scroll to the control layer"><Arrow down /></a></div>
  </section>;
}

function IntegrationStrip() {
  return <section className="integration-strip" aria-labelledby="integration-title"><div className="section-width integration-inner">
    <h2 className="mono" id="integration-title">ONE CONTROL LAYER.<br />SEPARATE SYSTEMS.</h2>
    <div className="integration-name"><strong>Airwallex</strong><span className="mono">SANDBOX BANKING</span></div>
    <div className="integration-name metal-name"><strong>Metal <span>/ x402</span></strong><span className="mono">TESTNET PAYMENTS</span></div>
    <div className="integration-name"><strong>llama.cpp</strong><span className="mono">LOCAL INFERENCE</span></div>
    <div className="integration-name ledger-name"><strong><svg width="22" height="24" viewBox="0 0 22 24" fill="none" aria-hidden="true"><path d="M3 2h15v20H3zM6 7h9M6 12h9M6 17h5" stroke="currentColor" strokeWidth="1.7" /></svg>SQLite</strong><span className="mono">DURABLE RECORDS</span></div>
  </div></section>;
}

const steps = [
  { number: "01", title: "Set the boundaries.", description: "A budget, a provider allowlist and a maximum call price. The mandate defines what an agent is allowed to buy.", detail: "MANDATE → RESERVATION", symbol: "boundary" },
  { number: "02", title: "Question the purchase.", description: "Use a deterministic tool when it can do the job. Require model qualification, then check the paid result against its source.", detail: "TOOLS → QUALIFICATION → CHECK", symbol: "check" },
  { number: "03", title: "Keep every receipt.", description: "Preserve the cost, result and financial state. An uncertain payment pauses for recovery; a rejected answer remains an expense.", detail: "RECEIPT → RECONCILIATION", symbol: "record" },
];

function ControlLayer() {
  return <section className="control-section section-width" id="control-layer" aria-labelledby="control-title">
    <div className="section-heading"><div><p className="eyebrow">AUTONOMY, WITH ACCOUNTABILITY</p><h2 id="control-title">Let the agent do the work.<br />Keep the terms in your hands.</h2></div><p>Decisions can be autonomous.<br />Spending limits stay in code.</p></div>
    <div className="process-grid" id="how-it-works">{steps.map(step => <article className="process-step" key={step.number}>
      <div className="step-top"><span className="mono">/{step.number}</span><svg viewBox="0 0 48 48" width="48" height="48" fill="none" aria-hidden="true">{step.symbol === "boundary" ? <><rect x="8" y="8" width="32" height="32" rx="1" stroke="currentColor" /><path d="M16 12v24m8-24v24m8-24v24" stroke="currentColor" strokeDasharray="1 3" /><path d="M12 24h24" stroke="currentColor" /></> : step.symbol === "check" ? <><circle cx="23" cy="23" r="15" stroke="currentColor" /><path d="m16 23 5 5 10-11m3 17 7 7" stroke="currentColor" strokeWidth="1.4" /></> : <><path d="M12 6h24v36l-4-3-4 3-4-3-4 3-4-3-4 3V6Z" stroke="currentColor" /><path d="M18 15h12m-12 7h12m-12 7h7" stroke="currentColor" /></>}</svg></div>
      <h3>{step.title}</h3><p>{step.description}</p><div className="step-detail mono">{step.detail}</div>
    </article>)}</div>
  </section>;
}

function Evidence() {
  return <section className="evidence-section" id="evidence" aria-labelledby="evidence-title"><div className="section-width evidence-inner">
    <div className="evidence-copy"><p className="eyebrow">THE RECORD IS THE POINT</p><h2 id="evidence-title">Proof, with<br />a paper trail.</h2><p>Real observations deserve precise labels. Explore the saved sandbox and testnet records alongside the separate simulated workflow.</p><a href={`${DASHBOARD}#feature-evidence`} className="text-link">Inspect the evidence <Arrow /></a></div>
    <div className="proof-tape"><a href={DASHBOARD} className="proof-row"><span className="proof-number mono">01</span><div><span className="proof-mode mono">MEASURED · AIRWALLEX SANDBOX</span><h3>A conversion, reconciled.</h3><p>1.00 USD → 0.89 EUR. Settled and matched to wallet history.</p></div><Arrow /></a><a href={DASHBOARD} className="proof-row"><span className="proof-number mono">02</span><div><span className="proof-mode mono">MEASURED · METAL TESTNET</span><h3>A paid call, recovered.</h3><p>Hard process death. Original receipt recovered without a duplicate observed.</p></div><Arrow /></a><a href={`${DASHBOARD}#feature-evidence`} className="proof-row"><span className="proof-number mono">03</span><div><span className="proof-mode mono">MEASURED · SAVED FAULT EVIDENCE</span><h3>A wrong answer, recorded.</h3><p>The source totals 2,000 cents. The model claimed 1,250. The charge remains.</p></div><Arrow /></a><p className="evidence-limit mono">TESTNET RECEIPTS ARE PRECONFIRMED. FINAL SETTLEMENT IS NOT INDEPENDENTLY PROVEN.</p></div>
  </div></section>;
}

export default function App() {
  return <><a href="#hero-title" className="skip-link">Skip to content</a><Navigation /><main><Hero /><IntegrationStrip /><ControlLayer /><Evidence /><section className="closing section-width"><p className="eyebrow">PAY FOR PROOF, NOT PROMISES.</p><h2>See the controls at work.</h2><a href={DASHBOARD} className="button button-dark">Open the dashboard <Arrow /></a><p>Provider payment precedes verification. No refund is implied.</p></section></main><footer className="footer section-width"><a className="brand footer-brand" href="#top"><Mark /><span>touchstone</span></a><span className="mono">SANDBOX · TESTNET · SIMULATED DEMO</span><a href="#top">Back to top <Arrow /></a></footer></>;
}
