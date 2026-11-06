import { useEffect, useRef, useState } from "react";
import { prefersReduced } from "@/hooks/useInView";

/* Isometric vault. Everything is generated from one projection so the geometry stays exact.
   x runs lower-right, y runs lower-left, z up. Right face = plane x=10 (door), left face = plane y=9.5. */
const S = 22, OX = 262, OY = 192, K = 0.8660254;
type V3 = [number, number, number];
const P = (x: number, y: number, z: number): [number, number] => [OX + (x - y) * K * S, OY + (x + y) * 0.5 * S - z * S];
const f2 = (n: number) => n.toFixed(2);
const pts = (a: V3[]) => a.map((p) => P(...p).map(f2).join(",")).join(" ");
const path = (a: V3[]) => "M" + a.map((p) => P(...p).map(f2).join(" ")).join("L") + "Z";
const circX = (xf: number, yc: number, zc: number, r: number, n = 72): V3[] =>
  Array.from({ length: n }, (_, i) => { const a = (i / n) * Math.PI * 2; return [xf, yc + r * Math.cos(a), zc + r * Math.sin(a)] as V3; });
const circZ = (xc: number, yc: number, z: number, r: number, n = 40): V3[] =>
  Array.from({ length: n }, (_, i) => { const a = (i / n) * Math.PI * 2; return [xc + r * Math.cos(a), yc + r * Math.sin(a), z] as V3; });
function hull(points: [number, number][]) {
  const p = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cr = (o: number[], a: number[], b: number[]) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo: [number, number][] = [], up: [number, number][] = [];
  for (const q of p) { while (lo.length > 1 && cr(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
  for (const q of [...p].reverse()) { while (up.length > 1 && cr(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
  return [...lo.slice(0, -1), ...up.slice(0, -1)];
}
const hullPath = (a: V3[], b: V3[]) => "M" + hull([...a, ...b].map((p) => P(...p))).map((q) => q.map((n) => n.toFixed(1)).join(" ")).join("L") + "Z";
const box = (x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) => ({
  top: path([[x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]),
  left: path([[x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1]]),
  right: path([[x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]]),
});
const seg = (p: number, a: number, b: number) => Math.min(1, Math.max(0, (p - a) / (b - a)));
const io = (t: number) => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

const C = { stroke: "#5d6166", top: "#f8f8f5", left: "#f0f0ec", right: "#e3e3df", plate: "#fbfbf9", plateL: "#eeeeea", plateR: "#e2e2de" };
const ln = { stroke: C.stroke, strokeWidth: 1, vectorEffect: "non-scaling-stroke" as const, strokeLinejoin: "round" as const };
const hair = { stroke: "#9a9da2", strokeWidth: 0.7, vectorEffect: "non-scaling-stroke" as const };

const hairN = { ...hair, fill: "none" };

const DUR = 1600;
const BX = { x0: 2, x1: 10, y0: 2.5, y1: 9.5, z0: 0.8, z1: 9.8 };
const OC = { y: 6, z: 6 };

export default function Vault({ open, onOpenChange }: { open: boolean; onOpenChange?: (o: boolean) => void }) {
  const [p, setP] = useState(open ? 1 : 0);
  const cur = useRef(p), raf = useRef(0), last = useRef(0);
  useEffect(() => {
    const target = open ? 1 : 0;
    if (prefersReduced()) { cur.current = target; setP(target); return; }
    cancelAnimationFrame(raf.current); last.current = performance.now();
    const tick = (t: number) => {
      const d = (t - last.current) / DUR; last.current = t;
      cur.current += Math.sign(target - cur.current) * d;
      if ((target - cur.current) * (target ? 1 : -1) <= 0) { cur.current = target; setP(target); return; }
      setP(cur.current); raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [open]);

  const rot = 90 * io(seg(p, 0.15, 0.4));
  const swing = io(seg(p, 0.4, 0.52));
  const slide = io(seg(p, 0.5, 1));
  const yd = lerp(6, -1.5, slide), xd = 10.4 + 0.9 * swing;
  const blinkOff = p > 0 && p < 0.15 ? Math.floor((p / 0.15) * 6) % 2 === 1 : false;
  const indicator = p === 0 ? "#e5322d" : p < 0.15 ? (blinkOff ? "#2b2b2b" : "#e5322d") : "#161616";
  const flash = Math.sin(Math.PI * seg(p, 0.05, 0.2));

  const pl = (r: number, a: number, xf: number): V3 => [xf, yd + r * Math.cos(a), OC.z + r * Math.sin(a)];
  const xf = xd + 0.6;
  const spokes = [0, 1, 2].map((i) => Math.PI / 2 + (i * 2 * Math.PI) / 3 + (rot * Math.PI) / 180);
  const dialRot = (-rot * Math.PI) / 180;
  const ticks = Array.from({ length: 28 }, (_, i) => dialRot + (i / 28) * Math.PI * 2);

  const B = box(0, 16, -5, 12, 0, 0.8);
  const bx = box(BX.x0, BX.x1, BX.y0, BX.y1, BX.z0, BX.z1);
  const rail = box(10.7, 11.3, -4.2, 10.4, 0.8, 1.05);
  const strip = box(11.7, 12.0, -4.2, 10.4, 0.8, 0.9);
  const stop = box(10.6, 11.4, 10.4, 11, 0.8, 1.9);
  const reader = box(8.6, 9.6, 9.5, 9.75, 2.6, 5.9);
  const drawers = Array.from({ length: 16 }, (_, i) => ({ c: i % 4, r: Math.floor(i / 4) }));
  const toggle = () => onOpenChange?.(!open);
  const [cx, cy] = P(xf, yd, OC.z);
  const car = box(10.4, 11.6, yd - 1.1, yd + 1.1, 1.0, 1.7);
  const [sx, sy1] = P(11.0, yd, 1.7);
  const [, sy2] = P(11.0, yd, 2.7);
  const back = circX(xd, yd, OC.z, 3.35), front = circX(xf, yd, OC.z, 3.35);

  return (
    <svg viewBox="0 0 700 600" className="vault-svg" role="group" aria-label={`Isometric vault, ${open ? "open" : "closed"}`}>
      <defs>
        <filter id="vShadow" x="-20%" y="-20%" width="140%" height="160%"><feGaussianBlur stdDeviation="16" /></filter>
        <clipPath id="vOpening"><polygon points={pts(circX(10, OC.y, OC.z, 2.6))} /></clipPath>
      </defs>
      <polygon points={pts([[0.5, -4.5, -1.2], [16.5, -4.5, -1.2], [16.5, 12.5, -1.2], [0.5, 12.5, -1.2]])} fill="#26324a" opacity=".16" filter="url(#vShadow)" />
      {/* base plate */}
      <path d={B.left} fill={C.plateL} {...ln} /><path d={B.right} fill={C.plateR} {...ln} /><path d={B.top} fill={C.plate} {...ln} />
      <path d={path([[0.7, -4.3, 0.8], [15.3, -4.3, 0.8], [15.3, 11.3, 0.8], [0.7, 11.3, 0.8]])} {...hairN} />
      {[[1.1, -3.7], [14.9, -3.7], [1.1, 10.9], [14.9, 10.9]].map(([x, y], i) => <polygon key={i} points={pts(circZ(x, y, 0.8, 0.22, 14))} fill="#f3f3ef" {...hair} />)}
      {/* nameplate */}
      <path d={path([[2.2, 10.2, 0.8], [5.6, 10.2, 0.8], [5.6, 11.4, 0.8], [2.2, 11.4, 0.8]])} fill="#f1f1ed" {...ln} />
      {[0.35, 0.6, 0.85].map((f, i) => <path key={i} d={`M${P(2.7, 10.2 + 1.2 * f, 0.8).join(" ")}L${P(5.1 - i * 0.5, 10.2 + 1.2 * f, 0.8).join(" ")}`} {...hairN} />)}
      {/* rail + ruler */}
      <path d={rail.left} fill="#ecece8" {...ln} /><path d={rail.right} fill="#dcdcd8" {...ln} /><path d={rail.top} fill="#f6f6f3" {...ln} />
      <path d={strip.left} fill="#ecece8" {...ln} /><path d={strip.top} fill="#f6f6f3" {...ln} />
      {Array.from({ length: 30 }, (_, i) => -4 + i * 0.48).map((y, i) => <path key={i} d={`M${P(12.0, y, 0.9).join(" ")}L${P(12.0 + (i % 5 === 0 ? 0.38 : 0.2), y, 0.9).join(" ")}`} {...hairN} />)}
      <path d={stop.left} fill="#ecece8" {...ln} /><path d={stop.right} fill="#dcdcd8" {...ln} /><path d={stop.top} fill="#f6f6f3" {...ln} />
      {/* vault body */}
      <path d={bx.left} fill={C.left} {...ln} /><path d={bx.right} fill={C.right} {...ln} /><path d={bx.top} fill={C.top} {...ln} />
      <path d={path([[2.7, 3.2, 9.8], [9.3, 3.2, 9.8], [9.3, 8.8, 9.8], [2.7, 8.8, 9.8]])} {...hairN} />
      <path d={path([[2.5, 9.5, 1.4], [9.5, 9.5, 1.4], [9.5, 9.5, 9.3], [2.5, 9.5, 9.3]])} {...hairN} strokeDasharray="0.1 5" strokeLinecap="round" strokeWidth={1.2} />
      <path d={path([[10, 3, 1.4], [10, 9, 1.4], [10, 9, 9.3], [10, 3, 9.3]])} {...hairN} strokeDasharray="0.1 5" strokeLinecap="round" strokeWidth={1.2} />
      {[[3.0, 8.4], [8.9, 3.5]].map(([x, y], i) => { const a = circZ(x, y, 9.8, 0.5), b = circZ(x, y, 10.3, 0.5); return <g key={i}><path d={hullPath(a, b)} fill="#efefeb" {...ln} /><polygon points={pts(b)} fill="#f7f7f4" {...ln} /></g>; })}
      {/* label plate */}
      <path d={path([[3, 9.5, 6.1], [6.3, 9.5, 6.1], [6.3, 9.5, 8.1], [3, 9.5, 8.1]])} fill="#f4f4f0" {...ln} />
      {[0.3, 0.5, 0.7].map((f, i) => <path key={i} d={`M${P(3.4, 9.5, 6.1 + 2 * f).join(" ")}L${P(5.9 - i * 0.5, 9.5, 6.1 + 2 * f).join(" ")}`} {...hairN} />)}
      {/* reader: USB key, keypad, indicator */}
      <g>
        <path d={reader.right} fill="#dcdcd8" {...ln} /><path d={reader.left} fill="#f3f3ef" {...ln} />
        <path d={path([[9.05, 9.75, 5.9], [9.35, 9.75, 5.9], [9.35, 9.75, 6.9], [9.05, 9.75, 6.9]])} fill="#f6f6f3" {...ln} />
        <path d={path([[9.15, 9.75, 6.35], [9.25, 9.75, 6.35], [9.25, 9.75, 6.6], [9.15, 9.75, 6.6]])} fill="#444" />
        <path d={path([[8.85, 9.75, 4.9], [9.3, 9.75, 4.9], [9.3, 9.75, 5.3], [8.85, 9.75, 5.3]])} fill={indicator} stroke={C.stroke} strokeWidth=".6" vectorEffect="non-scaling-stroke" />
        {Array.from({ length: 12 }, (_, i) => {
          const c = i % 3, rr = Math.floor(i / 3), x = 8.78 + c * 0.26, z = 4.45 - rr * 0.4;
          return <path key={i} d={path([[x, 9.75, z], [x + 0.17, 9.75, z], [x + 0.17, 9.75, z - 0.26], [x, 9.75, z - 0.26]])} fill={flash > 0 ? `rgba(255,255,255,${0.4 + flash * 0.6})` : "#e2e2de"} stroke="#8c8f94" strokeWidth=".5" vectorEffect="non-scaling-stroke" />;
        })}
      </g>
      {/* opening */}
      <polygon points={pts(circX(10, OC.y, OC.z, 3.15))} fill="#dcdcd8" {...ln} />
      <polygon points={pts(circX(10, OC.y, OC.z, 3.0))} {...hairN} />
      <polygon points={pts(circX(10, OC.y, OC.z, 2.6))} fill="#c3c3be" {...ln} />
      <g clipPath="url(#vOpening)">
        <polygon points={pts(circX(9.9, OC.y - 0.35, OC.z + 0.25, 2.6))} fill="#d6d6d2" />
        {drawers.map(({ c, r }, i) => {
          const y0 = OC.y - 2.35 + c * 1.2, z0 = OC.z - 2.35 + r * 1.2;
          const a = io(seg(p, 0.55 + i * 0.025, 0.78 + i * 0.025));
          const f = (dy: number, dz: number): V3 => [9.9, y0 + dy, z0 + dz];
          return (
            <g key={i} style={{ opacity: a }}>
              <path d={path([f(0, 0), f(1.05, 0), f(1.05, 1.0), f(0, 1.0)])} fill="#ecece8" stroke="#80848a" strokeWidth=".8" vectorEffect="non-scaling-stroke" />
              <path d={path([f(0.25, 0.38), f(0.8, 0.38), f(0.8, 0.55), f(0.25, 0.55)])} fill="#f8f8f6" stroke="#80848a" strokeWidth=".6" vectorEffect="non-scaling-stroke" />
            </g>
          );
        })}
      </g>
      <polygon points={pts(circX(10, OC.y, OC.z, 2.6))} fill="none" {...ln} />
      {/* carriage + door */}
      <g>
        <path d={car.left} fill="#eeeeea" {...ln} /><path d={car.right} fill="#dcdcd8" {...ln} /><path d={car.top} fill="#f7f7f4" {...ln} />
        {[-0.7, 0.7].map((o, i) => <polygon key={i} points={pts(circX(11.6, yd + o, 1.15, 0.34, 22))} fill="#f4f4f0" {...ln} />)}
        <rect x={sx - 6} y={sy2} width={12} height={sy1 - sy2} fill="#ecece8" {...ln} />
        <ellipse cx={sx} cy={sy1} rx={6} ry={3} fill="#f4f4f0" {...ln} />
      </g>
      <g>
        <path d={hullPath(back, front)} fill="#dededa" {...ln} />
        <polygon points={pts(front)} fill="#f4f4f1" {...ln} />
        <polygon points={pts(circX(xf, yd, OC.z, 3.0))} fill="#f9f9f7" {...hair} />
        <polygon points={pts(circX(xf, yd, OC.z, 2.55))} fill="none" {...hair} />
        {spokes.map((a, i) => {
          const d = `M${P(...pl(0.6, a, xf)).join(" ")}L${P(...pl(1.95, a, xf)).join(" ")}`;
          const knob = Array.from({ length: 24 }, (_, k) => { const t = (k / 24) * Math.PI * 2; return [xf, yd + 1.95 * Math.cos(a) + 0.36 * Math.cos(t), OC.z + 1.95 * Math.sin(a) + 0.36 * Math.sin(t)] as V3; });
          return <g key={i}><path d={d} stroke={C.stroke} strokeWidth={9} strokeLinecap="round" /><path d={d} stroke="#fbfbf9" strokeWidth={6.6} strokeLinecap="round" /><polygon points={pts(knob)} fill="#fff" {...ln} /></g>;
        })}
        <polygon points={pts(circX(xf, yd, OC.z, 1.2))} fill="#ededea" {...ln} />
        <polygon points={pts(circX(xf, yd, OC.z, 0.95))} fill="#fafaf8" {...hair} />
        {ticks.map((a, i) => <path key={i} d={`M${P(...pl(0.95, a, xf)).join(" ")}L${P(...pl(i % 4 === 0 ? 1.2 : 1.08, a, xf)).join(" ")}`} stroke="#6a6d72" strokeWidth=".8" vectorEffect="non-scaling-stroke" />)}
        <polygon points={pts(circX(xf, yd, OC.z, 0.38))} fill="#f6f6f3" {...ln} />
        <polygon points={pts(circX(xf, yd, OC.z, 0.16))} fill="#cfcfca" {...hair} />
      </g>
      {/* click / keyboard target on the wheel */}
      <g role="button" tabIndex={0} aria-pressed={open} aria-label={open ? "Close vault" : "Open vault"} className="vault-hit"
        onClick={toggle} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } }}>
        <circle cx={cx} cy={cy} r={62} fill="transparent" /><circle cx={cx} cy={cy} r={66} className="vault-focus" fill="none" />
      </g>
    </svg>
  );
}
