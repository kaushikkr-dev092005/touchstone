import { useEffect, useMemo, useRef, useState } from "react";
import { scene } from "@/data/cards-scene";
import { prefersReduced, useInView } from "@/hooks/useInView";
import GlassSurface from "./Glass";

const fmt = (n: number, d = 2) => n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const RANGES = ["1H", "1D", "1W", "1M", "1Y", "ALL"] as const;
const XLAB: Record<string, string[]> = {
  "1H": ["0:00", "0:10", "0:20", "0:30", "0:40", "0:50", "1:00"], "1D": ["0:00", "3:00", "6:00", "9:00", "12:00", "14:00", "18:00"],
  "1W": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "1M": ["W1", "W1.5", "W2", "W2.5", "W3", "W3.5", "W4"],
  "1Y": ["Jan", "Mar", "May", "Jul", "Sep", "Nov", "Dec"], ALL: ["2021", "2022", "2023", "2024", "2025", "2026", "now"],
};
function series(seed: number, n = 56) {
  let s = seed; const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  let a = 1.9, b = 1.6; const ratio: number[] = [], mult: number[] = [];
  for (let i = 0; i < n; i++) { a += (rnd() - 0.5) * 0.55 + (1.7 - a) * 0.12; b += (rnd() - 0.5) * 0.5 + (1.3 - b) * 0.15; ratio.push(Math.min(3.7, Math.max(0.3, a))); mult.push(Math.min(3.7, Math.max(0.3, b))); }
  return { ratio, mult };
}

function Chart() {
  const [range, setRange] = useState<(typeof RANGES)[number]>("1D");
  const [hover, setHover] = useState<number | null>(null);
  const data = useMemo(() => series(RANGES.indexOf(range) * 977 + 31), [range]);
  const W = 330, H = 100, N = data.ratio.length;
  const X = (i: number) => (i / (N - 1)) * W, Y = (v: number) => H - (v / 4) * H;
  const d = (a: number[]) => a.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join("");
  return (
    <div className="cs-chart">
      <div className="cs-row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <b className="cs-h2">{scene.chart.title}</b>
        <span><b className="cs-big">{scene.chart.value}</b> <small className="cs-green">↗ {scene.chart.delta}</small></span>
      </div>
      <div className="cs-plot">
        <div className="cs-yax">{[4, 3, 2, 1, 0].map((v) => <span key={v}>{v}</span>)}</div>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" onPointerMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); setHover(Math.round(((e.clientX - r.left) / r.width) * (N - 1))); }} onPointerLeave={() => setHover(null)}>
          {[0, 1, 2, 3, 4].map((v) => <line key={v} x1="0" x2={W} y1={Y(v)} y2={Y(v)} stroke="#d9d9d6" strokeWidth=".6" vectorEffect="non-scaling-stroke" />)}
          <path key={range + "g"} d={d(data.ratio)} fill="none" stroke="#58b86a" strokeWidth="1.3" vectorEffect="non-scaling-stroke" pathLength={1} className="cs-draw" />
          <path key={range + "b"} d={d(data.mult)} fill="none" stroke="#111" strokeWidth="1.3" vectorEffect="non-scaling-stroke" pathLength={1} className="cs-draw" />
          {hover !== null && <line x1={X(hover)} x2={X(hover)} y1="0" y2={H} stroke="#111" strokeWidth=".8" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />}
        </svg>
        {hover !== null && <div className="cs-tip" style={{ left: `${(hover / (N - 1)) * 100}%` }}><span>C-RATIO <b>{(data.ratio[hover] * 50 + 20).toFixed(1)}%</b></span><span>MULTIPLIER <b>{data.mult[hover].toFixed(2)}</b></span></div>}
      </div>
      <div className="cs-xax">{XLAB[range].map((l) => <span key={l}>{l}</span>)}</div>
      <div className="cs-row cs-foot">
        <span className="cs-legend"><i style={{ background: "#111" }} /> MULTIPLIER <i style={{ background: "#58b86a" }} /> C-RATIO</span>
        <span className="cs-pills" role="tablist" aria-label="Range">{RANGES.map((r) => <button key={r} role="tab" aria-selected={r === range} className={r === range ? "on" : ""} onClick={() => setRange(r)}>{r}</button>)}</span>
      </div>
    </div>
  );
}

type Card = { id: string; x: number; y: number; w: number; h: number; layer: 0 | 1 | 2; z: number; phase: number; dur: number; node: React.ReactNode; cls: string };

export default function CardsScene() {
  const b = scene.borrow;
  const [pct, setPct] = useState(75);
  const [amount, setAmount] = useState(String(b.initial));
  const [editing, setEditing] = useState(false);
  const [iso, setIso] = useState(false);
  const setFromPct = (p: number) => { setPct(p); setAmount(String(Math.round((p / 100) * b.maxBorrow))); };
  const onAmount = (v: string) => { const n = Number(v.replace(/[^\d.]/g, "")) || 0; setAmount(v.replace(/[^\d.]/g, "")); setPct(Math.max(0, Math.min(100, Math.round((n / b.maxBorrow) * 100)))); };
  const amt = Number(amount) || 0;
  const ltv = (pct / 75) * b.ltvAt75, liq = (pct / 75) * scene.cash.liquidationAt75;
  const collateralPct = Math.min(100, (liq / 45600) * 100);

  const [wrapRef, inView] = useInView<HTMLDivElement>("-10% 0px", false);
  const [seen, setSeen] = useState(false);
  useEffect(() => { if (inView) setSeen(true); }, [inView]);
  const stage = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [scroll, setScroll] = useState(0);
  useEffect(() => {
    const el = wrapRef.current!; const ro = new ResizeObserver(() => setScale(el.clientWidth < 700 ? 0.56 : Math.min(1, el.clientWidth / 1280))); ro.observe(el); return () => ro.disconnect();
  }, [wrapRef]);

  /* pointer parallax (eased), idle bob and scroll drift in one rAF loop, paused off-screen */
  const target = useRef({ x: 0, y: 0 }), cur = useRef({ x: 0, y: 0 });
  useEffect(() => {
    if (!inView || prefersReduced()) return;
    const coarse = matchMedia("(pointer: coarse)").matches;
    const mv = (e: PointerEvent) => { const r = wrapRef.current!.getBoundingClientRect(); target.current = { x: ((e.clientX - r.left) / r.width - 0.5) * 2, y: ((e.clientY - r.top) / r.height - 0.5) * 2 }; };
    const sc = () => { const r = wrapRef.current!.getBoundingClientRect(); setScroll((r.top + r.height / 2 - innerHeight / 2) / innerHeight); };
    if (!coarse) addEventListener("pointermove", mv);
    addEventListener("scroll", sc, { passive: true }); sc();
    let raf = 0; const t0 = performance.now();
    const loop = (t: number) => {
      const s = (t - t0) / 1000;
      if (coarse) target.current = { x: Math.sin(s * 0.25), y: Math.cos(s * 0.19) * 0.6 };
      cur.current.x += (target.current.x - cur.current.x) * 0.06; cur.current.y += (target.current.y - cur.current.y) * 0.06;
      const root = stage.current; if (root) {
        root.style.setProperty("--px", cur.current.x.toFixed(3)); root.style.setProperty("--py", cur.current.y.toFixed(3)); root.style.setProperty("--t", s.toFixed(2));
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { removeEventListener("pointermove", mv); removeEventListener("scroll", sc); cancelAnimationFrame(raf); };
  }, [inView, wrapRef]);

  const cards: Card[] = [
    { id: "cash", x: 90, y: 26, w: 266, h: 147, layer: 2, z: 0, phase: 0, dur: 7, cls: "green", node: <>
      <div className="cs-row" style={{ gap: 10 }}><LogoC /><div><div className="mono cs-bal">${fmt(scene.cash.balance)}</div><div className="mono cs-sub">{scene.cash.label}</div></div></div>
      <div className="cs-row mono cs-sm" style={{ justifyContent: "space-between", marginTop: 14 }}><span>Collateral</span><span>${fmt(scene.cash.collateral)}</span></div>
      <div className="cs-bar"><i style={{ width: `${collateralPct}%` }} /></div>
      <div className="mono cs-sm" style={{ marginTop: 8 }}>liquidation: ${fmt(liq)}</div></> },
    { id: "borrow", x: 506, y: 143, w: 271, h: 376, layer: 1, z: 1, phase: 1.3, dur: 8, cls: "white", node: <>
      <b className="cs-h2" style={{ fontSize: 15 }}>{b.title}</b>
      <label className="cs-input"><input aria-label="Borrow amount" inputMode="decimal" className="mono" value={editing ? amount : fmt(amt, 0)} onFocus={() => setEditing(true)} onBlur={() => setEditing(false)} onChange={(e) => onAmount(e.target.value)} /><span className="mono cs-sm">MAX</span></label>
      <div className="cs-slider"><span className="mono cs-pct" style={{ left: `${pct}%` }}>{pct}%</span>
        <input type="range" min={0} max={100} value={pct} aria-label="Borrow percentage" onChange={(e) => setFromPct(Number(e.target.value))} style={{ ["--v" as string]: `${pct}%` }} />
        <div className="cs-row cs-sm" style={{ justifyContent: "space-between" }}><span>Safer</span><span>Risky</span></div></div>
      <Rows rows={[["Available for Borrowing", b.available], ["Est Interest Rate", b.rate], ["AURA Rewards", b.rewards]]} />
      <Rows rows={[["LTV", ltv.toFixed(1) + "%"], ["Max LTV", b.maxLtv.toFixed(1) + "%"]]} gap />
      <Rows rows={[["Liquidation Threshold", b.liqThreshold.toFixed(1) + "%"]]} gap />
      <button className="cs-borrow" onClick={() => {}}>Borrow</button></> },
    { id: "cash2", x: 996, y: 116, w: 195, h: 128, layer: 0, z: 2, phase: 2.1, dur: 6.5, cls: "dark", node: <ApyCard c={scene.apyCards[0]} /> },
    { id: "chart", x: 746, y: 236, w: 364, h: 205, layer: 2, z: 3, phase: 3, dur: 9, cls: "white", node: <Chart /> },
    { id: "synth", x: 160, y: 489, w: 337, h: 113, layer: 2, z: 0, phase: 4.4, dur: 7.5, cls: "white", node: <>
      <div className="cs-tiny">{scene.synth.title}</div>
      <div className="cs-row" style={{ gap: 8, margin: "4px 0 10px" }}><LogoC dark /><b style={{ fontSize: 26, letterSpacing: "-.02em" }}>CASH</b></div>
      <div className="cs-row mono cs-stats">
        <span><small>Current Price</small><b>{scene.synth.price}</b></span><span><small>Target C-Ratio</small><b>{scene.synth.cRatio}</b></span>
        <span><small>Market Cap</small><b>{scene.synth.cap} <em>CASH</em></b></span><span><small>Multiplier</small><b>{scene.synth.multiplier} <u>↘ {scene.synth.change}</u></b></span></div></> },
    { id: "gscia", x: 188, y: 622, w: 196, h: 128, layer: 0, z: 0, phase: 5.2, dur: 8.5, cls: "dark", node: <ApyCard c={scene.apyCards[1]} /> },
    { id: "cpia", x: 847, y: 553, w: 195, h: 128, layer: 0, z: 3, phase: 0.7, dur: 7, cls: "dark", node: <ApyCard c={scene.apyCards[2]} /> },
  ];
  const depth = [6, 10, 14]; // px parallax per layer (back..front), max about 14

  return (
    <div className="cs-wrap" ref={wrapRef}>
      <button className="cs-iso" aria-pressed={iso} onClick={() => setIso(!iso)}>{iso ? "Flat view" : "Isometric view"}</button>
      <div className="cs-viewport" style={{ height: 800 * scale, perspective: iso ? 2200 : undefined }}>
        <div ref={stage} className={`cs-stage${iso ? " iso" : ""}`} style={{ transform: `${scale < 0.6 ? "translateX(calc(-50% + 50vw)) " : ""}scale(${scale})` }}>
          <div className="cs-plane" style={iso ? { transform: "translate(60px,-30px) rotateX(58deg) rotateZ(-38deg) scale(.8)" } : undefined}>
            <svg className="cs-logo" width="36" height="52" viewBox="0 0 36 52" aria-label="Touchstone mark"><circle cx="26" cy="26" r="24" fill="#fff" />{[6, 12, 18].map((x) => <rect key={x} x={x - 6} y="0" width="3" height="52" fill="#000" />)}</svg>
            <div className="cs-circles">{["+", "?", "↗"].map((c) => <GlassSurface key={c} radius={99} className="cs-circ"><button aria-label={{ "+": "Add", "?": "Help", "↗": "Open" }[c]}>{c}</button></GlassSurface>)}</div>
            {cards.map((c, i) => (
              <div key={c.id} className={`cs-card ${c.cls}${seen ? " in" : ""}`} data-card={c.id}
                style={{
                  left: c.x, top: c.y, width: c.w, minHeight: c.h, zIndex: c.z, transitionDelay: `${(c.layer * 60) + i * 60}ms`,
                  transform: iso ? `translateZ(${c.layer * 70 + c.z * 12}px)` : `translate3d(calc(var(--px,0)*${-depth[c.layer]}px),calc(var(--py,0)*${-depth[c.layer]}px + ${scroll * -depth[c.layer] * 3}px + sin(calc(var(--t,0)*${(6.283 / c.dur).toFixed(3)} + ${c.phase}))*${3 + (i % 4)}px),0)`,
                  ["--zl" as string]: c.layer,
                }}>
                <div className="cs-inner">{c.node}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Rows({ rows, gap }: { rows: string[][]; gap?: boolean }) {
  return <div className="cs-rows" style={{ marginTop: gap ? 18 : 14 }}>{rows.map(([k, v]) => <div key={k} className="cs-row mono cs-sm" style={{ justifyContent: "space-between" }}><span>{k}</span><span>{v}</span></div>)}</div>;
}
function ApyCard({ c }: { c: { name: string; apy: string; value: string } }) {
  return <><div className="cs-row" style={{ gap: 10, marginBottom: 14 }}><LogoC light /><b className="cs-sub2">{c.name}</b></div>
    <div className="cs-row mono cs-sm" style={{ justifyContent: "space-between" }}><span>APY</span><span>{c.apy}</span></div>
    <div className="cs-row mono cs-sm" style={{ justifyContent: "space-between", marginTop: 8 }}><span>Total Value</span><span>{c.value}</span></div></>;
}
function LogoC({ dark, light }: { dark?: boolean; light?: boolean }) {
  const col = dark ? "#58b86a" : light ? "#e8e8e8" : "#fff";
  return <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="11.5" fill="none" stroke={col} strokeWidth="2.2" strokeDasharray="60 8" /><path d="M16.5 9.5A5 5 0 1 0 16.5 16.5" fill="none" stroke={col} strokeWidth="2" strokeLinecap="round" /></svg>;
}
