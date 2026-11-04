# Touchstone cinematic integration

The implementation extends the existing stdlib dashboard. It adds no runtime dependencies, CDN requests, build framework, external HDR environment, or downloaded 3D assets. `index.html` remains the complete runtime page. Editable sources are `cinematic.js` and `cinematic.css`; regenerate the inline blocks with:

```bash
python tools/build_dashboard_effects.py
python -m touchstone serve
```

These commands also work in PowerShell. The custom implementation prompt is in [CINEMATIC_BUILD_PROMPT.md](CINEMATIC_BUILD_PROMPT.md).

## Effects and financial meaning

- **Assay track:** dark glass, mint pad flood, three expanding perspective rings, vertical dashes, brightened glyph/rim and downstream illumination. £/€/$/¥/₿ are decorative currency glyphs, not token transfers. Ambient inspection is DEMO. A successful mock demo start queues exactly three visual passes. Readiness checkmarks continue to describe saved account/provider evidence; the animation does not manufacture successful integration checks.
- **Component interactions:** vanilla ports of Magic UI's moving gradient band, click-local button ripple, head/tail meteors and concentric ripple. The proof word and existing evidence/Ledger headings retain their original typography. Replay works with both the button and `L`. Band colours are adjusted to the requested gold palette; underlying text remains present for contrast.
- **Specimen:** a 400vh pinned explanation with four DOM captions. Twin polished rings grow curved tapering tendrils, become clay with a graph, then morph into a faceted ore surface. The graph uses current local ledger provider/price/score/receipt fields and explicitly says SIMULATED/MOCK. Missing scores stay unrecorded. No run means no invented provider values. Graph anchors follow projected specimen tips.
- **Wipe:** reversible edge metal, a mottled dark interior, reflective meniscus, layout-derived rounded-rectangle silhouette and an L bracket. The flash is bounded to approximately 160ms, including when scroll stops inside its trigger band. Reduced motion removes the wipe/flash.
- **Ledger gateway:** a single scroll-smoothed `uGlow` controls ember accents, centre-out limb ignition, atmosphere, domain-warped cloud texture, photon edge and grain. Copy stays over the black area. Scrolling back dims it. The next CTA opens the existing working Ledger.

`?cinematic=1` plays the sequence automatically with recording hints/cursor hidden. Escape stops it. Cinematic playback sends no POST and does not run a financial demo. `?quality=low` is an explicit reduced-resolution option; full visual detail is the default.

## How quality stays lightweight

The specimen uses one indexed procedural mesh: 31,816 vertices / 60,672 triangles, generated once, with vertex deformation and precomputed ore targets/normals. This replaces the initial per-pixel SDF raymarch. Vertex buffers and indices total approximately 1.5 MB; no mesh file is downloaded. The ore adds 384 instanced surface shards. Studio reflections are analytic softbox strips, with warm thin-film edges, clear highlights and procedural microfacets; there is no HDR texture or environment-map download.

Only one WebGL canvas is active. Ordinary specimen frames use its mesh/shard passes; the full-screen shader runs only for the wipe or gateway. Shaders compile lazily on first scene entry. Pixel ratio is capped at 1.5. Frame loops stop off-screen and when hidden. Static geometry, instance buffers and scratch arrays are reused. Pointer movement eases to a maximum of about six degrees. The embedded WebP fallback is pre-rendered from the actual specimen and includes no DOM text.

Idle motion is capped at 30fps, matching the recordings' 30fps cadence; interaction can render at 60fps. This reduces idle work while retaining the same geometry, resolution and materials. The watchdog records missed frame budgets; it does not silently remove effects or reduce default visual quality. An explicitly selected low mode is labelled in diagnostic results. The saved performance report states the actual browser/GPU, viewport and quality. It is not an RTX 3050 + llama.cpp qualification.

## Tuning

Change the tokens at the top of `apps/dashboard/cinematic.css`, then run the build command:

| Token | Default | Controls |
|---|---|---|
| `--assay-glow` | `#97f6d0` | Mint pad, rim, lane and beam light |
| `--gold` | Existing site token | Brand type and UI |
| `--specimen-tint` | `#d8b982` | Warm chrome reflections |
| `--assay-cadence` | `1.217` | Seconds between inspection passes |
| `--assay-flare` | `.367` | Beam flare width in seconds |
| `--assay-intensity` | `1` | Pad light strength |
| `--specimen-growth` | `1` | Tendril growth amount |
| `--specimen-growth-speed` | `1` | Scroll response smoothing speed |
| `--specimen-drip` | `.32` | Downward bias |
| `--transition-duration` | `4.2` | Timed wipe duration |
| `--effect-quality` | `1` | Default resolution/detail, full by default |
| `--idle-fps` / `--active-fps` | `30` / `60` | Frame-rate caps |

Material/growth/clay/ore keyframes live together in `TouchstoneCinema.states` in the source. They do not authorize payments or classify model answers.

## References and attribution

The user-supplied conveyor recording is 10.667s at 30fps, 636×380. The second recording is 38.133s at 30fps, 1272×688. Source frames were extracted locally with OpenCV/Pillow; source videos are not bundled into the site. Conveyor beam peaks were measured from a fixed upper-column region and a five-frame moving average. Inter-peak median is 1.217s; brightness half-peak median is 0.367s. See the saved [reference analysis](evidence/cinematic/reference-analysis.json).

Magic UI source was read from the official registry:

- [Meteors](https://magicui.design/r/meteors.json)
- [DiaTextReveal](https://magicui.design/r/dia-text-reveal.json)
- [RippleButton](https://magicui.design/r/ripple-button.json)
- [Ripple](https://magicui.design/r/ripple.json)

The dependency-free ports preserve the core sweep, ripple and head/tail mechanics, adapted to the requested placement, easing, palette and accessibility constraints. [MIT attribution](licenses/magicui-MIT.txt) is included. No React, motion, Tailwind, shadcn CLI or Node package was installed.

## Verification and visual comparison

Run the isolated browser checks with optional development installations of Playwright, OpenCV and Pillow:

```bash
python tools/check_dashboard_cinematic.py
python tools/check_dashboard_phase1.py
python -m unittest discover -s tests -v
python tools/metal.py test
```

The cinematic harness checks all four states, reverse scrubbing, three demo passes, source labels, no fabricated readiness changes, reduced-motion shutdown, context-loss fallback, mobile overflow, a single canvas and cinematic playback without mutations. The existing dashboard harness checks demo/halt/resume/close, mandate approval/stale versions, SSE reconnect/deduplication, token/Origin/Host refusal and keyboard drawer focus. Both use temporary public-code roots and mock runtime data, excluding local credentials and private `data/`.

Captures, a timestamped 4×6 comparison sheet and measured performance live in [the evidence folder](evidence/cinematic/README.md). Remaining differences from the supplied recording are documented there; this is an original procedural reconstruction, not the source site's geometry or shader.
