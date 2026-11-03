# Dashboard design — Phase 1

2026-11-03. Scenes 1 and 4, implementing the approved [design brief](../../DESIGN.md).

## Changed

- One inline design system: ink, bone, assay gold; three system font families; no font downloads. The self-contained HTML is under 80 KB.
- Asymmetric ignition scene, original stone-streak mark, warm horizon, finite star reveal, pill navigation, keyboard replay (`L`) and explicit demo disclosure.
- A ruled Ledger with a 12-column desktop grid, light/dark paper, a gated cost-per-correct figure, flat evidence sections and a receipt-like decision tape. All existing operational panels and controls remain.
- No startup balances, task counts or provider quotes are invented. The main cost figure requires a reconciled qualifying paid report; mixed measured payments and simulated check fees stay disclosed.
- Confirmed halt overrides every lamp effect. Reconnect/initial history does not replay payment pulses. Reduced motion is static; the star loop ends after ignition and pauses off-screen. Hidden-tab handlers cancel its frame request and pause CSS animation.
- Added tests for cost provenance, invalid evidence and halt precedence, plus a reproducible isolated browser check.

## Removed

Five overlapping style blocks, duplicate marketing `h1`s, purple/lime decoration, repeated rounded glass panels, continuous twinkling, pointer parallax, speculative startup quotes, and the decorative multicolour payment path. Its five evidence controls remain as a numbered worksheet.

No ledger, rail, verifier or server/security implementation changed. The existing session token and Host/Origin checks remain in use. No transaction or external financial request was made.

## Critique and fixes

**Squint test:** the serif promise and gold proof word form the hero's focal point; one filled button carries the primary action. The Ledger changes clearly to paper, with the missing measured figure occupying the large numeric position. The operational content uses rules and spacing rather than competing boxes.

**Grid:** desktop title, navigation, section rules and tables share 48px outer lines. The main measure splits at column seven. Mobile uses 24px margins and four structural columns; wide financial tables scroll inside labelled, keyboard-focusable regions.

Three generic-looking details identified in the first browser pass and fixed:

1. Tiny metadata resembled decorative dashboard filler. Increased readiness, metric and connection type sizes, retaining explicit on-file/mode descriptions.
2. Four equal historical-proof metrics resembled a stock KPI row. Gave the source/model result a wider column and a rejection rule, making the failed assay the visual conclusion.
3. The transparent secondary CTA crossed the mobile horizon, resembling a generic glass button with variable contrast. Gave it an opaque ink surface and checked the resulting text contrast.

**Contrast:** computed foreground/background checks cover primary/secondary buttons, Ledger text, secondary text, gold figures and rejection text in both themes. The lowest checked ratio is **5.06:1**; see [browser-checks.json](browser-checks.json). Input/button boundaries use the secondary text colour. This is not a comprehensive assistive-technology or WCAG certification.

## Verification

| Evidence | Result |
|---|---|
| Python `python -m unittest discover -s tests -v` | MEASURED — 177 passed |
| Node `python tools/metal.py test` | MEASURED — 32 passed |
| Browser `python tools/check_dashboard_phase1.py` | MEASURED — isolated MOCK financial workflow; detailed checks in JSON |
| Three-job demo, halt/resume, capture/release | MOCK — exercised through the actual local server |
| Mandate approval and stale-version refusal | SIMULATED — exercised through the actual form/server |
| Reconciliation and audit chain | MOCK — matched and valid after the browser run |
| Session token, Origin and Host rejection | MEASURED — invalid requests returned 403 |
| SSE reconnect | MEASURED — isolated server restarted; history deduplicated, no replay pulse |
| Keyboard drawer dismissal/focus return | MEASURED — Escape closes; focus returns to the evidence control |
| Offline UI and reduced motion | MEASURED — controls remain usable; no external requests; static reduced-motion state |
| RTX 3050 / 60fps target | NOT MEASURED — headless Chromium is not hardware performance qualification |

The browser harness copies only tracked public code/evidence into a temporary root, uses a temporary mock ledger, and excludes credentials and private runtime data. Screenshot timing is deterministic CSS-animation seeking at 0/1/3 seconds, with the 3-second frame showing the completed intro and idle lamp; it is not frame-rate evidence. The JSON records the dashboard SHA-256 and Chromium version.

## Screenshots

| Scene/state | 1440 × 900 | 390 × 844 |
|---|---|---|
| Ignition, 0s | [Desktop](desktop-ignition-0ms.png) | [Mobile](mobile-ignition-0ms.png) |
| Ignition, 1s | [Desktop](desktop-ignition-1000ms.png) | [Mobile](mobile-ignition-1000ms.png) |
| Ignition, 3s | [Desktop](desktop-ignition-3000ms.png) | [Mobile](mobile-ignition-3000ms.png) |
| Ledger | [Desktop](desktop-ledger.png) | [Mobile](mobile-ledger.png) |

Additional inspection: [dark paper](desktop-ledger-dark.png), [reduced motion](desktop-ignition-reduced-motion.png), [confirmed halt](desktop-halted.png), [mobile purchases](mobile-purchases.png).

## Data limits and remaining work

- Existing saved planning evidence reports `STALE_OR_INVALID` against the current source. Its explorer remains disabled and labelled BLOCKED. No report was regenerated to conceal this condition.
- The isolated browser run has no private paid-policy reports. Its main cost figure is an em dash, not the simulator's cost/accepted value. The historical rejected testnet probe is displayed separately from the current mock run.
- Existing APIs do not supply a complete real P&L, upstream API dollar costs, continuous provider health, or raw signed receipt documents for the drawer. No substitute figures or live-health claims were added.
- Airwallex fiat and Metal testnet accounts remain separate; no bridge is implied.
- Hidden-tab handling is implemented; a hardware rendering/hidden-window profile and broader assistive-technology review remain manual checks. No 60fps claim is made.
- Phase 2 (mandate, stone, loop and event-linked receipt slabs) and Phase 3 (guardrail scene) await their review gates. Phase 1 stops here.
