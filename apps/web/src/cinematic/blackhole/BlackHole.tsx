import { useEffect, useRef, useState } from "react";
import { BlackHoleRenderer, type HoleState } from "./renderer";

/**
 * Persistent full-viewport black hole. Mounted once at the app root; other modules drive it
 * through `holeHandle` (GSAP tweens `holeHandle.state.*` and calls `wake()` on update).
 * The render loop stops by itself when intensity reaches 0 or the tab is hidden.
 */
/** One state object for the app lifetime, so tweens survive renderer re-creation. */
const sharedState: HoleState = { ignite: 0, intensity: 0, point: 0, bloomBoost: 0 };
let renderer: BlackHoleRenderer | null = null;
let canvasEl: HTMLCanvasElement | null = null;
let fallbackEl: HTMLDivElement | null = null;

function sync() {
  const s = holeHandle.state;
  if (canvasEl) canvasEl.style.opacity = s.intensity > 0 ? "1" : "0";
  if (fallbackEl) fallbackEl.style.opacity = String(Math.min(1, s.ignite) * s.intensity * (1 - Math.min(1, scrollProgress)));
}
let scrollProgress = 0;

export const holeHandle = {
  get state(): HoleState { return sharedState; },
  get supported() { return renderer !== null; },
  wake() { sync(); renderer?.wake(); },
  renderOnce() { sync(); renderer?.renderOnce(); },
  setStartPoint(x: number, y: number) { if (renderer) renderer.startPoint = { x: x / innerWidth, y: y / innerHeight }; },
  setScroll(p: number) { scrollProgress = p; if (renderer) renderer.scroll = p; this.wake(); },
  level: () => renderer?.level ?? -1,
  frameMs: () => renderer?.frameMs ?? 0,
};

export default function BlackHole() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const fallback = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (failed) { fallbackEl = fallback.current; sync(); return () => { fallbackEl = null; }; }
    const el = canvas.current!;
    let r: BlackHoleRenderer;
    try {
      r = new BlackHoleRenderer(el, { mobile: matchMedia("(pointer: coarse)").matches || innerWidth < 700, state: sharedState });
    } catch (error) {
      console.warn("Touchstone: WebGL black hole unavailable, using the static fallback.", error);
      setFailed(true);
      return;
    }
    renderer = r; canvasEl = el;
    if (new URLSearchParams(location.search).get("debug") === "1") (window as unknown as { __hole: unknown }).__hole = r;
    sync(); if (r.state.intensity > 0) r.renderOnce();
    const onResize = () => r.resize();
    const onMove = (e: PointerEvent) => r.setMouse(e.clientX / innerWidth * 2 - 1, -(e.clientY / innerHeight * 2 - 1));
    const onVisibility = () => r.setPaused(document.hidden);
    const onLost = (e: Event) => { e.preventDefault(); setFailed(true); };
    addEventListener("resize", onResize);
    addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    el.addEventListener("webglcontextlost", onLost);
    return () => {
      removeEventListener("resize", onResize);
      removeEventListener("pointermove", onMove);
      document.removeEventListener("visibilitychange", onVisibility);
      el.removeEventListener("webglcontextlost", onLost);
      if (renderer === r) { renderer = null; canvasEl = null; }
      r.dispose();
    };
  }, [failed]);

  return <div className="hole-layer" aria-hidden="true">
    {failed ? <div ref={fallback} className="hole-fallback" /> : <canvas ref={canvas} className="hole-canvas" />}
  </div>;
}
