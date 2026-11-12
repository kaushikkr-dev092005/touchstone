import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import type { VaultPhases } from "../timeline";
import {
  BACK_X, box, C30, CARRIAGE, cylinderX, DOOR, DOOR_TRAVEL, doorCenter, ellipseX, H, iso, KEYBOX, keyboxFaces,
  plane, PLATE, poly, RAIL, RING, rivets, S30, VIEWBOX,
} from "./geometry";

export type VaultVariant = "intro" | "dashboard";
type Props = {
  variant: VaultVariant;
  phases: VaultPhases;
  /** Receives the paused timeline so a controller can nest it in its master timeline. */
  onTimeline: (tl: gsap.core.Timeline, api: VaultApi) => void;
  caption?: string;
};
export type VaultApi = {
  /** Viewport position of the bright point the seam collapses into. */
  pointPosition(): { x: number; y: number };
  pointEl: HTMLDivElement;
};

const [DCX, DCY] = doorCenter();
const plateFaces = box(PLATE.x0, PLATE.x1, PLATE.y0, PLATE.y1, PLATE.z0, 0);
const railFaces = box(RAIL.x0, RAIL.x1, RAIL.y0, RAIL.y1, 0, 1.6);
const carriage = box(CARRIAGE.x0, CARRIAGE.x1, 100 - DOOR.cu - CARRIAGE.half, 100 - DOOR.cu + CARRIAGE.half, CARRIAGE.z0, CARRIAGE.z1);
const stemTop = H - (DOOR.cv + DOOR.r) + 1.5;
const stem = box(104, 107.5, 100 - DOOR.cu - 1.8, 100 - DOOR.cu + 1.8, CARRIAGE.z1, stemTop);
const KEY_ORIGIN = iso(BACK_X + KEYBOX.out - 8, 100 - (KEYBOX.u0 + KEYBOX.u1) / 2, H - KEYBOX.v0);
const seamPath = ellipseX(DOOR.x1 - 0.5, DOOR.cu, DOOR.cv, DOOR.r + 0.6, 120);
const openingClip = ellipseX(RING.x1, DOOR.cu, DOOR.cv, RING.inner, 96);
const cubeHex = poly([iso(0, 0, H), iso(100, 0, H), iso(100, 0, 0), iso(100, 100, 0), iso(0, 100, 0), iso(0, 100, H)]);
const knob = (x: number, y: number) => {
  const [sx, sy] = iso(x, y, H), rx = 1.2247 * 4.2, ry = 0.7071 * 4.2, h = 5;
  return <g key={x + "-" + y}><path d={`M${sx - rx} ${sy}V${sy - h}H${sx + rx}V${sy}Z`} fill="url(#vs-side)" /><ellipse cx={sx} cy={sy} rx={rx} ry={ry} fill="url(#vs-side)" /><ellipse cx={sx} cy={sy - h} rx={rx} ry={ry} fill="#fbfbf8" /><ellipse cx={sx} cy={sy - h} rx={rx * 0.55} ry={ry * 0.55} fill="none" /></g>;
};
const railTicks = Array.from({ length: 19 }, (_, i) => RAIL.y0 + 4 + i * 8);
const drawerSlots = [36, 52, 68].flatMap(u => [38, 50, 62].map(v => ({ u, v }))).filter(d => !(d.u === 52 && d.v === 50));

export default function VaultSequence({ variant, phases, onTimeline, caption }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const point = useRef<HTMLDivElement>(null);
  const cb = useRef(onTimeline);
  cb.current = onTimeline;

  useLayoutEffect(() => {
    const el = root.current!, s = svg.current!, q = <T extends Element>(id: string) => s.querySelector<T>("#" + id)!;
    const doorAsm = q<SVGGElement>("door-assembly"), swing = q<SVGGElement>("door-swing"), dial = q<SVGGElement>("dial"), spokes = q<SVGGElement>("spokes");
    const led = q<SVGRectElement>("led-light"), ledGlow = q<SVGCircleElement>("led-glow"), interiorGlow = q<SVGGElement>("interior-glow"), drawers = q<SVGGElement>("drawers");
    const kbInnerTop = q<SVGPathElement>("kb-in-top"), kbInnerLeft = q<SVGPathElement>("kb-in-left"), kbInnerFront = q<SVGPathElement>("kb-in-front");
    const kbOut = q<SVGGElement>("keybox"), kbOutTop = q<SVGPathElement>("kb-out-top"), kbOutLeft = q<SVGPathElement>("kb-out-left"), kbOutFront = q<SVGPathElement>("kb-out-front"), kbHole = q<SVGGElement>("kb-keyhole");
    const key = q<SVGGElement>("key"), seam = q<SVGPathElement>("seam-light"), seamGroup = q<SVGGElement>("seam-group"), stage = s;
    const cap = el.querySelector<HTMLElement>(".vault-caption");

    const P = { dial: 0, spokes: 0, travel: 0, bolt: 0, swing: 1, pull: 0, keyY: 0, keyRot: 0, key: 0, glow: 0, drawers: 0, led: 0, ledBlink: 1, seam: 0, seamOn: 0, seamFull: 0, seamScale: 1, point: 0 };
    let lastPull = -1;
    const red = [255, 77, 61], green = [80, 255, 160];
    let pointPos = { x: innerWidth / 2, y: innerHeight * 0.46 };

    const measure = () => {
      const m = s.getScreenCTM();
      if (!m) return;
      const p = new DOMPoint(DCX, DCY).matrixTransform(m);
      pointPos = { x: p.x, y: p.y };
    };

    const apply = () => {
      dial.setAttribute("transform", `rotate(${P.dial.toFixed(2)} ${DOOR.cu} ${DOOR.cv})`);
      spokes.setAttribute("transform", `rotate(${P.spokes.toFixed(2)} ${DOOR.cu} ${DOOR.cv})`);
      const tx = C30 * (P.travel + P.bolt), ty = -S30 * P.travel + S30 * P.bolt;
      doorAsm.setAttribute("transform", `translate(${tx.toFixed(2)} ${ty.toFixed(2)})`);
      swing.setAttribute("transform", `translate(${DCX} ${DCY}) scale(${P.swing.toFixed(4)} 1) translate(${-DCX} ${-DCY})`);
      if (Math.abs(P.pull - lastPull) > 0.01) {
        lastPull = P.pull;
        const k = keyboxFaces(P.pull);
        kbInnerTop.setAttribute("d", k.inner.top); kbInnerLeft.setAttribute("d", k.inner.left); kbInnerFront.setAttribute("d", k.inner.front);
        kbOut.style.display = k.outer ? "" : "none";
        if (k.outer) { kbOutTop.setAttribute("d", k.outer.top); kbOutLeft.setAttribute("d", k.outer.left); kbOutFront.setAttribute("d", k.outer.front); }
        kbHole.setAttribute("transform", plane.z(k.z1) + ` translate(${(k.xf - 9).toFixed(2)} ${(k.y0 + k.y1) / 2})`);
      }
      const [kx, ky] = KEY_ORIGIN;
      key.setAttribute("transform", `translate(${kx.toFixed(2)} ${(ky + P.keyY).toFixed(2)}) rotate(${P.keyRot.toFixed(2)}) scale(1.45)`);
      key.style.opacity = String(P.key);
      interiorGlow.style.opacity = String(P.glow);
      drawers.style.opacity = String(0.35 + 0.65 * P.drawers);
      const c = red.map((r, i) => Math.round(r + (green[i] - r) * P.led));
      led.setAttribute("fill", `rgb(${c})`);
      ledGlow.setAttribute("fill", `rgb(${c})`);
      ledGlow.style.opacity = String(0.55 * P.ledBlink);
      led.style.opacity = String(0.35 + 0.65 * P.ledBlink);
      seam.style.strokeDashoffset = String(1000 - P.seam * 1000);
      seam.style.opacity = String(P.seamOn);
      const dash = 160 + 840 * P.seamFull;
      seam.style.strokeDasharray = `${dash.toFixed(1)} ${(1000 - dash + 0.01).toFixed(1)}`;
      seamGroup.setAttribute("transform", `translate(${DCX} ${DCY}) scale(${P.seamScale.toFixed(4)}) translate(${-DCX} ${-DCY})`);
      if (point.current) {
        point.current.style.opacity = String(P.point);
        point.current.style.transform = `translate(${pointPos.x}px, ${pointPos.y}px) translate(-50%, -50%) scale(${(0.25 + 0.75 * P.point).toFixed(3)})`;
      }
    };

    measure(); apply();
    const onResize = () => { measure(); apply(); };
    addEventListener("resize", onResize);

    const v = phases;
    const tl = gsap.timeline({ paused: true, onUpdate: apply, defaults: { ease: "power2.inOut" } });
    let t = 0;
    // safeIn
    tl.addLabel("safeIn", t);
    tl.fromTo(stage, { opacity: 0, scale: 0.94, y: 24, filter: "blur(14px)" }, { opacity: 1, scale: 1, y: 0, filter: "blur(0px)", duration: v.safeIn, ease: "power3.out", transformOrigin: "50% 55%" }, t);
    t += v.safeIn;
    // locked: LED blinks once, dial ticks two notches
    tl.addLabel("locked", t);
    tl.to(P, { ledBlink: 0.15, duration: Math.min(0.12, v.locked * 0.2), yoyo: true, repeat: 1, ease: "none" }, t + v.locked * 0.1);
    tl.to(P, { dial: 10, duration: v.locked * 0.18, ease: "power3.out" }, t + v.locked * 0.4);
    tl.to(P, { dial: 20, duration: v.locked * 0.18, ease: "power3.out" }, t + v.locked * 0.68);
    t += v.locked;
    // unlock: 2 turns CW, 1 CCW, settle; handle 120°, LED red → green, bolts retract
    tl.addLabel("unlock", t);
    tl.to(P, { dial: 20 + 720, duration: v.unlock * 0.5, ease: "power2.inOut" }, t);
    tl.to(P, { dial: 20 + 360 + 4, duration: v.unlock * 0.32, ease: "power3.out" }, t + v.unlock * 0.5);
    tl.to(P, { dial: 20 + 360, duration: v.unlock * 0.12, ease: "back.out(3)" }, t + v.unlock * 0.82);
    tl.to(P, { spokes: 120, duration: v.unlock * 0.42, ease: "power2.inOut" }, t + v.unlock * 0.5);
    tl.to(P, { led: 1, duration: v.unlock * 0.15, ease: "none" }, t + v.unlock * 0.82);
    tl.to(P, { bolt: 2.4, duration: v.unlock * 0.18, ease: "power2.out" }, t + v.unlock * 0.82);
    t += v.unlock;
    // doorOpen: carriage slides the door along the rail; door swings; interior warms
    tl.addLabel("doorOpen", t);
    tl.to(P, { travel: DOOR_TRAVEL, duration: v.doorOpen, ease: "power2.inOut" }, t);
    tl.to(P, { swing: 0.84, duration: v.doorOpen * 0.45, ease: "sine.inOut", yoyo: true, repeat: 1 }, t + v.doorOpen * 0.05);
    tl.to(P, { glow: 1, drawers: 1, duration: v.doorOpen * 0.7, ease: "power1.out" }, t + v.doorOpen * 0.3);
    t += v.doorOpen;
    // keyReveal: drawer slides ~40% out; key rises with a 15° turn; hold
    tl.addLabel("keyReveal", t);
    tl.to(P, { pull: KEYBOX.out, duration: v.keyReveal * 0.4, ease: "power3.out" }, t);
    tl.to(P, { keyY: -46, keyRot: 15, key: 1, duration: v.keyReveal * 0.45, ease: "power2.out" }, t + v.keyReveal * 0.18);
    if (cap) tl.fromTo(cap, { opacity: 0, y: 6 }, { opacity: 1, y: 0, duration: 0.3, ease: "power2.out" }, t);
    t += v.keyReveal;
    // keyStow
    tl.addLabel("keyStow", t);
    tl.to(P, { keyY: 0, keyRot: 0, key: 0, duration: v.keyStow * 0.55, ease: "power2.in" }, t);
    tl.to(P, { pull: 0, duration: v.keyStow * 0.55, ease: "power2.inOut" }, t + v.keyStow * 0.4);
    tl.to(P, { glow: 0.35, duration: v.keyStow, ease: "power1.inOut" }, t);
    if (cap) tl.to(cap, { opacity: 0, duration: 0.25 }, t);
    t += v.keyStow;
    // doorClose: exact reverse, then handle/dial back, LED → red, seam pulse
    tl.addLabel("doorClose", t);
    tl.to(P, { travel: 0, duration: v.doorClose * 0.62, ease: "power2.inOut" }, t);
    tl.to(P, { swing: 0.84, duration: v.doorClose * 0.28, ease: "sine.inOut", yoyo: true, repeat: 1 }, t + v.doorClose * 0.03);
    tl.to(P, { glow: 0, drawers: 0, duration: v.doorClose * 0.5, ease: "power1.in" }, t + v.doorClose * 0.15);
    tl.to(P, { bolt: 0, duration: v.doorClose * 0.12, ease: "power2.in" }, t + v.doorClose * 0.62);
    tl.to(P, { spokes: 0, duration: v.doorClose * 0.25, ease: "power2.inOut" }, t + v.doorClose * 0.64);
    tl.to(P, { dial: 0, duration: v.doorClose * 0.3, ease: "power3.out" }, t + v.doorClose * 0.64);
    tl.to(P, { led: 0, duration: v.doorClose * 0.1, ease: "none" }, t + v.doorClose * 0.86);
    tl.set(P, { seam: 0, seamOn: 1 }, t + v.doorClose * 0.6);
    tl.to(P, { seam: 1, duration: v.doorClose * 0.4, ease: "power1.inOut" }, t + v.doorClose * 0.6);
    t += v.doorClose;
    // safeOut: seam light contracts into one point; vault dissolves around it
    tl.addLabel("safeOut", t);
    tl.to(P, { seamFull: 1, duration: v.safeOut * 0.15, ease: "power1.out" }, t);
    tl.to(P, { seamScale: 0.02, duration: v.safeOut * 0.4, ease: "power3.in" }, t + v.safeOut * 0.08);
    tl.to(P, { point: 1, duration: v.safeOut * 0.3, ease: "power2.out" }, t + v.safeOut * 0.25);
    tl.to(P, { seamOn: 0, duration: v.safeOut * 0.12 }, t + v.safeOut * 0.42);
    tl.to(stage, { opacity: 0, scale: 1.04, filter: "blur(10px)", duration: v.safeOut * 0.7, ease: "power2.in" }, t + v.safeOut * 0.3);
    t += v.safeOut;
    tl.addLabel("end", t);

    cb.current(tl, { pointPosition: () => { measure(); return pointPos; }, pointEl: point.current! });
    return () => { removeEventListener("resize", onResize); tl.kill(); };
  }, [phases]);

  const k0 = keyboxFaces(0);
  return <div ref={root} className={"vault-sequence vault-" + variant} aria-hidden="true">
    <svg ref={svg} className="vault-svg-iso" viewBox={`${VIEWBOX.x} ${VIEWBOX.y} ${VIEWBOX.w} ${VIEWBOX.h}`} role="presentation">
      <defs>
        <linearGradient id="vs-top" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#fbfbf8" /><stop offset="1" stopColor="#efefea" /></linearGradient>
        <linearGradient id="vs-left" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f3f3ef" /><stop offset="1" stopColor="#e2e2dc" /></linearGradient>
        <linearGradient id="vs-front" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#ebebe6" /><stop offset="1" stopColor="#d9d9d3" /></linearGradient>
        <linearGradient id="vs-side" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#e4e4de" /><stop offset="1" stopColor="#cfcfc8" /></linearGradient>
        <linearGradient id="vs-door" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#fafaf7" /><stop offset="1" stopColor="#e3e3dd" /></linearGradient>
        <radialGradient id="vs-interior" cx=".35" cy=".35" r=".8"><stop offset="0" stopColor="#3a2410" /><stop offset="1" stopColor="#120a04" /></radialGradient>
        <radialGradient id="vs-warm" cx=".45" cy=".45" r=".6"><stop offset="0" stopColor="#ffb45a" stopOpacity=".95" /><stop offset=".55" stopColor="#ff9a3c" stopOpacity=".35" /><stop offset="1" stopColor="#ff8a2a" stopOpacity="0" /></radialGradient>
        <radialGradient id="vs-floor" cx=".5" cy=".5" r=".5"><stop offset="0" stopColor="#ffffff" stopOpacity=".09" /><stop offset="1" stopColor="#ffffff" stopOpacity="0" /></radialGradient>
        <clipPath id="vs-opening"><path d={openingClip} /></clipPath>
        <filter id="vs-key-glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="2.4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        <filter id="vs-seam-glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="1.6" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>

      <g id="vault-stage">
        <ellipse cx={iso(57, 11, -10)[0]} cy={iso(57, 11, -10)[1] + 6} rx="190" ry="54" fill="url(#vs-floor)" />
        {/* Base plate */}
        <g id="plate" className="vs-line">
          <path d={plateFaces.left} fill="url(#vs-side)" />
          <path d={plateFaces.front} fill="#d4d4ce" />
          <g transform={plane.z(0)}><rect x={PLATE.x0} y={PLATE.y0} width={PLATE.x1 - PLATE.x0} height={PLATE.y1 - PLATE.y0} rx="7" fill="url(#vs-top)" /><rect x={PLATE.x0 + 6} y={PLATE.y0 + 6} width={PLATE.x1 - PLATE.x0 - 12} height={PLATE.y1 - PLATE.y0 - 12} rx="4" fill="none" className="vs-faint" /><circle cx={PLATE.x0 + 8} cy={PLATE.y1 - 8} r="1.4" fill="none" /><circle cx={PLATE.x1 - 8} cy={PLATE.y0 + 8} r="1.4" fill="none" /></g>
          <g id="plate-label" transform={plane.z(0)}><rect x="106" y="74" width="16" height="26" rx="1.5" fill="#f4f4f0" />{[80, 85, 90].map(y => <path key={y} d={`M109 ${y + 3}h10`} className="vs-faint" />)}</g>
        </g>
        {/* Rail */}
        <g id="rail" className="vs-line">
          <path d={railFaces.left} fill="#d7d7d1" /><path d={railFaces.front} fill="#cdcdc6" /><path d={railFaces.top} fill="#f1f1ec" />
          <g transform={plane.z(1.6)}>{[104, 112].map(x => <rect key={x} x={x - 0.9} y={RAIL.y0 + 2} width="1.8" height={RAIL.y1 - RAIL.y0 - 4} rx=".9" fill="#e2e2dc" />)}<rect x={RAIL.x0 + 1} y={RAIL.y0 + 1} width={RAIL.x1 - RAIL.x0 - 2} height="5" rx="1" fill="#e9e9e4" /></g>
          <g id="rail-ticks" transform={plane.z(1.6)}>{railTicks.map((y, i) => <path key={y} d={`M${RAIL.x1 - 0.5} ${y}h${i % 4 === 0 ? -2.6 : -1.4}`} className="vs-faint" />)}</g>
        </g>
        {/* Body */}
        <path d={cubeHex} fill="#d6d6d0" className="vs-line" />
        <g id="body-top" transform={plane.z(H)} className="vs-line"><rect x="1" y="1" width="98" height="98" rx="5" fill="url(#vs-top)" /><rect x="7" y="7" width="86" height="86" rx="2.5" fill="none" className="vs-faint" /></g>
        <g className="vs-line">{knob(16, 82)}{knob(82, 16)}</g>
        <g id="body-left" transform={plane.y(100)} className="vs-line">
          <rect x="1" y="1" width="98" height="102" rx="5" fill="url(#vs-left)" />
          <rect x="7" y="7" width="86" height="90" rx="2" fill="none" className="vs-faint" />
          <g id="nameplate"><rect x="16" y="22" width="28" height="17" rx="1.2" fill="#f6f6f2" />{[27, 31, 35].map((y, i) => <path key={y} d={`M20 ${y}h${i === 2 ? 12 : 19}`} className="vs-faint" />)}</g>
          <g id="usb"><rect x="85.5" y="39.5" width="4.6" height="9" rx=".6" fill="#f1f1ed" /><rect x="86.7" y="41" width="2.2" height="2.6" fill="#9c9c95" stroke="none" /></g>
          <g id="keypad"><rect x="81.6" y="49.6" width="12.4" height="30" rx="1.4" fill="#cfcfc8" stroke="none" transform="translate(-1.2 .9)" /><rect x="81.6" y="48" width="12.4" height="30" rx="1.4" fill="#f7f7f3" />
            {Array.from({ length: 12 }, (_, i) => <rect key={i} x={83.6 + (i % 3) * 3.1} y={63 + Math.floor(i / 3) * 3.2} width="2.2" height="2.1" rx=".3" fill="none" className="vs-faint" />)}
          </g>
          <g id="led"><circle id="led-glow" cx="87.8" cy="56.4" r="4.2" fill="rgb(255,77,61)" stroke="none" style={{ filter: "blur(1.6px)" }} /><rect id="led-light" x="85.9" y="55" width="3.8" height="2.8" rx=".4" fill="rgb(255,77,61)" stroke="none" /></g>
          <g id="rivets-left">{rivets(4, 4, 96, 100, 8).map(([u, v], i) => <circle key={i} cx={u} cy={v} r=".55" className="vs-rivet" />)}</g>
        </g>
        <g id="body-front" transform={plane.x(100)} className="vs-line">
          <rect x="1" y="1" width="98" height="102" rx="5" fill="url(#vs-front)" />
          <g id="rivets">{rivets(4, 4, 96, 100, 8).map(([u, v], i) => <circle key={i} cx={u} cy={v} r=".55" className="vs-rivet" />)}</g>
        </g>
        {/* Door frame ring and the opening behind the door */}
        <path id="door-rim" d={cylinderX(100, RING.x1, DOOR.cu, DOOR.cv, RING.outer)} fill="url(#vs-side)" className="vs-line" />
        <g transform={plane.x(RING.x1)} className="vs-line"><circle cx={DOOR.cu} cy={DOOR.cv} r={RING.outer} fill="url(#vs-door)" /><circle cx={DOOR.cu} cy={DOOR.cv} r={RING.outer - 3} fill="none" className="vs-faint" />{Array.from({ length: 24 }, (_, i) => { const a = (i / 24) * Math.PI * 2; return <circle key={i} cx={DOOR.cu + Math.cos(a) * (RING.outer - 5.2)} cy={DOOR.cv + Math.sin(a) * (RING.outer - 5.2)} r=".5" className="vs-rivet" />; })}</g>
        <g id="interior" clipPath="url(#vs-opening)">
          <path d={openingClip} fill="url(#vs-interior)" />
          <g transform={plane.x(BACK_X)}><circle cx={DOOR.cu} cy={DOOR.cv} r={RING.inner + 2} fill="#2a1a0c" stroke="#5a3b1c" strokeWidth=".8" vectorEffect="non-scaling-stroke" /></g>
          <g id="drawers" transform={plane.x(BACK_X + 0.3)}>
            {drawerSlots.map(d => <g key={d.u + "-" + d.v}><rect x={d.u - 7} y={d.v - 5} width="14" height="10" rx=".8" fill="#f1ede4" stroke="#b7a993" strokeWidth=".8" vectorEffect="non-scaling-stroke" /><rect x={d.u - 3} y={d.v - 0.9} width="6" height="1.8" rx=".9" fill="none" stroke="#a89a84" strokeWidth=".8" vectorEffect="non-scaling-stroke" /></g>)}
          </g>
          <g id="keybox-inner" className="vs-line"><path id="kb-in-left" d={k0.inner.left} fill="#ddd8cd" /><path id="kb-in-top" d={k0.inner.top} fill="#f4f1ea" /><path id="kb-in-front" d={k0.inner.front} fill="#ece8df" /></g>
          <g id="interior-glow" style={{ mixBlendMode: "screen" }}><path d={openingClip} fill="url(#vs-warm)" /></g>
        </g>
        {/* Key box pulled out past the face */}
        <g id="keybox" className="vs-line" style={{ display: "none" }}>
          <path id="kb-out-left" fill="url(#vs-side)" /><path id="kb-out-top" fill="#f8f8f4" /><path id="kb-out-front" fill="#ecece6" />
          <g id="kb-keyhole"><circle cx="0" cy="-1.2" r="1.6" fill="none" /><path d="M-.6 .2 L-1.1 3 H1.1 L.6 .2" fill="none" /></g>
        </g>
        {/* The secret key */}
        <g id="key" style={{ opacity: 0 }} filter="url(#vs-key-glow)">
          <g fill="none" stroke="#ffc46e" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke">
            <circle cx="0" cy="-30" r="7.5" /><circle cx="0" cy="-30" r="3" /><path d="M0 -37.5v-2.5M7.5 -30h2.5M0 -22.5v2.4M-7.5 -30h-2.5" />
            <path d="M0 -20.1V0" /><path d="M0 -3h4.2v-2.6M0 -8h3v-2.2M0 -13h4.6" /><path d="M-1.6 -18.5h3.2" />
          </g>
        </g>
        {/* Door assembly: carriage + stem + door slide together along the rail */}
        <g id="door-assembly">
          <g id="door-swing">
            <path d={cylinderX(DOOR.x0, DOOR.x1, DOOR.cu, DOOR.cv, DOOR.r)} fill="url(#vs-side)" className="vs-line" />
            <g id="door-disc" transform={plane.x(DOOR.x1)} className="vs-line">
              <circle cx={DOOR.cu} cy={DOOR.cv} r={DOOR.r} fill="url(#vs-door)" />
              <circle cx={DOOR.cu} cy={DOOR.cv} r={DOOR.r - 4.5} fill="none" className="vs-faint" />
              <circle cx={DOOR.cu} cy={DOOR.cv} r={DOOR.r - 8} fill="none" className="vs-faint" />
              {Array.from({ length: 16 }, (_, i) => { const a = (i / 16) * Math.PI * 2; return <circle key={i} cx={DOOR.cu + Math.cos(a) * (DOOR.r - 2.3)} cy={DOOR.cv + Math.sin(a) * (DOOR.r - 2.3)} r=".5" className="vs-rivet" />; })}
              <g id="spokes">{[0, 120, 240].map(a => <g key={a} transform={`rotate(${a - 90} ${DOOR.cu} ${DOOR.cv})`}><rect x={DOOR.cu + 5} y={DOOR.cv - 1.4} width="16" height="2.8" rx="1.4" fill="#f7f7f3" /><circle cx={DOOR.cu + 22.5} cy={DOOR.cv} r="3.6" fill="#fbfbf8" /><circle cx={DOOR.cu + 22.5} cy={DOOR.cv} r="1.4" fill="none" className="vs-faint" /></g>)}</g>
              <circle cx={DOOR.cu} cy={DOOR.cv} r="8.6" fill="#f3f3ef" />
              <g id="dial"><circle cx={DOOR.cu} cy={DOOR.cv} r="7" fill="#fbfbf8" /><g id="dial-ticks">{Array.from({ length: 40 }, (_, i) => <path key={i} d={`M${DOOR.cu} ${DOOR.cv - 7}v${i % 5 === 0 ? 2 : 1.1}`} transform={`rotate(${i * 9} ${DOOR.cu} ${DOOR.cv})`} className="vs-faint" />)}</g><circle cx={DOOR.cu} cy={DOOR.cv} r="3.2" fill="#ededE8" /></g>
              <path d={`M${DOOR.cu - 1.4} ${DOOR.cv - 10.6} h2.8 l-1.4 2.2z`} fill="#4c4c48" stroke="none" />
            </g>
            <path id="hinge-stem-front" d={stem.front} fill="#e6e6e0" className="vs-line" />
          </g>
          <g id="hinge-stem" className="vs-line"><path d={stem.left} fill="#dcdcd5" /><path d={stem.top} fill="#f4f4f0" /></g>
          <g id="carriage" className="vs-line">
            <path d={carriage.left} fill="url(#vs-side)" /><path d={carriage.top} fill="#f6f6f2" /><path d={carriage.front} fill="#e8e8e2" />
            {[-4.5, 4.5].map(o => <g key={o} transform={plane.x(CARRIAGE.x1 + 0.2)}><circle cx={DOOR.cu + o} cy={H - 4.8} r="3.3" fill="#f7f7f3" /><circle cx={DOOR.cu + o} cy={H - 4.8} r="1.1" fill="none" className="vs-faint" /></g>)}
          </g>
        </g>
        {/* Seam light: sweeps once around the door seam, then contracts to a point */}
        <g id="seam-group"><path id="seam-light" d={seamPath} pathLength={1000} fill="none" stroke="#ffd59a" strokeWidth="1.6" strokeLinecap="round" vectorEffect="non-scaling-stroke" strokeDasharray="160 840" filter="url(#vs-seam-glow)" style={{ opacity: 0 }} /></g>
      </g>
    </svg>
    <div ref={point} className="vault-point" />
    {caption && <p className="vault-caption mono">{caption}</p>}
  </div>;
}
