import { COMPOSITE_FS, DOWN_FS, FULLSCREEN_VS, PARTICLE_FS, PARTICLE_VS, SCENE_FS, UP_FS } from "./shaders";

/** Framing constants. Tune the composition here (see docs/landing.md). */
export const FRAMING = {
  /** Horizontal hole centre offset, in viewport heights from centre. */
  HOLE_POS_X: 0,
  /** Shadow radius as a fraction of viewport width (clamped by HOLE_RADIUS_MIN/MAX, in heights). */
  HOLE_SCALE: 0.8,
  HOLE_RADIUS_MIN: 0.46,
  HOLE_RADIUS_MAX: 2.3,
  /** How far the lowest point of the shadow dips below the top edge, in viewport heights. */
  HOLE_DIP: 0.17,
  /** Disk light fades to black over this distance below the ring (viewport heights). */
  TEXT_FADE: 0.34,
  /** Ignition: share of the ignite progress spent blooming in place, and the radius reached there. */
  IGNITE_SPLIT: 0.38,
  IGNITE_SMALL_RADIUS: 0.075,
  /** Camera elevation above the disk plane (radians). 8° ≈ 82° inclination. */
  DISK_TILT: (8 * Math.PI) / 180,
  /** Screen roll of the whole system (radians). */
  DISK_ROLL: (-2.5 * Math.PI) / 180,
  CAM_DIST: 40,
  R_IN: 2.6,
  R_OUT: 12,
  DOPPLER: 0.85,
  /** Tiny distant body, relative to viewport (x as fraction of half-width, y in heights from centre). */
  BODY: { x: 0.74, y: 0.08, r: 0.0042 },
};

const BC = 2.598076;

type Level = { scale: number; steps: number; particles: number };
export const QUALITY: Level[] = [
  { scale: 0.72, steps: 96, particles: 4500 },
  { scale: 0.6, steps: 96, particles: 4500 },
  { scale: 0.52, steps: 80, particles: 3000 },
  { scale: 0.45, steps: 64, particles: 2000 },
  { scale: 0.38, steps: 48, particles: 1000 },
];

export type HoleState = {
  /** 0 → 1 ignition: point → ring → disk → dust. */
  ignite: number;
  /** Overall brightness. 0 stops the render loop. */
  intensity: number;
  /** Extra brightness of the handed-over point of light. */
  point: number;
  /** Additional bloom multiplier (ignite overshoot). */
  bloomBoost: number;
};

type FBO = { fb: WebGLFramebuffer; tex: WebGLTexture; w: number; h: number };

const ease = {
  inOut: (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  clamp: (t: number) => Math.min(1, Math.max(0, t)),
};

function compile(gl: WebGL2RenderingContext, vs: string, fs: string) {
  const make = (type: number, src: string) => {
    const s = gl.createShader(type)!;
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader compile failed");
    return s;
  };
  const p = gl.createProgram()!, v = make(gl.VERTEX_SHADER, vs), f = make(gl.FRAGMENT_SHADER, fs);
  gl.attachShader(p, v); gl.attachShader(p, f); gl.linkProgram(p);
  gl.deleteShader(v); gl.deleteShader(f);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) || "link failed");
  const cache = new Map<string, WebGLUniformLocation | null>();
  const u = (n: string) => { if (!cache.has(n)) cache.set(n, gl.getUniformLocation(p, n)); return cache.get(n)!; };
  return { p, u };
}

export class BlackHoleRenderer {
  readonly state: HoleState;
  /** Viewport-pixel position of the point the vault collapses into. */
  startPoint = { x: 0.5, y: 0.46 };
  scroll = 0;
  level = 0;
  onLevelChange?: (level: number) => void;
  private gl: WebGL2RenderingContext;
  private hdr = true;
  private scene!: ReturnType<typeof compile>;
  private down!: ReturnType<typeof compile>;
  private up!: ReturnType<typeof compile>;
  private comp!: ReturnType<typeof compile>;
  private part!: ReturnType<typeof compile>;
  private vao!: WebGLVertexArrayObject;
  private partVao!: WebGLVertexArrayObject;
  private partBuf!: WebGLBuffer;
  private sceneFbo: FBO | null = null;
  private mips: FBO[] = [];
  private raf = 0;
  private running = false;
  private last = 0;
  private t0 = performance.now();
  private slowTime = 0;
  private fastTime = 0;
  private mouse = { x: 0, y: 0, tx: 0, ty: 0 };
  private cssW = 1;
  private cssH = 1;
  private disposed = false;
  private paused = false;
  readonly mobile: boolean;
  frameMs = 16.7;

  constructor(private canvas: HTMLCanvasElement, opts: { mobile: boolean; state: HoleState }) {
    this.state = opts.state;
    const gl = canvas.getContext("webgl2", { antialias: false, alpha: false, depth: false, stencil: false, premultipliedAlpha: false, powerPreference: "high-performance" });
    if (!gl) throw new Error("WebGL2 unavailable");
    // Software rasterizers cannot ray-march at interactive rates; use the static fallback instead.
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    const name = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "";
    if (/swiftshader|llvmpipe|softpipe|software|basic render/i.test(name)) throw new Error("Software WebGL renderer: " + name);
    this.gl = gl;
    this.mobile = opts.mobile;
    this.level = opts.mobile ? 2 : 0;
    this.hdr = !!gl.getExtension("EXT_color_buffer_float");
    this.scene = compile(gl, FULLSCREEN_VS, SCENE_FS);
    this.down = compile(gl, FULLSCREEN_VS, DOWN_FS);
    this.up = compile(gl, FULLSCREEN_VS, UP_FS);
    this.comp = compile(gl, FULLSCREEN_VS, COMPOSITE_FS);
    this.part = compile(gl, PARTICLE_VS, PARTICLE_FS);
    this.vao = gl.createVertexArray()!;
    this.buildParticles();
    this.resize();
  }

  private buildParticles() {
    const gl = this.gl, n = QUALITY[0].particles, data = new Float32Array(n * 8);
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < n; i++) {
      const o = i * 8, wide = rnd() < 0.18;
      data[o] = 3.2 + Math.pow(rnd(), 1.6) * 17;                 // orbit radius
      data[o + 1] = rnd() * 0.12;                                 // eccentricity
      data[o + 2] = rnd() * Math.PI * 2;                          // phase
      data[o + 3] = 0.25 + Math.pow(rnd(), 3) * 1.6;              // brightness
      data[o + 4] = (rnd() - 0.5) * (wide ? 0.5 : 0.07);          // inclination
      data[o + 5] = rnd() * Math.PI * 2;                          // node
      data[o + 6] = 0.6 + Math.pow(rnd(), 4) * 2.8;               // size
      data[o + 7] = rnd();                                        // seed
    }
    this.partVao = gl.createVertexArray()!;
    gl.bindVertexArray(this.partVao);
    this.partBuf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.partBuf);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 4, gl.FLOAT, false, 32, 0);
    gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 4, gl.FLOAT, false, 32, 16);
    gl.bindVertexArray(null);
  }

  private makeFbo(w: number, h: number): FBO {
    const gl = this.gl, tex = gl.createTexture()!, fb = gl.createFramebuffer()!;
    gl.bindTexture(gl.TEXTURE_2D, tex);
    if (this.hdr) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, w, h, 0, gl.RGBA, gl.HALF_FLOAT, null);
    else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE && this.hdr) {
      gl.deleteFramebuffer(fb); gl.deleteTexture(tex); this.hdr = false; return this.makeFbo(w, h);
    }
    return { fb, tex, w, h };
  }

  private freeTargets() {
    const gl = this.gl;
    for (const f of [this.sceneFbo, ...this.mips]) if (f) { gl.deleteFramebuffer(f.fb); gl.deleteTexture(f.tex); }
    this.sceneFbo = null; this.mips = [];
  }

  resize() {
    if (this.disposed) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    this.cssW = Math.max(1, window.innerWidth); this.cssH = Math.max(1, window.innerHeight);
    this.canvas.width = Math.round(this.cssW * dpr); this.canvas.height = Math.round(this.cssH * dpr);
    this.freeTargets();
    const q = QUALITY[this.level];
    const sw = Math.max(64, Math.round(this.canvas.width * q.scale)), sh = Math.max(64, Math.round(this.canvas.height * q.scale));
    this.sceneFbo = this.makeFbo(sw, sh);
    let w = sw >> 1, h = sh >> 1;
    for (let i = 0; i < 5 && w >= 8 && h >= 8; i++) { this.mips.push(this.makeFbo(w, h)); w >>= 1; h >>= 1; }
    if (!this.running) this.renderFrame(this.now());
  }

  setMouse(nx: number, ny: number) { if (!this.mobile) { this.mouse.tx = nx; this.mouse.ty = ny; } }
  setPaused(paused: boolean) { this.paused = paused; if (!paused) this.wake(); }

  /** Start the loop if anything is visible. Cheap to call often (e.g. from tween onUpdate). */
  wake() {
    if (this.disposed || this.running || this.paused || document.hidden || this.effectiveIntensity() <= 0) return;
    this.running = true; this.last = performance.now();
    this.raf = requestAnimationFrame(this.tick);
  }

  /** Render exactly one frame (reduced motion / static). */
  renderOnce() { this.renderFrame(this.now()); }

  private now() { return (performance.now() - this.t0) / 1000; }
  private effectiveIntensity() { return this.state.intensity * (1 - smooth(0.15, 1.05, this.scroll)); }

  private tick = (ts: number) => {
    if (this.disposed) return;
    const dt = ts - this.last; this.last = ts;
    this.frameMs = this.frameMs * 0.9 + dt * 0.1;
    this.govern(dt);
    this.renderFrame(this.now());
    if (this.paused || document.hidden || this.effectiveIntensity() <= 0) { this.running = false; return; }
    this.raf = requestAnimationFrame(this.tick);
  };

  /** Adaptive quality: >20ms average for 1s drops a level (resolution, then steps, then particles). */
  private govern(dt: number) {
    dt = Math.min(dt, 1000); // `last` is reset on wake/resume, so long gaps here are real slow frames
    // Only steady-state frames count: ignition flights and DOM transitions are short, deliberate spikes,
    // and a level dropped for them could never come back (vsync hides headroom).
    if (this.state.ignite < 1 || this.state.intensity < 1) { this.slowTime = 0; return; }
    if (this.frameMs > 20) { this.slowTime += dt; this.fastTime = 0; } else { this.slowTime = 0; this.fastTime += dt; }
    if (this.slowTime > 1000 && this.level < QUALITY.length - 1) {
      this.level++; this.slowTime = 0; this.frameMs = 16.7; this.resize(); this.onLevelChange?.(this.level);
    }
  }

  private geometry() {
    const aspect = this.cssW / this.cssH;
    const g = this.state.ignite;
    const R = Math.min(FRAMING.HOLE_RADIUS_MAX, Math.max(FRAMING.HOLE_RADIUS_MIN, FRAMING.HOLE_SCALE * aspect));
    const finalPos = { x: FRAMING.HOLE_POS_X, y: 0.5 - FRAMING.HOLE_DIP + R + this.scroll * 0.35 };
    const start = { x: (this.startPoint.x - 0.5) * aspect, y: 0.5 - this.startPoint.y };
    // Phase A (g 0 → IGNITE_SPLIT): the point blooms in place into a small, complete black hole (power4.out).
    // Phase B (g IGNITE_SPLIT → 1): it grows and rises into the final framing while the headline fade engages.
    const split = FRAMING.IGNITE_SPLIT;
    const a = ease.clamp(g / split), b = ease.clamp((g - split) / (1 - split));
    const bloom = 1 - Math.pow(1 - a, 4);
    const small = FRAMING.IGNITE_SMALL_RADIUS;
    const growB = Math.pow(b, 2.2);
    const move = ease.inOut(b);
    const radius = Math.max(0.003, b > 0 ? small + (R - small) * growB : small * bloom);
    const pos = { x: start.x + (finalPos.x - start.x) * move, y: start.y + (finalPos.y - start.y) * move };
    const textFade = Math.min(FRAMING.TEXT_FADE, R * 0.36);       // narrower screens: tighter fade
    const fadeRatio = 5 + (textFade / R - 5) * smooth(0.25, 0.85, b);
    const fade = radius * fadeRatio;
    const k = Math.tan(Math.asin(BC / FRAMING.CAM_DIST)) / radius;
    const kFinal = Math.tan(Math.asin(BC / FRAMING.CAM_DIST)) / R;
    return { aspect, R, radius, pos, start, k, kFinal, fade };
  }

  private renderFrame(time: number) {
    const gl = this.gl, s = this.state, sf = this.sceneFbo;
    if (!sf || this.disposed) return;
    const m = this.mouse; m.x += (m.tx - m.x) * 0.04; m.y += (m.ty - m.y) * 0.04;
    const geo = this.geometry(), q = QUALITY[this.level];
    const hdrScale = this.hdr ? 1 : 0.25;
    const inten = this.effectiveIntensity();
    gl.disable(gl.DEPTH_TEST);
    gl.bindVertexArray(this.vao);

    // 1. Ray-marched scene.
    gl.bindFramebuffer(gl.FRAMEBUFFER, sf.fb); gl.viewport(0, 0, sf.w, sf.h); gl.disable(gl.BLEND);
    const S = this.scene; gl.useProgram(S.p);
    gl.uniform2f(S.u("uRes"), sf.w, sf.h);
    gl.uniform1f(S.u("uTime"), time); gl.uniform1f(S.u("uIgnite"), s.ignite); gl.uniform1f(S.u("uIntensity"), inten);
    gl.uniform2f(S.u("uMouse"), m.x, m.y);
    gl.uniform2f(S.u("uHole"), geo.pos.x, geo.pos.y); gl.uniform1f(S.u("uRadius"), geo.radius); gl.uniform1f(S.u("uK"), geo.k);
    gl.uniform1f(S.u("uCamDist"), FRAMING.CAM_DIST); gl.uniform1f(S.u("uTilt"), FRAMING.DISK_TILT); gl.uniform1f(S.u("uRoll"), FRAMING.DISK_ROLL);
    gl.uniform1f(S.u("uFade"), geo.fade); gl.uniform1f(S.u("uRin"), FRAMING.R_IN); gl.uniform1f(S.u("uRout"), FRAMING.R_OUT); gl.uniform1f(S.u("uDoppler"), FRAMING.DOPPLER);
    gl.uniform1i(S.u("uSteps"), q.steps);
    gl.uniform1f(S.u("uStarScale"), this.cssH / (geo.kFinal * 11));
    gl.uniform1f(S.u("uHdr"), hdrScale); gl.uniform1f(S.u("uPoint"), s.point);
    gl.uniform2f(S.u("uPointPos"), geo.start.x, geo.start.y);
    gl.uniform2f(S.u("uBody"), FRAMING.BODY.x * geo.aspect * 0.5, FRAMING.BODY.y + this.scroll * 0.2); gl.uniform1f(S.u("uBodyR"), FRAMING.BODY.r);
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    // 2. Dust particles, additive, same camera and lensing approximation.
    const dust = smooth(0.45, 1, s.ignite);
    if (dust > 0) {
      const P = this.part; gl.useProgram(P.p);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
      const e = FRAMING.DISK_TILT + m.y * 0.026, az = m.x * 0.035 + Math.sin(time * 0.05) * 0.012, D = FRAMING.CAM_DIST;
      const cam = [D * Math.sin(az) * Math.cos(e), D * Math.sin(e), D * Math.cos(az) * Math.cos(e)];
      const f = cam.map(c => -c / D);
      const rt = norm([-f[2], 0, f[0]]);              // cross(f, up)
      const upv = [rt[1] * f[2] - rt[2] * f[1], rt[2] * f[0] - rt[0] * f[2], rt[0] * f[1] - rt[1] * f[0]];
      gl.uniform3fv(P.u("uCam"), cam); gl.uniform3fv(P.u("uF"), f); gl.uniform3fv(P.u("uRt"), rt); gl.uniform3fv(P.u("uUp"), upv);
      gl.uniform2f(P.u("uHole"), geo.pos.x, geo.pos.y); gl.uniform2f(P.u("uRes"), sf.w, sf.h);
      gl.uniform1f(P.u("uK"), geo.k); gl.uniform1f(P.u("uRoll"), FRAMING.DISK_ROLL); gl.uniform1f(P.u("uTime"), time);
      gl.uniform1f(P.u("uDust"), dust); gl.uniform1f(P.u("uCamDist"), D); gl.uniform1f(P.u("uPx"), sf.h / 700);
      gl.uniform1f(P.u("uHdr"), hdrScale);
      gl.bindVertexArray(this.partVao);
      gl.drawArrays(gl.POINTS, 0, q.particles);
      gl.bindVertexArray(this.vao);
      gl.disable(gl.BLEND);
    }

    // 3. Bloom: thresholded 13-tap downsample chain, tent upsample back up.
    const D2 = this.down; gl.useProgram(D2.p);
    let src: FBO = sf;
    this.mips.forEach((dst, i) => {
      gl.bindFramebuffer(gl.FRAMEBUFFER, dst.fb); gl.viewport(0, 0, dst.w, dst.h);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, src.tex);
      gl.uniform1i(D2.u("uTex"), 0); gl.uniform2f(D2.u("uTexel"), 1 / src.w, 1 / src.h);
      gl.uniform1f(D2.u("uThreshold"), 0.6 * hdrScale); gl.uniform1i(D2.u("uPrefilter"), i === 0 ? 1 : 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      src = dst;
    });
    const U = this.up; gl.useProgram(U.p);
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
    for (let i = this.mips.length - 2; i >= 0; i--) {
      const dst = this.mips[i], from = this.mips[i + 1];
      gl.bindFramebuffer(gl.FRAMEBUFFER, dst.fb); gl.viewport(0, 0, dst.w, dst.h);
      gl.bindTexture(gl.TEXTURE_2D, from.tex);
      gl.uniform1i(U.u("uTex"), 0); gl.uniform2f(U.u("uTexel"), 1 / from.w, 1 / from.h);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
    gl.disable(gl.BLEND);

    // 4. Composite: fringe, bloom, ACES, vignette, grain.
    gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    const C = this.comp; gl.useProgram(C.p);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, sf.tex);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.mips[0]?.tex ?? sf.tex);
    gl.uniform1i(C.u("uScene"), 0); gl.uniform1i(C.u("uBloom"), 1);
    gl.uniform2f(C.u("uRes"), this.canvas.width, this.canvas.height);
    gl.uniform2f(C.u("uHole"), geo.pos.x, geo.pos.y); gl.uniform1f(C.u("uRadius"), geo.radius);
    gl.uniform1f(C.u("uBloomStr"), 0.6 * (1 + s.bloomBoost)); gl.uniform1f(C.u("uIntensity"), inten);
    gl.uniform1f(C.u("uTime"), time); gl.uniform1f(C.u("uHdrInv"), 1 / hdrScale);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.activeTexture(gl.TEXTURE0);
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true; cancelAnimationFrame(this.raf); this.running = false;
    const gl = this.gl;
    this.freeTargets();
    for (const p of [this.scene, this.down, this.up, this.comp, this.part]) gl.deleteProgram(p.p);
    gl.deleteBuffer(this.partBuf); gl.deleteVertexArray(this.vao); gl.deleteVertexArray(this.partVao);
  }
}

function smooth(a: number, b: number, x: number) { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); }
function norm(v: number[]) { const l = Math.hypot(v[0], v[1], v[2]) || 1; return v.map(c => c / l); }
