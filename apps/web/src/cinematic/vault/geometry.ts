// Isometric construction for the vault. World axes: x → screen (cos30, sin30), y → (−cos30, sin30), z up.
// Body occupies x,y ∈ [0,100], z ∈ [0,104]. The door face is the plane x = 100.
// Face-plane local coordinates for x-planes: u = 100 − y (rightwards), v = 104 − z (downwards).

export const C30 = Math.cos(Math.PI / 6), S30 = 0.5;
export const H = 104;

export const iso = (x: number, y: number, z: number): [number, number] => [C30 * (x - y), S30 * (x + y) - z];
const f = (n: number) => +n.toFixed(2);
export const pt = (p: [number, number]) => f(p[0]) + " " + f(p[1]);
export const poly = (ps: [number, number][]) => "M" + ps.map(pt).join("L") + "Z";

/** SVG matrix mapping 2D drawing coords onto each isometric plane (circles become 0.577 ellipses). */
export const plane = {
  x: (X: number) => `matrix(${C30} ${-S30} 0 1 ${f(C30 * (X - 100))} ${f(S30 * (X + 100) - H)})`,
  y: (Y: number) => `matrix(${C30} ${S30} 0 1 ${f(-C30 * Y)} ${f(S30 * Y - H)})`,
  z: (Z: number) => `matrix(${C30} ${S30} ${-C30} ${S30} 0 ${f(-Z)})`,
};

/** Screen position of a point on an x-plane given local (u, v). */
export const onX = (X: number, u: number, v: number) => iso(X, 100 - u, H - v);

/** Sampled screen-space ellipse of a circle on an x-plane. */
export function ellipseX(X: number, cu: number, cv: number, r: number, n = 72) {
  const ps: [number, number][] = [];
  for (let i = 0; i < n; i++) { const t = (i / n) * Math.PI * 2; ps.push(onX(X, cu + r * Math.cos(t), cv + r * Math.sin(t))); }
  return poly(ps);
}

/**
 * Silhouette of a cylinder whose axis is the world x direction (a disc of radius r from X0 to X1).
 * Tangent points sit at t = −45° and 135° for this projection.
 */
export function cylinderX(X0: number, X1: number, cu: number, cv: number, r: number, n = 36) {
  const ps: [number, number][] = [];
  const a = -Math.PI / 4;
  for (let i = 0; i <= n; i++) { const t = a + (i / n) * Math.PI; ps.push(onX(X1, cu + r * Math.cos(t), cv + r * Math.sin(t))); }
  for (let i = 0; i <= n; i++) { const t = a + Math.PI + (i / n) * Math.PI; ps.push(onX(X0, cu + r * Math.cos(t), cv + r * Math.sin(t))); }
  return poly(ps);
}

/** Axis-aligned box faces visible in this projection (+x, +y, +z). */
export function box(x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) {
  return {
    top: poly([iso(x0, y0, z1), iso(x1, y0, z1), iso(x1, y1, z1), iso(x0, y1, z1)]),
    left: poly([iso(x0, y1, z1), iso(x1, y1, z1), iso(x1, y1, z0), iso(x0, y1, z0)]),
    front: poly([iso(x1, y1, z1), iso(x1, y0, z1), iso(x1, y0, z0), iso(x1, y1, z0)]),
  };
}

// --- Layout constants (world units) ---
export const DOOR = { cu: 52, cv: 50, r: 36, x0: 100, x1: 108 };
export const RING = { outer: 41, inner: 30.5, x1: 102 };
export const BACK_X = 86;                         // drawer wall depth inside the opening
export const KEYBOX = { u0: 45, u1: 59, v0: 45, v1: 55, out: 38 };
export const PLATE = { x0: -14, x1: 128, y0: -92, y1: 114, z0: -10 };
export const RAIL = { x0: 101, x1: 115, y0: -84, y1: 64 };
export const CARRIAGE = { x0: 102.5, x1: 113.5, z0: 1.5, z1: 9.5, half: 8 };
/** Door travel along −y when opened (world units). */
export const DOOR_TRAVEL = 98;

export const doorCenter = () => onX(DOOR.x1, DOOR.cu, DOOR.cv);

/** Keybox faces for a given pull length; inner part (x < 100) and outer part (x ≥ 100). */
export function keyboxFaces(pull: number) {
  const y0 = 100 - KEYBOX.u1, y1 = 100 - KEYBOX.u0, z0 = H - KEYBOX.v1, z1 = H - KEYBOX.v0;
  const xf = BACK_X + 0.5 + pull;
  const inner = box(BACK_X, Math.min(xf, 100), y0, y1, z0, z1);
  const outer = xf > 100.2 ? box(100, xf, y0, y1, z0, z1) : null;
  return { inner, outer, xf, y0, y1, z0, z1 };
}

/** Rivet dots along a rectangle (local plane coords). */
export function rivets(u0: number, v0: number, u1: number, v1: number, step: number) {
  const out: [number, number][] = [];
  for (let u = u0; u <= u1 + 0.01; u += step) { out.push([u, v0], [u, v1]); }
  for (let v = v0 + step; v < v1 - 0.01; v += step) { out.push([u0, v], [u1, v]); }
  return out;
}

/** viewBox covering the vault in both closed and open states, plus the key's rise. */
export const VIEWBOX = { x: -122, y: -128, w: 316, h: 268 };
