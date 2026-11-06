import { useSyncExternalStore } from "react";
export type Theme = "light" | "dark";
const KEY = "ts-theme";
const get = (): Theme => (document.documentElement.classList.contains("light") ? "light" : "dark");
const subs = new Set<() => void>();
function apply(t: Theme) {
  const d = document.documentElement;
  d.classList.remove("light", "dark");
  d.classList.add(t);
  d.style.colorScheme = t;
  try { localStorage.setItem(KEY, t); } catch {}
  subs.forEach((f) => f());
}
export function useTheme(): Theme {
  return useSyncExternalStore((f) => { subs.add(f); return () => subs.delete(f); }, get, () => "dark" as Theme);
}
/** Switch theme with a circular reveal from (x,y) via View Transitions; falls back to a cross-fade. */
export function setTheme(next: Theme, x: number, y: number) {
  if (get() === next) return;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const doc = document as Document & { startViewTransition?: (cb: () => void) => { ready: Promise<void> } };
  if (reduce) return apply(next);
  if (doc.startViewTransition) {
    const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    const vt = doc.startViewTransition(() => apply(next));
    vt.ready.then(() =>
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
        { duration: 650, easing: "cubic-bezier(.22,.8,.3,1)", pseudoElement: "::view-transition-new(root)" },
      ),
    ).catch(() => {});
  } else {
    document.documentElement.classList.add("theme-fade");
    apply(next);
    setTimeout(() => document.documentElement.classList.remove("theme-fade"), 520);
  }
}
