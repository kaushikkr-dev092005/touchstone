import type { ReactNode } from "react";

const ICONS: Record<string, () => ReactNode> = {
  home: () => <path d="m3 10 9-7 9 7v11h-6v-8H9v8H3Z" />,
  dashboard: () => <><rect x="3" y="3" width="18" height="18" rx="4" /><path d="M7 14v-4m5 7V7m5 8V9" /></>,
  ledger: () => <path d="m3 7 9-4 9 4-9 4-9-4Zm0 5 9 4 9-4M3 17l9 4 9-4" />,
  arrow: () => <path d="M5 12h14m-6-6 6 6-6 6" />,
  check: () => <><rect x="4" y="3" width="16" height="18" rx="1" /><path d="m8 11 3 3 6-6" /></>,
  grid: () => <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
  close: () => <path d="m6 6 12 12M6 18 18 6" />,
  shield: () => <><path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z" /><path d="m8 11 3 3 5-6" /></>,
  spark: () => <><path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z" /><path d="M18.5 16.5v3M17 18h3" /></>,
  wallet: () => <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="M15 12h6v4h-6a2 2 0 0 1 0-4ZM7 9h6" /></>,
  search: () => <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  bell: () => <><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9" /><path d="M10 19a2 2 0 0 0 4 0" /></>,
  "chevron-left": () => <path d="m15 6-6 6 6 6" />,
  "chevron-right": () => <path d="m9 6 6 6-6 6" />,
  "chevron-down": () => <path d="m6 9 6 6 6-6" />,
  dots: () => <><circle cx="6" cy="12" r="1.4" fill="currentColor" stroke="none" /><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" /><circle cx="18" cy="12" r="1.4" fill="currentColor" stroke="none" /></>,
  cpu: () => <><rect x="6" y="6" width="12" height="12" rx="2" /><path d="M9 1v3m6-3v3M9 20v3m6-3v3M1 9h3m-3 6h3m16-6h3m-3 6h3" /></>,
  bolt: () => <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />,
};

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const render = ICONS[name];
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {render ? render() : <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" /></>}
    </svg>
  );
}

export function Brand() {
  return <span className="brand-lockup" aria-label="Touchstone"><span className="brand-flower" aria-hidden="true">{[0, 1, 2, 3].map(i => <i key={i} />)}</span><span className="wordmark" aria-hidden="true">touchstone</span></span>;
}

export function LogoStudy() {
  return <div className="logo-study" aria-label="Animated Touchstone identity"><div className="logo-study-dots" aria-hidden="true">{[0, 1, 2, 3].map(i => <i key={i} />)}</div><svg className="logo-study-word" viewBox="0 0 760 180" aria-hidden="true"><g className="logo-construction" fill="none" stroke="currentColor" strokeWidth=".6">{[37, 81, 138].map(y => <path key={y} d={"M15 " + y + "H745"} />)}{Array.from({ length: 11 }, (_, i) => <g key={i}><path d={"M" + (35 + i * 68) + " 20v140"} /><circle cx={35 + i * 68} cy="81" r="42" /></g>)}</g><text x="380" y="132" textAnchor="middle" textLength="700" lengthAdjust="spacingAndGlyphs">touchstone</text></svg><span className="logo-study-label mono">ONE IDENTITY. THROUGH EVERY STATE.</span></div>;
}
