import { useCallback, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState, type Ref } from "react";
import gsap from "gsap";
import VaultSequence, { type VaultApi, type VaultVariant } from "./vault/VaultSequence";
import { holeHandle } from "./blackhole/BlackHole";
import { INTRO_STATES, introSchedule, TIMELINE, type IntroState, type VaultPhases } from "./timeline";
import type { View } from "@/siteTypes";

/**
 * IntroController + RouteTransitionProvider.
 * Owns one GSAP master timeline at a time and the persistent vault overlay layer.
 * States (intro): black → safeIn → locked → unlock → doorOpen → keyReveal → keyStow → doorClose → safeOut → holeIgnite → heroIn → done.
 * The current state is mirrored to <html data-intro-state> for debugging and browser checks.
 */
export type DirectorApi = {
  toWorkspace(next: View, commit: () => void): void;
  toHome(commit: () => void): void;
  busy(): boolean;
};

type VaultRequest = { variant: VaultVariant; phases: VaultPhases; caption?: string; key: number };
type Mode = "full" | "returning" | "reduced" | "none";

const html = () => document.documentElement;
const params = () => new URLSearchParams(location.search);
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const wake = () => holeHandle.wake();
const SESSION_KEY = "ts-intro";
// Keep choreography on wall-clock time even when frames are slow (no stalled intros on weak GPUs).
gsap.ticker.lagSmoothing(0);

function heroTargets() {
  const q = (s: string) => Array.from(document.querySelectorAll<HTMLElement>(`[data-reveal="${s}"]`));
  return { nav: q("nav"), badge: q("badge"), lines: q("line"), sub: q("sub"), cta: q("cta"), built: q("built"), below: q("below") };
}

function setState(state: IntroState | string) { html().dataset.introState = state; }

function setHeroInteractive(on: boolean) {
  const hero = document.querySelector<HTMLElement>(".lp-hero");
  if (!hero) return;
  hero.inert = !on;
  if (on) hero.removeAttribute("aria-hidden"); else hero.setAttribute("aria-hidden", "true");
}

function finishIntro() {
  const t = heroTargets();
  gsap.set([...t.nav, ...t.badge, ...t.lines, ...t.sub, ...t.cta, ...t.built, ...t.below], { clearProps: "opacity,transform,filter,visibility" });
  html().dataset.intro = "done";
  html().classList.remove("intro-lock");
  setHeroInteractive(true);
  setState("done");
  try { sessionStorage.setItem(SESSION_KEY, "1"); } catch { /* storage unavailable */ }
}

/** Adds the black hole ignition to a master timeline. */
function addIgnite(m: gsap.core.Timeline, at: number, dur: number, withPoint: boolean) {
  const s = holeHandle.state;
  m.fromTo(s, { intensity: 0 }, { intensity: 1, duration: 0.2, ease: "none", onUpdate: wake, immediateRender: false }, at);
  m.fromTo(s, { ignite: 0 }, { ignite: 1, duration: dur, ease: "sine.inOut", onUpdate: wake, immediateRender: false }, at);
  if (withPoint) m.fromTo(s, { point: 1.15 }, { point: 0, duration: dur * 0.45, ease: "power2.in", onUpdate: wake, immediateRender: false }, at);
  m.fromTo(s, { bloomBoost: 0 }, { bloomBoost: 0.6, duration: dur * 0.45, ease: "power2.out", onUpdate: wake, immediateRender: false }, at + dur * 0.15);
  m.to(s, { bloomBoost: 0, duration: dur * 0.9, ease: "back.inOut(1.6)", onUpdate: wake }, at + dur * 0.6);
}

/** Adds the staggered hero reveal. */
function addHeroIn(m: gsap.core.Timeline, at: number) {
  const t = heroTargets(), st = TIMELINE.stagger;
  const from = { opacity: 0, y: 12, filter: "blur(6px)" }, to = { opacity: 1, y: 0, filter: "blur(0px)", duration: 0.7, ease: "power3.out", immediateRender: false };
  if (t.nav.length) m.fromTo(t.nav, { opacity: 0, y: -20 }, { opacity: 1, y: 0, duration: 0.7, ease: "power3.out", immediateRender: false }, at);
  if (t.badge.length) m.fromTo(t.badge, from, to, at + st);
  if (t.lines.length) m.fromTo(t.lines, { opacity: 0, yPercent: 102, filter: "blur(10px)" }, { opacity: 1, yPercent: 0, filter: "blur(0px)", duration: 0.85, ease: "power3.out", stagger: st, immediateRender: false }, at + st * 2);
  if (t.sub.length) m.fromTo(t.sub, from, to, at + st * 4);
  if (t.cta.length) m.fromTo(t.cta, from, { ...to, stagger: st }, at + st * 5);
  if (t.built.length) m.fromTo(t.built, { opacity: 0 }, { opacity: 1, duration: 0.8, ease: "power1.out", immediateRender: false }, at + st * 7);
  if (t.below.length) m.fromTo(t.below, { opacity: 0 }, { opacity: 1, duration: 0.6, ease: "none", immediateRender: false }, at + st * 7);
}

export default function Director({ view, prefetch, ref }: { view: View; prefetch: () => void; ref: Ref<DirectorApi> }) {
  const [vault, setVault] = useState<VaultRequest | null>(null);
  const [skippable, setSkippable] = useState(false);
  const [skipLabel, setSkipLabel] = useState("Skip intro");
  const [live, setLive] = useState("");
  const [debugState, setDebugState] = useState<{ t: number; d: number; state: string } | null>(null);
  const master = useRef<gsap.core.Timeline | null>(null);
  const pending = useRef<((tl: gsap.core.Timeline, api: VaultApi) => void) | null>(null);
  const cover = useRef<HTMLDivElement>(null);
  const seamLine = useRef<HTMLDivElement>(null);
  const handledView = useRef<View | null>(null);
  const debug = params().get("debug") === "1";
  const skipTimer = useRef(0);

  const startMaster = useCallback((m: gsap.core.Timeline, schedule?: Record<string, number>, skipAfter = 1, label = "Skip intro") => {
    setSkipLabel(label);
    master.current?.kill();
    master.current = m;
    clearTimeout(skipTimer.current);
    setSkippable(false);
    if (skipAfter >= 0) skipTimer.current = window.setTimeout(() => setSkippable(true), skipAfter * 1000);
    const labelFor = (time: number) => {
      if (!schedule) return "";
      let cur = "black";
      for (const s of INTRO_STATES) if (schedule[s] !== undefined && time >= schedule[s]) cur = s;
      return cur;
    };
    m.eventCallback("onUpdate", () => {
      const st = labelFor(m.time());
      if (st && html().dataset.introState !== st) setState(st);
      if (debug) setDebugState({ t: m.time(), d: m.duration(), state: st || "transition" });
    });
    if (debug) setDebugState({ t: 0, d: m.duration(), state: "black" });
  }, [debug]);

  const endMaster = useCallback((m: gsap.core.Timeline) => {
    if (master.current !== m) return;
    master.current = null;
    clearTimeout(skipTimer.current);
    setSkippable(false);
  }, []);

  const skip = useCallback(() => {
    const m = master.current;
    if (!m || m.timeScale() > 1) return;
    gsap.to(m, { timeScale: TIMELINE.skipTimeScale, duration: TIMELINE.skipRamp, ease: "power2.in" });
    setSkippable(false);
  }, []);

  /** Returning visitors and the way back from the ledger: holeIgnite + heroIn only. */
  const playReturning = useCallback(() => {
    const T = TIMELINE.returning;
    html().dataset.intro = "returning";
    setHeroInteractive(false);
    holeHandle.setStartPoint(innerWidth / 2, innerHeight * 0.46);
    const heroAt = T.black + T.holeIgnite - T.heroOverlap;
    const m = gsap.timeline({ onComplete: () => { finishIntro(); endMaster(m); } });
    startMaster(m, { black: 0, holeIgnite: T.black, heroIn: heroAt, done: heroAt + T.heroIn }, -1);
    setState("black");
    addIgnite(m, T.black, T.holeIgnite, false);
    addHeroIn(m, heroAt);
  }, [startMaster, endMaster]);

  /** Reduced motion: 600ms black → one static frame of the hole → hero crossfade. */
  const playReduced = useCallback(() => {
    const s = holeHandle.state;
    Object.assign(s, { ignite: 1, intensity: 0, point: 0, bloomBoost: 0 });
    const t = heroTargets(), d = TIMELINE.reduced.crossfade;
    const all = [...t.nav, ...t.badge, ...t.lines, ...t.sub, ...t.cta, ...t.built, ...t.below];
    const m = gsap.timeline({ onComplete: () => { finishIntro(); endMaster(m); } });
    startMaster(m, undefined, -1);
    m.to(s, { intensity: 1, duration: d, ease: "none", onUpdate: () => holeHandle.renderOnce() }, 0);
    m.fromTo(all, { opacity: 0 }, { opacity: 1, duration: d, ease: "none", immediateRender: false }, 0);
  }, [startMaster, endMaster]);

  /** Full intro: mount the vault; the master timeline is assembled once its timeline exists. */
  const playFull = useCallback(() => {
    html().classList.add("intro-lock");
    setHeroInteractive(false);
    setState("black");
    pending.current = (vaultTl, api) => {
      const T = TIMELINE.intro, sched = introSchedule();
      const m = gsap.timeline({ paused: debug, onComplete: () => { finishIntro(); if (!debug) setVault(null); endMaster(m); } });
      startMaster(m, sched, 1);
      vaultTl.paused(false);
      m.add(vaultTl, T.black);
      m.call(() => { const p = api.pointPosition(); holeHandle.setStartPoint(p.x, p.y); }, [], sched.holeIgnite - 0.02);
      addIgnite(m, sched.holeIgnite, T.holeIgnite, true);
      m.to(api.pointEl.parentElement!, { opacity: 0, duration: 0.35, ease: "power1.in" }, sched.holeIgnite + 0.05);
      if (!debug) m.call(() => setVault(null), [], sched.holeIgnite + 0.6);
      addHeroIn(m, sched.heroIn);
    };
    setVault({ variant: "intro", phases: TIMELINE.intro.vault, key: Date.now() });
  }, [debug, startMaster, endMaster]);

  const revealLedger = () => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(".workspace-heading, .workspace-tabs, .workspace-metrics, .workspace-panels > *, .policy-comparison, .ledger-panel .panel-top, .ledger-toolbar, .record-table tbody tr")).slice(0, 48);
    if (els.length) gsap.fromTo(els, { opacity: 0, y: 14 }, { opacity: 1, y: 0, duration: TIMELINE.dashboard.ledgerIn * 0.6, stagger: TIMELINE.dashboard.ledgerIn * 0.4 / els.length, ease: "power3.out", clearProps: "opacity,transform" });
  };

  useImperativeHandle(ref, () => ({
    busy: () => master.current !== null && master.current.isActive(),
    toWorkspace(next, commit) {
      if (master.current?.isActive() && vault) return;
      prefetch();
      setLive("Opening the " + next + ".");
      const nav = heroTargets().nav;
      if (reducedMotion()) {
        const c = cover.current!;
        gsap.timeline({ onComplete: () => setLive("The " + next + " is open.") })
          .to(c, { opacity: 1, duration: 0.25, ease: "none" })
          .call(() => { commit(); Object.assign(holeHandle.state, { intensity: 0 }); holeHandle.wake(); })
          .to(c, { opacity: 0, duration: 0.3, ease: "none", delay: 0.05 });
        return;
      }
      pending.current = (vaultTl, api) => {
        const D = TIMELINE.dashboard, t = heroTargets();
        const fadeOut = [...t.badge, ...t.lines, ...t.sub, ...t.cta, ...t.built, ...t.below, ...nav, ...document.querySelectorAll<HTMLElement>(".workspace, .footer")];
        const m = gsap.timeline({ onComplete: () => { setVault(null); setLive("The " + next + " is open."); setState("done"); endMaster(m); } });
        startMaster(m, undefined, 1, "Skip");
        setState("dashboard");
        m.to(fadeOut, { opacity: 0, y: -6, duration: D.heroOut, ease: "power2.in" }, 0);
        m.to(holeHandle.state, { intensity: 0, duration: D.heroOut, ease: "power1.in", onUpdate: wake }, 0);
        m.to(cover.current!, { opacity: 1, duration: D.heroOut, ease: "none" }, 0);
        vaultTl.paused(false);
        m.add(vaultTl, D.heroOut);
        // Commit the route while the screen is fully covered.
        m.call(() => { commit(); gsap.set(nav, { opacity: 0 }); }, [], D.heroOut + vaultTl.labels.keyStow);
        const end = D.heroOut + vaultTl.duration();
        const line = seamLine.current!;
        m.call(() => {
          const p = api.pointPosition();
          gsap.set(line, { x: p.x, y: p.y, xPercent: -50, scaleX: 0.004, opacity: 1 });
        }, [], end - 0.2);
        m.to(line, { y: 0, duration: D.seamExpand * 0.45, ease: "power3.in" }, end - 0.18);
        m.to(api.pointEl.parentElement!, { opacity: 0, duration: 0.15 }, end - 0.18);
        m.to(line, { x: innerWidth / 2, scaleX: 1, duration: D.seamExpand * 0.55, ease: "power3.out" }, end - 0.18 + D.seamExpand * 0.45);
        m.to(cover.current!, { opacity: 0, duration: 0.6, ease: "power1.out" }, end + 0.1);
        m.call(revealLedger, [], end + 0.12);
        m.fromTo(nav, { opacity: 0, y: -10 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out", immediateRender: false }, end + 0.25);
        m.to(line, { opacity: 0, duration: 0.7, ease: "power1.in" }, end + 0.35);
        m.set([...nav, ...document.querySelectorAll<HTMLElement>(".workspace, .footer")], { clearProps: "opacity,transform" }, end + D.ledgerIn);
      };
      setVault({ variant: "dashboard", phases: TIMELINE.dashboard.vault, caption: "AUTHORIZING LEDGER ACCESS", key: Date.now() });
    },
    toHome(commit) {
      master.current?.kill(); master.current = null;
      html().dataset.intro = reducedMotion() ? "reduced" : "returning";
      commit();
    },
  }));

  const onVaultTimeline = useCallback((tl: gsap.core.Timeline, api: VaultApi) => { pending.current?.(tl, api); }, []);

  // React to the current view: first load, history navigation and returns home.
  useLayoutEffect(() => {
    if (handledView.current === view && view !== "home") return;
    const first = handledView.current === null;
    const prev = handledView.current;
    handledView.current = view;
    if (view !== "home") {
      if (!vault) { gsap.killTweensOf(holeHandle.state); Object.assign(holeHandle.state, { intensity: 0 }); holeHandle.wake(); }
      delete html().dataset.intro;
      return;
    }
    if (!first && prev === "home") return;
    let mode = (html().dataset.intro as Mode | undefined) ?? "returning";
    if (first && params().get("intro") === "force") mode = reducedMotion() ? "reduced" : "full";
    if (reducedMotion()) mode = "reduced";
    if (mode === "full") playFull();
    else if (mode === "reduced") playReduced();
    else playReturning();
  }, [view]);

  // Scroll parallax/dimming of the hole on the landing page.
  useEffect(() => {
    if (view !== "home") return;
    const onScroll = () => holeHandle.setScroll(scrollY / innerHeight);
    onScroll();
    addEventListener("scroll", onScroll, { passive: true });
    return () => { removeEventListener("scroll", onScroll); holeHandle.setScroll(0); };
  }, [view]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && master.current) skip(); };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [skip]);

  // Unmount (also React StrictMode's simulated unmount): stop everything and allow a clean replay.
  useEffect(() => () => { master.current?.kill(); master.current = null; clearTimeout(skipTimer.current); handledView.current = null; }, []);

  return <>
    <div ref={cover} className="cine-cover" aria-hidden="true" />
    {vault && <div className="cine-vault-layer"><VaultSequence key={vault.key} variant={vault.variant} phases={vault.phases} caption={vault.caption} onTimeline={onVaultTimeline} /></div>}
    <div ref={seamLine} className="cine-seam-line" aria-hidden="true" />
    {skippable && <button className="cine-skip" onClick={skip}>{skipLabel} <kbd aria-hidden="true">Esc</kbd></button>}
    <p className="sr-only" aria-live="polite">{live}</p>
    {debug && debugState && <div className="cine-debug" role="group" aria-label="Timeline debugger">
      <span className="mono">{debugState.state} · {debugState.t.toFixed(2)}s / {debugState.d.toFixed(2)}s · q{holeHandle.level()} · {holeHandle.frameMs().toFixed(1)}ms</span>
      <input type="range" min={0} max={1000} value={Math.round((debugState.t / Math.max(debugState.d, 0.001)) * 1000)} aria-label="Scrub timeline"
        onChange={e => { const m = master.current; if (!m) return; m.pause(); m.progress(+e.target.value / 1000); }} />
      <button onClick={() => { const m = master.current; if (m) m.paused(!m.paused()); }}>Play / pause</button>
    </div>}
  </>;
}
