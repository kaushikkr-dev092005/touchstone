import React, { useEffect, useRef, useState } from "react";
import Landing, { GITHUB_URL } from "@/components/Landing";
import BlackHole from "@/cinematic/blackhole/BlackHole";
import Director, { type DirectorApi } from "@/cinematic/Director";
import Workspace from "@/components/Workspace";
import { Brand, Icon } from "@/components/Identity";
import { prefersReduced } from "@/hooks/useInView";
import type { Evidence, Go, View } from "@/siteTypes";
import ControlRoom from "@/components/ControlRoom";

const currentView = (): View => /\/(dashboard|ledger)\/?$/.test(location.pathname) ? location.pathname.includes("ledger") ? "ledger" : "dashboard" : "home";

function PillNav({ view, go }: { view: View; go: Go }) {
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [view]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, []);
  const links: { label: string; href: string; onClick?: () => void; current?: boolean; external?: boolean }[] = [
    { label: "How it works", href: "/site/#how", onClick: () => go("home", "how") },
    { label: "Providers", href: "/site/#providers", onClick: () => go("home", "providers") },
    { label: "Ledger", href: "/ledger", onClick: () => go("ledger"), current: view === "ledger" },
    { label: "GitHub", href: GITHUB_URL, external: true },
  ];
  return <header className="pill-nav-wrap" data-reveal="nav"><nav className="pill-nav" aria-label="Main navigation">
    <a href="/site/" className="pill pill-logo" onClick={e => { e.preventDefault(); go("home", "top"); }} aria-label="Touchstone home"><Brand /></a>
    <div className={"pill-links" + (open ? " is-open" : "")} id="primary-nav">{links.map(l => <a key={l.label} className="pill" href={l.href} aria-current={l.current ? "page" : undefined} {...(l.external ? { target: "_blank", rel: "noreferrer" } : { onClick: (e: React.MouseEvent) => { e.preventDefault(); setOpen(false); l.onClick?.(); } })}>{l.label}</a>)}</div>
    <button className="pill pill-menu" aria-label={open ? "Close navigation" : "Open navigation"} aria-controls="primary-nav" aria-expanded={open} onClick={() => setOpen(!open)}><span /><span /></button>
  </nav></header>;
}

function Dock({ view, go }: { view: View; go: Go }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLElement>(null), trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const dismiss = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, []);
  const links = [{ key: "home", label: "Home", icon: "home" }, { key: "dashboard", label: "Dashboard", icon: "dashboard" }, { key: "ledger", label: "Ledger", icon: "ledger" }, { key: "architecture", label: "Architecture", icon: "grid" }, { key: "evidence", label: "Evidence", icon: "check" }];
  return <nav className={"glass-dock" + (open ? " is-expanded" : "")} ref={root} aria-label="Quick navigation" onPointerEnter={e => { if (e.pointerType === "mouse") setOpen(true); }} onPointerLeave={() => { if (!root.current?.contains(document.activeElement)) setOpen(false); }} onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false); }} onKeyDown={e => { if (e.key === "Escape") { setOpen(false); trigger.current?.focus(); } }}><button ref={trigger} className="dock-trigger" aria-label="Expand quick navigation" aria-expanded={open} onClick={() => setOpen(true)}><Icon name={view === "home" ? "ledger" : view} size={28} /></button><div className="dock-items" inert={!open}>{links.map(item => <a key={item.key} href={item.key === "dashboard" || item.key === "ledger" ? "/" + item.key : "/site/#" + (item.key === "home" ? "top" : item.key)} className={view === item.key ? "is-active" : ""} aria-label={item.label} aria-current={view === item.key ? "page" : undefined} onClick={e => { e.preventDefault(); setOpen(false); if (item.key === "dashboard" || item.key === "ledger") go(item.key); else go("home", item.key === "home" ? "top" : item.key); }}><Icon name={item.icon} size={24} /><span>{item.label}</span></a>)}</div></nav>;
}

function EvidenceApp() {
  const [view, setView] = useState<View>(currentView), [evidence, setEvidence] = useState<Evidence | null>(null), [operator, setOperator] = useState(false);
  const anchor = useRef<string | undefined>(undefined), director = useRef<DirectorApi>(null), evidenceRequest = useRef<Promise<void> | null>(null);
  useEffect(() => { const pop = () => setView(currentView()); window.addEventListener("popstate", pop); return () => window.removeEventListener("popstate", pop); }, []);
  const loadEvidence = () => {
    evidenceRequest.current ??= fetch("/site/data/evidence.json").then(r => { if (!r.ok) throw Error(); return r.json(); }).then(setEvidence).catch(() => { evidenceRequest.current = null; });
    return evidenceRequest.current;
  };
  useEffect(() => {
    const abort = new AbortController();
    loadEvidence();
    fetch("/api/site-context", { signal: abort.signal }).then(r => r.ok ? r.json() : null).then(context => setOperator(context?.operator_console === true)).catch(() => {});
    return () => abort.abort();
  }, []);
  useEffect(() => { document.title = "Touchstone — " + (view === "home" ? "Inference that passes the test" : view === "dashboard" ? "Dashboard" : "Ledger"); if (anchor.current) { const id = anchor.current; anchor.current = undefined; requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: prefersReduced() ? "instant" : "smooth" })); } }, [view]);
  function commit(next: View, target?: string) {
    history.pushState(null, "", next === "home" ? "/site/" + (target && target !== "top" ? "#" + target : "") : "/" + next);
    if (next === view && target) document.getElementById(target)?.scrollIntoView({ behavior: prefersReduced() ? "instant" : "smooth" });
    else { anchor.current = target; setView(next); window.scrollTo({ top: 0, behavior: "instant" }); }
    requestAnimationFrame(() => { if (next !== "home") document.querySelector<HTMLElement>("main")?.focus({ preventScroll: true }); });
  }
  const go: Go = (next, target) => {
    if (director.current?.busy()) return;
    if (next !== "home" && view === "home") director.current?.toWorkspace(next, () => commit(next));
    else if (next === "home" && view !== "home") director.current?.toHome(() => commit(next, target));
    else commit(next, target);
  };
  return <>
    <a href="#main-content" className="skip-link">Skip to content</a>
    <BlackHole />
    <PillNav view={view} go={go} />
    <main id="main-content" tabIndex={-1}>{view === "home" ? <Landing go={go} /> : <Workspace view={view} evidence={evidence} go={go} operator={operator} />}</main>
    <footer className="footer section-width" data-reveal={view === "home" ? "below" : undefined}><a href="/site/" onClick={e => { e.preventDefault(); go("home", "top"); }} className="brand" aria-label="Touchstone home"><Brand /></a><p className="mono">SANDBOX BANKING · TESTNET PAYMENTS · LABELLED EVIDENCE.</p><a className="mono footer-github" href={GITHUB_URL} target="_blank" rel="noreferrer">GITHUB <Icon name="arrow" size={12} /></a><a className="mono" href="/control-room">OPERATOR WORKSPACE</a><a className="mono" href="/merchant">SANDBOX MERCHANT</a><span className="mono">© TOUCHSTONE / 2026</span></footer>
    {view !== "home" && <Dock view={view} go={go} />}
    <Director ref={director} view={view} prefetch={loadEvidence} />
  </>;
}

export default function App() {
  return location.pathname.replace(/\/$/, '') === '/control-room' ? <ControlRoom /> : <EvidenceApp />;
}
