import { Glass } from "@samasante/liquid-glass";
import type { CSSProperties, ReactNode } from "react";
import { useRef } from "react";

/* Themed wrapper around the real <Glass> lens: tint tuned per theme through CSS vars, an inner
   highlight border (also the fallback look in browsers without SVG backdrop refraction), and a
   cursor-following specular. */
export default function GlassSurface({ children, className = "", style, radius = 16, tint = "var(--glass-tint)", ...rest }:
  { children?: ReactNode; className?: string; style?: CSSProperties; radius?: number; tint?: string } & React.HTMLAttributes<HTMLDivElement>) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
  };
  return (
    <Glass
      {...rest}
      optics={{ frost: 6, dispersion: 0.12 }}
      className={`gs ${className}`}
      onPointerMove={(e) => { move(e); rest.onPointerMove?.(e); }}
      style={{ background: tint, borderRadius: radius, display: "block", ...style }}
    >
      <div ref={ref} className="gs-spec" aria-hidden="true" />
      {children}
    </Glass>
  );
}
