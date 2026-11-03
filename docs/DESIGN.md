# Touchstone — the assay bench

Design brief · 3 November 2026 · **Review gate: dashboard implementation has not started.**

## Concept and composition

A dark testing stone, one overhead lamp, and evidence left by each attempt. Gold means **passed the bounded verifier**; a red scratch means rejected; an unfinished outline means unresolved. None of these marks grants permission to pay an invoice or guarantees semantic correctness. Failed inference purchases remain expenses.

Use the references as devices: Neywa's illuminated horizon and pill navigation; Monei's mandate-to-emblem loop; CYBE's masked hex field and angled tags; Metal's editorial grid, large type and chrome edges. All objects and marks are original CSS/SVG geometry. No copied artwork, logos, asterisk, bonsai, payment-network mark, stock AI imagery or external assets.

Composition is asymmetric: copy occupies the left five columns; the lamp and stone extend beyond the right margin. The Ledger becomes a ruled financial worksheet. Reserve glass for the navigation and mandate; operational panels are flat, square-edged sections separated by hairlines. No repeated rounded glass-card rows.

**Copy correction:** retain “Pay for [proof], not promises.” as the conceptual hook, with nearby paid-failure disclosure. Replace the proposed Loop heading “ONLY PAY FOR / VERIFIED WORK” with **“EVERY CALL IS PAID. / EVERY RESULT IS TESTED.”** The requested wording would imply an unimplemented outcome-contingent charging/refund policy.

## System

| Token | Dark scenes | Bone Ledger |
|---|---|---|
| Canvas / text | ink `#090A08`, bone `#F2EFE6`; intro starts `#000000` | bone `#F2EFE6`, ink `#151710` |
| Secondary text | `#ADB0A4` | `#5D6057` |
| Hairlines | `#303329` | `#D0CCBF` |
| Assay gold, sole brand accent | `#D8B65A` | `#80601D` |
| Rejection, semantic only | `#F07868` | `#A32E27` |
| Live confirmation, semantic only | `#8AC595` | `#256443` |

Warm gold and ivory form the mandate's two blurred blobs. Chrome uses neutral reflections; RGB fringes are confined to a one-pixel object edge, never UI accents or status indicators. Only the main display headline may use a subtle bone-to-white text gradient. Other headings use solid text. Decorative hairlines do not substitute for accessible control boundaries.

- **Three families, zero font bytes:** Georgia for display, Arial for UI, Consolas/monospace for figures. Display-only line spans receive restrained optical horizontal condensation with compensated layout width; body text remains uncompressed. This supplies the narrow serif silhouette without remote fonts, font-loading shift or a CSP change.
- **Scale:** display 64–120px desktop / 48–60px mobile; scene headings 40–64 / 32–40; oversized figure 112–176 / 80–104; section headings 24; body 16/24; metadata 12/16. Figures use tabular numerals. One `h1`; subsequent scene titles are `h2`.
- **Grid:** 8px spacing baseline; desktop Ledger has 12 visible hairline columns, 24px gutters and 48px outer margins at 1440px. At 390px use four structural columns, 16px gutters and 24px margins; retain subtle 12-column ruling as a background. Stack content in reading order; wide tables scroll inside their own labelled container.
- **Controls:** 44px minimum targets, persistent labels, 3px visible focus ring, disabled plus explanatory text. Normal text must reach 4.5:1 contrast, large text and essential boundaries 3:1. Validate actual composited surfaces in each phase.
- **Mode forms:** LIVE = solid dot plus text; SIMULATED = hollow dot and dashed border; BLOCKED = diagonal stripe swatch plus text; MEASURED = check mark plus text; MOCK = square outline plus text. Outcome symbols add check / cross / dashed outline. Connection status says CONNECTED, never LIVE merely because SSE works. Historical proof says MEASURED · TESTNET · ON FILE.
- **Theme:** Ledger defaults to bone; its dark/light toggle changes worksheet and drawer tokens and remembers the operator's local choice. The three narrative scenes retain their dark material. No theme change affects execution.

## Four scenes

1. **Ignition.** Black canvas, an enormous original horizon limb, thin warm rim and restrained atmosphere. A glass pill nav sits above left-aligned serif copy with the solid gold “proof” pill. Keep “Sandbox - Testnet - Simulated demo,” with the dashed SIMULATED form and a nearby scope explanation. Buttons: “Run three-job demo” and “View evidence”; retain Replay intro and key L, excluding typing/modifier shortcuts. At t=0 the atmosphere is black and controls remain readable; at 1s the rim is emerging; by 2.5s the reveal finishes and actual run state controls the lamp. The intro is labelled DEMO, not financial activity.
2. **The Loop.** A frosted **SIMULATED customer mandate** shows the selected job's actual hold/budget, per-call cap, expiry and mandate version from state. Empty fields are dashes. A static infinity SVG connects the authorization metaphor to an original polished assay slab; its caption makes clear that this is a control loop, not an Airwallex-to-token bridge. Up to 12 chrome slabs represent distinct recorded attempts/events. A fresh payment advances their orbit once; verification adds a gold streak or a red scratch/drop. Pending attempts remain dim and dashed, explicitly “no receipt yet” when appropriate. Wireframes represent actual unresolved attempts, not invented records. Rejection never removes the underlying expense from the drawer or Ledger. With no events the ring is empty.
3. **Guardrails.** Olive-black field, radial-masked hex grid and soft downward beams. Five angled tags: Capped, Idempotent, Verified, Audited, Kill switch. Each opens the corresponding real evidence source below; missing evidence is BLOCKED. Tags move slightly only on fresh operational events; hover/focus freezes them. The prominent kill action uses the existing halt endpoint and clearly states its simulator scope. Confirmed halt extinguishes every artistic lamp; readable controls and evidence remain available. Resume is explicit and restores light only after server confirmation. In-flight effects may still need reconciliation.
4. **The Ledger.** Bone worksheet with a large grotesk cost numeral, source caption and run identity; all existing functional panels remain. The numeral is **— / NOT YET MEASURED** unless an eligible saved paid-run metric is supplied. The event stream becomes a numbered receipt tape with mode, timestamp and outcome; it never autoscrolls away while the operator reads. Group controls, planning, comparisons, probe P&L and audit evidence along shared grid rules. Job summaries become divided columns, not glass cards.

## Motion and SSE contract

Use `cubic-bezier(0.16,1,0.3,1)`: hover/focus 150ms, controls/theme 220–300ms, payment pulse/orbit 320ms, rejected slab 400ms. The **2.5s ignition is the sole long sequence**. Stars reveal with that sequence, then stay static; remove continuous twinkle and pointer parallax. No idle carousel, floating decoration or permanent pulse. Reduced motion shows final static states immediately, with symbols/text replacing flicker, travel and drift.

Only the dominant visible scene may animate. One shared IntersectionObserver/visibility scheduler owns motion; pause on hidden tabs and render the latest state on return without replaying a backlog. Retain the SSE connection and state updates. Only the intro uses an animating canvas; receipt slabs use focusable CSS 3D buttons. Cap canvas DPR at 2, cache geometry, animate transforms/opacity, and keep at most three visible backdrop-filter surfaces. 60fps is a target to measure in Chrome on the RTX 3050, not a current claim.

The server emits **unnamed SSE messages**, not named browser events, about every 900ms: `id: cursor`, JSON `{state, events, worker_error}`. Records contain `id`, `ts`, `kind`, `payload`, `previous_hash`, `hash`. Browser reconnect uses `Last-Event-ID`; server batches up to 100 records. Preserve deduplication by event ID. Initial/history/reconnect catch-up hydrates the ring/tape without replaying old payment effects. Snapshot attempts are limited to the latest 80; never label that window as the lifetime total.

| Code-backed signal | Meaning and visual |
|---|---|
| `state.halted`, `KILL_SWITCH` | Highest priority, including over intro/rejection: lamp off after confirmation |
| `OPERATOR_RESUME`, refreshed state | Restore only the state the server confirms; never clear halt locally |
| `jobs[].status === RUNNING` | Full lamp; no periodic pulse without a payment event |
| `PAID` | One soft pulse and one receipt arrival; same attempt retains its identity |
| `VERIFIED_OK` | Gold streak and check; bounded checker acceptance |
| `VERIFIED_FAIL` | One brief red rim response and slab drop; expense remains recorded |
| `PAUSED_POLICY`, `PAUSED_REVIEW`, `PAUSED_RECOVERY`, `RECOVERY_PENDING` | Cooler neutral, dimmer lamp; dashed unresolved form when payment is uncertain |
| No active job / completed | Dim resting lamp |
| Disconnect or `WORKER_ERROR` | Visible stale/error notice; no fabricated activity; error cannot conceal a confirmed halt |

Other emitted kinds in the inspected control plane: `HOLD_AUTHORIZED`, `MANDATE_INCREASE_APPROVED`, `FLOAT_TOPUP`, `RESERVED`, `ROUTED`, `DISPATCHING`, `PROVIDER_MEASUREMENT`, `RESERVATION_VOIDED`, `RECOVERED`, `HOLD_CAPTURED`, `WORKER_ACQUIRED`, `WORKER_RELEASED`, `CHAOS`. They populate evidence/tape; `CHAOS` is a simulator scenario, not a measured outage. `PAUSED_KILL`, `RUNNING` and `COMPLETED` are job snapshot states, not dedicated emitted kinds. There is no provider-light, lamp or orbit event. An unsupported demonstration stays idle and explicitly labelled DEMO.

**Transport is not provenance:** `serve()` constructs `Engine(..., MockRail(...))`. Its genuine ledger/SSE records describe simulated financial operations. Ring, tape and lamp all retain SIMULATED labels. Separate historical testnet evidence never gets merged into the simulator's current event ring.

## Endpoint and panel inventory

All requests are same-origin loopback. No new endpoint or server/security change is planned.

| GET | Existing source / retained use |
|---|---|
| `/` | Single HTML; preserve token meta and nonced script placeholders |
| `/api/state` | Jobs, mandates, attempts, modes, reconciliation, audit, worker status; controls and scene state |
| `/api/events` | SSE snapshots and ledger events; lamp, receipt tape and event evidence |
| `/api/audit` | Full local event chain and validity; deliberate evidence inspection, not an animation feed |
| `/api/readiness` | Local configuration/saved observations, historical paid proof, model profiles; no automatic live-health claim |
| `/api/real-provider-runs` | Redacted saved paid-policy reports; paid comparison and potential cost numeral |
| `/api/benchmark` | Saved `bench/results/simulated.json`; separate SIMULATED comparison |
| `/api/noisy-verification-chart` | Saved SVG; synthetic fault-injection chart, with missing-artifact fallback |
| `/api/procurement-evidence` | Deterministic planner, eligibility and source explorer; retain stale/missing refusals |
| `/api/invoice-study` | M3 baseline, qualification and three-task showcase; retain BLOCKED model state |
| `/api/banked-jobs` | Banked journal, treasury FX stages and separate-account labels |

POST actions remain `/api/demo`, `/api/halt`, `/api/resume`, `/api/close`, `/api/approve-increase`. Preserve the per-process `X-Touchstone-Token`, JSON bodies, Host/Origin checks, CSP nonce and existing validation/error semantics. An HTTP error must not be rendered as a successful stop, approval or resume. No scene initiates a paid external transaction.

| Existing component | Placement / retained behavior |
|---|---|
| Intro, readiness strip, replay, navigation | Scene 1; glass nav and single intro |
| Five-node payment-path evidence | Restyled with Ledger in Phase 1; becomes Scene 2 with its evidence access retained in Phase 2 |
| Demo run / resume / halt / close controls, notices | Ledger control strip; guardrail halt shares the existing action handler later |
| Float, total spend, accepted count, cost/accepted | Ruled summary strip, always SIMULATED; do not confuse acceptance with offline correctness |
| Three job summaries, provider market | Ledger job columns and quote table |
| Decision stream and purchase ledger | Receipt tape and detailed attempt table |
| Reconciliation, safety assertions, versioned approval form | Ledger controls/evidence; approvals still simulated, still require separate Resume |
| Historical paid-proof headline, spend/capture/unbilled probe summary | Evidence folio and existing limited probe P&L; no fabricated consolidated banking revenue |
| Real-provider trial / simulator benchmark / noisy-check chart | Separate comparison blocks with their own modes and missing-data states |
| Testnet proof, banked journal, treasury funding accounts | Evidence folio; preserve fiat/token separation |
| M3 three-task panel, eligibility table, source/output explorer | Planning folio; current source/provenance guards retained |
| Integration readiness, audit status/head/JSON link | Evidence rail and worksheet footer |
| Evidence dialog, confirmed-kill overlay | Accessible drawer and persistent stop status; retain keyboard close and focus return |

## Data limits and evidence links

- **Cost numeral:** use the latest reconciled `real-touchstone` report from `/api/real-provider-runs` with `valid_live_evidence === true`, positive verified-correct count and a finite nonnegative supplied cost. Show its scope, task sample and currency. Simulated check fees and excluded upstream API dollars must remain disclosed; a mixed cost cannot be labelled wholly measured. Empty/invalid/incomplete evidence leaves the dash. Never substitute `/api/benchmark` or the simulator's cost/accepted value. The one historical rejected testnet call provides no nonzero correct-output denominator.
- **Mandate:** select an actual snapshot job; read its `hold`, `budget`, `price_cap`, `expires_at`, `mandate_version`. No invented balance, expiry or current authorization.
- **Slabs/drawer:** link `PAID.payload.key/receipt` to subsequent verification events and their event IDs. Pending reservations may have no receipt. The browser receives IDs and redacted records, not the original signed receipt/invoice document; do not present a reconstructed signature or claim browser-side payment verification.
- **Guardrail links:** Capped → job limits/reservations; Idempotent → saved replay evidence, labelled on-file and scoped; Verified → actual verifier outcomes/version; Audited → current local chain; Kill switch → confirmed halt/resume events. Links open the drawer or existing panel anchors. Unserved `docs/` paths are not dashboard links. A valid local hash chain is not independent attestation.
- No endpoint supplies a complete real customer/provider/check-fee P&L, continuous external-provider health, model qualification by mere connectivity, upstream dollar bill, or fiat/token bridge. Keep those absent or BLOCKED. The existing readiness observations are advisory/on-file. Do not read wallet files or private `data/` contents for this design.

## Delivery gates and critique

1. **This gate:** commit only this brief; stop for user review before dashboard coding.
2. **Phase 1:** consolidate the five overlapping style blocks; apply tokens and Scenes 1/4, theme toggle and existing controls. Remove purple/lime visual accents, identical glass panel styling, duplicate marketing `h1`s, endless twinkle/parallax and hardcoded loading amounts/counts presented as current state. Keep all operational panels. Commit and stop; the user may finish here.
3. **Phase 2:** build the mandate/stone/infinity composition and event-bound receipt slabs/drawer. No synthetic receipt placeholders. Commit and stop; the user may finish here.
4. **Phase 3:** build the evidence-linked guardrail field and confirmed-kill lighting; finish responsive, performance and accessibility work. Commit and report.

At each phase, perform the squint test (one focal point and one primary action), check alignment against the visible grid, measure contrast, and name **three specific elements that look generic/AI-made**. Fix those elements before the phase commit; save the critique and changes with its evidence. Initial risks to challenge: a generic planet landing page, an ornamental finance card, and a wall of dashboard boxes.

Acceptance after each implemented phase: full `python -m unittest discover -s tests -v` plus existing Node tests; isolated mock-demo browser checks for run, SSE reconnect without duplicate effects, approval/resume, kill/error paths and session-token rejection. Use temporary test data, no financial service or wallet. Exercise keyboard, focus return, reduced motion on/off, hidden-tab suspension and no external requests. Keep the HTML below about 250KB, with inline CSS/JS and no new runtime dependencies or security changes.

Capture implemented scenes at **1440×900 and 390×844**, with Scene 1 at **t=0, 1s and 3s**; include reduced-motion final states, empty evidence, rejection and confirmed halt. Reserve art/chart/table dimensions to avoid layout shift. Measure Chrome rendering performance before claiming 60fps. Final phase reports list changes, removals, test/screenshot evidence, unresolved data sources and limits. No screenshot, test or performance claim is made by this brief.


## Reference revision — 2026-11-03

The user withdrew the Metal screenshot reference and supplied a screen recording of upright discs moving over a metallic track with a circular inspection light. This recording now guides the background effect. Do not use the withdrawn image or its glyph ring. Recreate the motion and depth with original inline SVG/CSS, assay marks and the existing gold palette; do not embed the recording, its currency marks, pointer or promotional text.

The hero horizon is replaced by an inspection track. Its introductory movement is explicitly DEMO and stops after ignition; subsequent scanning pulses follow received payment events. These decorative discs are not ledger records or currency transfers. Reduced motion is static, off-screen/hidden animation pauses, and confirmed halt turns the light off. The earlier proposed Metal-inspired orbit is superseded; any later receipt composition should use this track direction and remain bound to real event records. Existing evidence labels, account separation and financial controls remain unchanged.
