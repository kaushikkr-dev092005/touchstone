import { useState } from "react";

/* Isometric icons. Colours come from CSS variables (dark-theme values are the defaults),
   every cluster is a labelled <g data-layer> so it can be animated. */
const F = "var(--icon-fill,#0a0a0a)", S = "var(--icon-stroke,#63666d)", H = "var(--icon-hi,#d1d6df)", I = "var(--icon-inner,#2c2e31)";
const SPRING = "transform 620ms cubic-bezier(.34,1.56,.64,1)";
const common = { width: 96, height: 96, viewBox: "0 0 48 48", fill: "none", strokeWidth: 1, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, role: "img" };

const SLAB = "M38.21 18.05Q39.94 19.05 40.51 19.45L41.09 19.85Q41.66 20.26 42.09 20.72L42.52 21.18Q42.94 21.64 43.21 22.14L43.47 22.64Q43.73 23.15 43.82 23.67L43.91 24.19Q44 24.71 44 26.6L44 28.48Q44 30.37 43.91 30.89L43.82 31.41Q43.73 31.93 43.47 32.43L43.21 32.93Q42.94 33.43 42.52 33.9L42.09 34.36Q41.66 34.82 41.09 35.22L40.51 35.63Q39.94 36.03 39.24 36.36L38.54 36.7Q37.84 37.03 37.04 37.28L36.24 37.52Q35.44 37.77 34.57 37.92L33.7 38.07Q32.84 38.22 31.93 38.28L31.03 38.33Q30.13 38.38 29.23 38.33L28.33 38.28Q27.42 38.22 26.56 38.07L25.69 37.92Q24.82 37.77 24.02 37.52L23.22 37.28Q22.42 37.03 21.72 36.7L21.02 36.36Q20.32 36.03 18.59 35.03L9.79 29.95Q8.06 28.95 7.49 28.55L6.91 28.15Q6.34 27.74 5.91 27.28L5.48 26.82Q5.06 26.36 4.79 25.86L4.53 25.36Q4.27 24.85 4.18 24.33L4.09 23.81Q4 23.29 4 21.4L4 19.52Q4 17.63 4.09 17.11L4.18 16.59Q4.27 16.07 4.53 15.57L4.79 15.07Q5.06 14.57 5.48 14.1L5.91 13.64Q6.34 13.18 6.91 12.78L7.49 12.37Q8.06 11.97 8.76 11.64L9.46 11.3Q10.16 10.97 10.96 10.72L11.76 10.48Q12.56 10.23 13.43 10.08L14.3 9.93Q15.16 9.78 16.07 9.72L16.97 9.67Q17.87 9.62 18.77 9.67L19.67 9.72Q20.58 9.78 21.44 9.93L22.31 10.08Q23.18 10.23 23.98 10.48L24.78 10.72Q25.58 10.97 26.28 11.3L26.98 11.64Q27.68 11.97 29.41 12.97Z";
const SLAB_INNER = "M41.66 29.16L40.51 29.97Q39.94 30.37 39.24 30.7L38.54 31.03Q37.84 31.37 37.04 31.61L36.24 31.86Q35.44 32.11 34.57 32.26L33.7 32.41Q32.84 32.56 31.93 32.61L31.03 32.66Q30.13 32.72 29.23 32.66L28.33 32.61Q27.42 32.56 26.56 32.41L25.69 32.26Q24.82 32.11 24.02 31.86L23.22 31.61Q22.42 31.37 21.72 31.03L21.02 30.7Q20.32 30.37 18.59 29.37L9.79 24.29Q8.06 23.29 7.49 22.89L6.34 22.08";
const WALL = "M23.19 23.43L23.19 24.71A6.94 4 0 0 0 37.06 24.71L37.06 23.43";

export function ToggleIcon({ on, className }: { on?: boolean; className?: string }) {
  const [hover, setHover] = useState(false);
  const active = on ?? hover;
  return (
    <svg {...common} aria-label="Toggle" className={className} onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)} onFocus={() => setHover(true)} onBlur={() => setHover(false)}>
      <g data-layer="slab">
        <path d={SLAB} fill={F} stroke={S} />
        <path d={SLAB_INNER} stroke={I} />
      </g>
      <g data-layer="knob" style={{ transform: active ? "translate(-15.7px,-9.06px)" : "none", transition: SPRING }}>
        <path d={WALL} fill={F} stroke={H} />
        <ellipse cx="30.13" cy="23.43" rx="6.94" ry="4" fill={F} stroke={H} />
      </g>
    </svg>
  );
}

const CUBE = "M22.27 17.36Q24 16.36 25.73 17.36L28.07 18.72Q29.81 19.72 29.81 21.72L29.81 24.42Q29.81 26.42 28.07 27.42L25.73 28.77Q24 29.77 22.27 28.77L19.93 27.42Q18.19 26.42 18.19 24.42L18.19 21.72Q18.19 19.72 19.93 18.72Z";
const CUBE_LINES = ["M24 23.07L27.53 21.03", "M24 23.07L20.47 21.03", "M24 23.07L24 27.14"];
function Cube({ dx, dy, delay, stroke, id }: { dx: number; dy: number; delay: number; stroke: string; id: string }) {
  return (
    <g data-layer={id} transform={`translate(${dx} ${dy})`}>
      <g className="net-cube" style={{ animationDelay: `${delay}ms` }}>
        <path d={CUBE} fill={F} stroke={stroke} />
        {CUBE_LINES.map((d) => <path key={d} d={d} stroke={I} />)}
      </g>
    </g>
  );
}
export function NetworkIcon({ className }: { className?: string }) {
  return (
    <svg {...common} aria-label="Network" className={className}>
      <g data-layer="connectors">
        <path d="M24 23.07L38.19 31.26" stroke={S} /><path d="M24 23.07L9.81 31.26" stroke={S} />
        <path d="M24 23.07L38.19 31.26" stroke={H} className="net-pulse" pathLength={1} />
        <path d="M24 23.07L9.81 31.26" stroke={H} className="net-pulse" pathLength={1} style={{ animationDelay: "350ms" }} />
      </g>
      <Cube id="cube-top" dx={0} dy={0} delay={0} stroke={H} />
      <Cube id="cube-right" dx={14.19} dy={8.19} delay={260} stroke={S} />
      <Cube id="cube-left" dx={-14.19} dy={8.19} delay={520} stroke={S} />
    </svg>
  );
}

const iso = (cx: number, cy: number, hw: number, t: number) => {
  const hh = hw * 0.577;
  return {
    top: `M${cx} ${cy - hh}L${cx + hw} ${cy}L${cx} ${cy + hh}L${cx - hw} ${cy}Z`,
    left: `M${cx - hw} ${cy}L${cx} ${cy + hh}L${cx} ${cy + hh + t}L${cx - hw} ${cy + t}Z`,
    right: `M${cx + hw} ${cy}L${cx} ${cy + hh}L${cx} ${cy + hh + t}L${cx + hw} ${cy + t}Z`,
  };
};
function Slab({ g, stroke, hw, cx, cy, t, topFill }: { g: ReturnType<typeof iso> | null; stroke: string; hw: number; cx: number; cy: number; t: number; topFill?: string }) {
  const s = g ?? iso(cx, cy, hw, t);
  return <>
    <path d={s.left} fill={F} stroke={stroke} /><path d={s.right} fill={F} stroke={stroke} />
    <path d={s.top} fill={topFill ?? F} stroke={stroke} />
  </>;
}
export function LayoutIcon({ className }: { className?: string }) {
  const [hover, setHover] = useState(false);
  const up = (n: number) => ({ transform: hover ? `translateY(${-n}px)` : "none", transition: SPRING });
  return (
    <svg {...common} aria-label="Layout" className={className} onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)} onFocus={() => setHover(true)} onBlur={() => setHover(false)}>
      <g data-layer="base"><Slab g={null} stroke={S} hw={19} cx={24} cy={36} t={3} /></g>
      <g data-layer="middle" style={up(7)}>
        <Slab g={null} stroke={S} hw={7} cx={15.5} cy={31} t={3.5} />
        <Slab g={null} stroke={S} hw={7} cx={32.5} cy={31} t={3.5} />
      </g>
      <g data-layer="top-plate" style={up(14)}>
        <Slab g={null} stroke={H} hw={17} cx={24} cy={23} t={2} />
      </g>
    </svg>
  );
}
