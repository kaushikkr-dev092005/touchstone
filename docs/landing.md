# Landing page: cinematic intro, black hole and vault transition

Code lives in `apps/web/src/cinematic/`:

| File | Role |
|---|---|
| `timeline.ts` | `TIMELINE`: every duration (intro, Dashboard transition, return path, skip ramp) |
| `Director.tsx` | IntroController + RouteTransitionProvider: one GSAP master timeline at a time, skip, debug scrubber, session logic |
| `vault/VaultSequence.tsx` | `<VaultSequence variant="intro" \| "dashboard" />`: layered isometric SVG and its timeline |
| `vault/geometry.ts` | Isometric projection helpers, face-plane matrices and layout constants |
| `blackhole/BlackHole.tsx` | Persistent full-viewport canvas plus the `holeHandle` API |
| `blackhole/renderer.ts` | WebGL2 renderer: `FRAMING` constants, quality governor, bloom chain |
| `blackhole/shaders.ts` | GLSL: ray-marched scene, particles, bloom, composite |

`public/intro-init.js` picks the intro mode before first paint (`full`, `returning` or `reduced`) and
writes it to `<html data-intro>`. It is an external file because the CSP is `script-src 'self'`.
CSS keeps every `[data-reveal]` element at opacity 0 until the mode becomes `done`, so the hero DOM
exists from first paint (for SEO) without flashing. The current state is mirrored to
`<html data-intro-state>`.

## Timeline (`TIMELINE`)

- `intro.black`: pure black lead-in (0.7s).
- `intro.vault`: `safeIn, locked, unlock, doorOpen, keyReveal, keyStow, doorClose, safeOut`.
  The vault timeline places every sub-motion as a fraction of its phase. Change a phase length and the
  whole phase scales with it.
- `intro.igniteOverlap`: `holeIgnite` starts this long before `safeOut` ends (0.3s, so it begins at 8.5s).
- `intro.holeIgnite`, `intro.heroOverlap`, `intro.heroIn`: ignition and hero reveal (finishes at about 11.2s).
- `dashboard.*`: the compressed vault for Open Dashboard (about 5.5s). The route is committed at the
  vault's `keyStow` label while the black cover is fully opaque. `seamExpand` turns the final point
  into the ledger's top-edge light, and `ledgerIn` staggers the rows.
- `returning.*`: returning visitors and the way back from the ledger (ignite + hero only).
- `reduced.crossfade`: the reduced-motion crossfade (600ms over one static frame).
- `skipTimeScale`, `skipRamp`: Skip / Esc ramps `timeScale` up to 14 over 0.45s instead of jumping.

`introSchedule()` derives the absolute start of every state from these values.

Query flags: `?intro=force` always plays the full intro. `?debug=1` shows a scrubber, the state label,
the quality level and the frame time, and exposes `window.__hole`. The intro plays once per session
(`sessionStorage["ts-intro"]`).

## Black hole

The fragment shader casts one ray per pixel from a camera at `CAM_DIST` (40 rs) and bends it with
`a = -1.5 h² r̂ / r⁴`, using adaptive steps (`dt ∝ r`). Rays with impact parameter `b > 18` take a
weak-field shortcut. Disk crossings between `R_IN` and `R_OUT` are composited front to back, so the
far side is lensed over the shadow and a secondary image appears beneath it. The disk uses a
Shakura–Sunyaev temperature profile, Doppler beaming `g³` with gravitational redshift, and fbm
streaks and dust lanes in `(log r, φ − Ω(r)t)`. The photon ring is drawn exactly at
`b = 3√3/2`, measured in scene pixels, so it stays the sharpest feature at any size. Escaping rays
sample a starfield by direction, which makes the stars lensed. GPU points on elliptical orbits
use a point-lens image and a shadow test. Post-processing is a 13-tap threshold downsample (0.6),
tent upsample, chromatic fringe at the ring, ACES, vignette and grain.

Uniforms driven from JS (`holeHandle.state`, tweened by GSAP):

| Field | Meaning |
|---|---|
| `ignite` (`uIgnite`) | 0→1. The first `IGNITE_SPLIT` blooms the point in place into a small black hole; the rest grows and raises it into the framing. Ring, then disk (inner → outer), then dust. |
| `intensity` (`uIntensity`) | Overall brightness. At 0 the canvas hides and the render loop stops. |
| `point` | Brightness of the handed-over point of light. |
| `bloomBoost` | Extra bloom (peaks at +0.6 during ignition, settles with a slight overshoot). |

`uTime` and `uMouse` (lerped, ±2° azimuth / ±1.5° elevation, disabled on touch) are internal.
Scrolling raises the hole and dims it. The loop also stops when the tab is hidden.

### Tuning the framing (`FRAMING` in `renderer.ts`)

- `HOLE_SCALE`: shadow radius as a fraction of viewport width (clamped by `HOLE_RADIUS_MIN/MAX`, in
  viewport heights). Larger values flatten the arc.
- `HOLE_DIP`: how far the lowest point of the shadow dips below the top edge.
- `HOLE_POS_X`: horizontal offset of the hole centre.
- `DISK_TILT` (camera elevation, 8° ≈ 82° inclination), `DISK_ROLL`, `R_IN`, `R_OUT`, `DOPPLER`.
- `TEXT_FADE`: distance below the ring over which disk light grades to black, which keeps the
  headline readable. It is capped at `0.36 × radius` on narrow screens. Stars and dust are not faded.
- `BODY`: the tiny distant body for scale.

### Performance

The scene renders at `QUALITY[level].scale` of a canvas whose DPR is capped at 1.5, and is upscaled
in the composite pass. When the steady-state frame time stays above 20ms for 1s, the governor drops
a level: resolution first, then march steps, then particle count. Ignition and transitions are not
judged. Touch or narrow screens start at level 2. Software rasterizers (SwiftShader/llvmpipe), a
missing WebGL2 or a lost context switch to a static CSS horizon (`.hole-fallback`).

Measured with the production build on this laptop's Intel UHD iGPU (ANGLE D3D11, 1440×900, headless
Chromium): 60fps at rest, settling at level 1. After four Dashboard round trips the DOM node count
was unchanged at 162 and the JS heap levelled off at about 5.1 MB.

## Vault

The vault is drawn in world units: the body is a 100×100×104 cube and the door face is the plane
x = 100. Each face is drawn in 2D inside an SVG `matrix()` (`plane.x/y/z`) that maps it onto the
isometric plane. Circles therefore become true 0.577 ellipses, and the dial and handle rotate
correctly within the door plane. Cylinder silhouettes use the analytic tangent points (−45°/135°).
Named groups: `#plate #plate-label #rail #rail-ticks #body-top #body-left #nameplate #keypad #led
#usb #body-front #rivets #door-rim #interior #drawers #keybox #key #door-assembly #door-disc #spokes
#dial #dial-ticks #hinge-stem #carriage #seam-light`.

Choreography: the door detaches onto the rail carriage and slides along −y by `DOOR_TRAVEL`, with a
slight swing. The key box extrudes out of the ring opening, and the amber key rises with a 15° turn.
On close, a seam pulse runs around the door, then contracts into one point. The vault exists only
inside the Director's overlay layer. It is unmounted 0.6s into ignition (its timeline is killed
on unmount) and is never part of the resting landing page.

## Copy boundaries

The suggested headline ("Pay for inference that passes the test") and "exactly-once ledger" were not
used. The repository records that rejected answers can still cost money (README) and that it does not
prove exactly-once effects on external rails (`docs/LIMITATIONS.md`). The landing says "Buy inference.
Prove it passes." and describes local idempotency, reservation, recovery and hash-chained audit
instead. The ledger preview is labelled SAMPLE DATA. Recorded numbers remain in the ledger view.
