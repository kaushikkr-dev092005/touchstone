import { useEffect, useRef, useState } from "react";
import { setTheme, useTheme } from "@/lib/theme";
import { prefersReduced } from "@/hooks/useInView";

/* Pull-cord lamp. Pure SVG + CSS; spring physics in one rAF loop that sleeps at rest. */
const VW = 300, VH = 470, CORD_X = 181, CORD_Y0 = 172, CORD_BASE = 395, CAP = 30;

export default function Lamp() {
  const theme = useTheme();
  const lit = theme === "light";
  const [pull, setPull] = useState(0);
  const [sway, setSway] = useState(0);
  const st = useRef({ p: 0, pv: 0, a: 0, av: 0, drag: false, raf: 0, last: 0 });
  const bulbRef = useRef<SVGEllipseElement>(null);
  const wrap = useRef<HTMLDivElement>(null);

  const loop = (t: number) => {
    const s = st.current;
    let dt = Math.min(0.032, (t - s.last) / 1000 || 0.016); s.last = t;
    const n = Math.ceil(dt / 0.004); dt /= n;
    for (let i = 0; i < n; i++) {
      if (!s.drag) { s.pv += (-300 * s.p - 12 * s.pv) * dt; s.p += s.pv * dt; }
      s.av += (-55 * s.a - 2.6 * s.av) * dt; s.a += s.av * dt;
    }
    setPull(s.p); setSway(s.a);
    const rest = !s.drag && Math.abs(s.p) < 0.05 && Math.abs(s.pv) < 0.5 && Math.abs(s.a) < 0.02 && Math.abs(s.av) < 0.1;
    if (rest) { s.p = s.pv = s.a = s.av = 0; setPull(0); setSway(0); s.raf = 0; } else s.raf = requestAnimationFrame(loop);
  };
  const kick = () => { const s = st.current; if (!s.raf) { s.last = performance.now(); s.raf = requestAnimationFrame(loop); } };
  useEffect(() => () => cancelAnimationFrame(st.current.raf), []);

  const toggle = () => {
    const r = bulbRef.current?.getBoundingClientRect();
    setTheme(lit ? "dark" : "light", r ? r.left + r.width / 2 : innerWidth / 2, r ? r.top + r.height / 2 : 80);
    const s = st.current;
    if (!prefersReduced()) { s.av += lit ? -26 : 26; kick(); }
  };
  const tug = () => { const s = st.current; if (!prefersReduced()) { s.p = 7; s.pv = 90; kick(); } toggle(); };

  const down = useRef<{ y: number; moved: boolean } | null>(null);
  const onDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    down.current = { y: e.clientY, moved: false }; st.current.drag = true; st.current.pv = 0; kick();
  };
  const onMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    const d = down.current; if (!d) return;
    const dy = e.clientY - d.y; if (Math.abs(dy) > 3) d.moved = true;
    const pos = Math.max(0, dy); st.current.p = CAP * (1 - Math.exp(-pos / CAP));
    st.current.av += (e.movementX || 0) * 0.02;
  };
  const onUp = (e: React.PointerEvent<HTMLButtonElement>) => {
    const d = down.current; down.current = null; if (!d) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    const s = st.current; s.drag = false;
    if (!d.moved) return tug();
    if (s.p > 14) toggle();
    kick();
  };
  const onKey = (e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tug(); } };

  const by = CORD_BASE + pull; // bead top
  return (
    <div className="lamp" ref={wrap} style={{ transform: `rotate(${sway}deg)` }}>
      <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" aria-hidden="true" className="lamp-svg" overflow="visible">
        <defs>
          <radialGradient id="dOff" cx=".4" cy=".1" r=".95"><stop offset="0" stopColor="#2f3033" /><stop offset="1" stopColor="#16171a" /></radialGradient>
          <linearGradient id="dOn" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#c4c6c5" /><stop offset=".6" stopColor="#abaead" /><stop offset="1" stopColor="#9fa2a1" /></linearGradient>
          <radialGradient id="inOff" cx=".5" cy=".3" r=".8"><stop offset="0" stopColor="#7d7d7d" /><stop offset="1" stopColor="#5a5a5a" /></radialGradient>
          <radialGradient id="inOn" cx=".5" cy=".35" r=".75"><stop offset="0" stopColor="#fbd9a8" /><stop offset="1" stopColor="#f2a65e" /></radialGradient>
          <radialGradient id="bloom"><stop offset="0" stopColor="#fff" stopOpacity=".95" /><stop offset=".4" stopColor="#ffe6bd" stopOpacity=".6" /><stop offset="1" stopColor="#ffd08f" stopOpacity="0" /></radialGradient>
          <clipPath id="intClip"><ellipse cx="150" cy="170" rx="130" ry="14" /></clipPath>
          <filter id="lampShadow" x="-30%" y="-30%" width="160%" height="170%"><feGaussianBlur stdDeviation="9" /></filter>
        </defs>
        {/* ambient shadow */}
        <ellipse cx="160" cy="190" rx="135" ry="26" fill="#000" opacity=".5" filter="url(#lampShadow)" className="lamp-shadow" />
        {/* suspension cord + cap */}
        <rect x="149.2" y="-400" width="1.6" height="426" className="lamp-cord-top" />
        <rect x="140" y="24" width="20" height="16" rx="2" className="lamp-cap" />
        {/* interior */}
        <ellipse cx="150" cy="170" rx="130" ry="14" fill="url(#inOff)" />
        <ellipse cx="150" cy="170" rx="130" ry="14" fill="url(#inOn)" className="fade" style={{ opacity: lit ? 1 : 0 }} />
        <g clipPath="url(#intClip)">
          {/* bulb */}
          <ellipse ref={bulbRef} cx="150" cy="176" rx="19" ry="23" className="bulb-glass" />
          <path d="M143 172v10M157 172v10M143 182q7 6 14 0" className="filament" />
          <ellipse cx="150" cy="178" rx="52" ry="44" fill="url(#bloom)" className="fade bloom" style={{ opacity: lit ? 1 : 0 }} />
          <ellipse cx="150" cy="177" rx="17" ry="21" fill="#fff" className="fade" style={{ opacity: lit ? .9 : 0 }} />
        </g>
        {/* dome */}
        <path d="M20 170A130 135 0 0 1 280 170A130 14 0 0 0 20 170Z" fill="url(#dOff)" />
        <path d="M20 170A130 135 0 0 1 280 170A130 14 0 0 0 20 170Z" fill="url(#dOn)" className="fade" style={{ opacity: lit ? 1 : 0 }} />
        <path d="M60 80A130 135 0 0 1 150 38" fill="none" stroke="#fff" strokeOpacity=".08" strokeWidth="6" strokeLinecap="round" className="dome-hi" />
        <path d="M20 170A130 14 0 0 0 280 170" fill="none" className="rim" strokeWidth="1.4" />
        {/* pull cord */}
        <rect x={CORD_X - .8} y={CORD_Y0} width="1.6" height={by - CORD_Y0 + 2} className="lamp-cord" />
        <rect x={CORD_X - 3.5} y={CORD_Y0 - 2} width="7" height="6" rx="2" className="lamp-cap" />
      </svg>
      <button
        className="bead" role="switch" aria-checked={lit} aria-label="Toggle light"
        style={{ left: `${(CORD_X / VW) * 100}%`, top: `${(by / VH) * 100}%` }}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onKeyDown={onKey}
        onClick={(e) => e.detail === 0 && undefined}
      >
        <svg viewBox="0 0 10 18" width="10" height="18" aria-hidden="true"><path d="M5 0 6 5C9.5 8 9.5 15 5 18 .5 15 .5 8 4 5Z" className="bead-shape" /></svg>
      </button>
    </div>
  );
}
