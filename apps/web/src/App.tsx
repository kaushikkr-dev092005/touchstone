import { useEffect, useRef, useState } from "react";
import Vault from "@/components/Vault";
import Landing from "@/components/Landing";
import Workspace from "@/components/Workspace";
import { Brand, Icon } from "@/components/Identity";
import { prefersReduced } from "@/hooks/useInView";
import type { Evidence, Go, View } from "@/siteTypes";

const currentView = (): View => /\/(dashboard|ledger)\/?$/.test(location.pathname) ? location.pathname.includes("ledger") ? "ledger" : "dashboard" : "home";

function Header({ view, go }: { view: View; go: Go }) {
  const [mobile, setMobile] = useState(false);
  useEffect(() => setMobile(false), [view]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") setMobile(false); };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, []);
  return <header className="site-header"><div className="status-strip"><span><i className="status-dot" /> BOUNDED SPENDING. VERIFIABLE WORK.</span><span>SANDBOX / TESTNET / SIMULATION <b>·</b> TS—01</span></div><div className="header-inner"><a href="/site/" className="brand" onClick={e => { e.preventDefault(); go("home"); }}><Brand /></a><nav className={"primary-nav" + (mobile ? " is-open" : "")} id="primary-nav" aria-label="Main navigation">{["Platform", "Controls", "Dashboard", "Ledger", "Evidence"].map((label, i) => { const target: View = i === 2 ? "dashboard" : i === 3 ? "ledger" : "home"; const anchor = ["architecture", "control-layer", undefined, undefined, "evidence"][i]; return <a key={label} href={target === "home" ? "/site/#" + anchor : "/" + target} aria-current={view === target && target !== "home" ? "page" : undefined} onClick={e => { e.preventDefault(); setMobile(false); go(target, anchor); }}>{label}</a>; })}</nav><div className="header-actions"><a className="header-context" href="/merchant">Sandbox merchant <Icon name="arrow" size={13} /></a><button className="button button-light header-cta" onClick={() => go("dashboard")}>Open workspace <Icon name="arrow" size={15} /></button><button className="menu-toggle" aria-label={mobile ? "Close navigation" : "Open navigation"} aria-controls="primary-nav" aria-expanded={mobile} onClick={() => setMobile(!mobile)}><span /><span /></button></div></div></header>;
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

function VaultPortal({ destination, complete, cancel }: { destination: View; complete: () => void; cancel: () => void }) {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null), finish = useRef(complete);
  finish.current = complete;
  useEffect(() => {
    dialog.current?.showModal();
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => setOpen(true)); });
    const timer = setTimeout(() => finish.current(), 1900);
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); clearTimeout(timer); dialog.current?.close(); };
  }, []);
  return <dialog ref={dialog} className="vault-portal" onCancel={e => { e.preventDefault(); cancel(); }} aria-label={"Opening " + destination}><button className="portal-cancel" aria-label="Cancel vault transition" onClick={cancel}><Icon name="close" /></button><p className="eyebrow"><i className="status-dot" /> TOUCHSTONE / WORKSPACE ACCESS</p><div className="portal-vault"><Vault open={open} /></div><div className="portal-caption"><span className="mono">UNLOCKING THE {destination.toUpperCase()}</span><div className="portal-progress"><i /></div><p role="status">Your workspace is opening.</p></div></dialog>;
}

export default function App() {
  const [view, setView] = useState<View>(currentView), [portal, setPortal] = useState<View | null>(null), [evidence, setEvidence] = useState<Evidence | null>(null), [operator, setOperator] = useState(false);
  const anchor = useRef<string | undefined>(undefined);
  useEffect(() => { const pop = () => { setPortal(null); setView(currentView()); }; window.addEventListener("popstate", pop); return () => window.removeEventListener("popstate", pop); }, []);
  useEffect(() => {
    const abort = new AbortController();
    fetch("/site/data/evidence.json", { signal: abort.signal }).then(r => { if (!r.ok) throw Error(); return r.json(); }).then(setEvidence).catch(() => {});
    fetch("/api/site-context", { signal: abort.signal }).then(r => r.ok ? r.json() : null).then(context => setOperator(context?.operator_console === true)).catch(() => {});
    return () => abort.abort();
  }, []);
  useEffect(() => { document.title = "Touchstone — " + (view === "home" ? "Agent spending. Human control." : view === "dashboard" ? "Dashboard" : "Ledger"); if (anchor.current) { const id = anchor.current; anchor.current = undefined; requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: prefersReduced() ? "instant" : "smooth" })); } }, [view]);
  function commit(next: View, target?: string) {
    history.pushState(null, "", next === "home" ? "/site/" + (target && target !== "top" ? "#" + target : "") : "/" + next); setPortal(null);
    if (next === view && target) document.getElementById(target)?.scrollIntoView({ behavior: prefersReduced() ? "instant" : "smooth" });
    else { anchor.current = target; setView(next); window.scrollTo({ top: 0, behavior: "instant" }); }
    requestAnimationFrame(() => { if (next !== "home") document.querySelector<HTMLElement>("main")?.focus({ preventScroll: true }); });
  }
  const go: Go = (next, target) => { if (next !== "home" && next !== view && !prefersReduced()) setPortal(next); else commit(next, target); };
  return <><a href="#main-content" className="skip-link">Skip to content</a><Header view={view} go={go} /><main id="main-content" tabIndex={-1}>{view === "home" ? <Landing go={go} hideVault={portal !== null} /> : <Workspace view={view} evidence={evidence} go={go} operator={operator} />}</main><footer className="footer section-width"><a href="/site/" onClick={e => { e.preventDefault(); go("home"); }} className="brand"><Brand /></a><p className="mono">AUTONOMY, WITH ACCOUNTABILITY.<br />SANDBOX · TESTNET · LABELLED EVIDENCE.</p><span className="mono">© TOUCHSTONE / 2026</span></footer><Dock view={view} go={go} />{portal && <VaultPortal destination={portal} complete={() => commit(portal)} cancel={() => setPortal(null)} />}</>;
}
