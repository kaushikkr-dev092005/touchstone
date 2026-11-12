# Touchstone website

The landing page, Dashboard and Ledger share one origin and browser history.
The landing opens on black. An isometric vault unlocks, reveals a key, closes and collapses
into a point of light. That point ignites into a ray-marched black hole whose photon ring arcs
behind the floating pill navigation, and then the hero is revealed. The intro plays once per
session (`?intro=force` replays it) and can be skipped with the button or Escape.
**Open Dashboard** and the Ledger link replay a compressed vault and commit the route while the
screen is covered. Returning home replays only the ignition and hero. Reduced-motion users get
crossfades and one static frame. Details, timing and tuning are in [landing.md](landing.md).

The workspace keeps its behaviour and is restyled to match: black, amber accent, Geist. The glass
dock appears on the Dashboard and Ledger. The pill navigation collapses into a menu on phones.

## Public and operator views

- Public: `/` redirects to `/site/`. `/dashboard` and `/ledger` display saved,
  explicitly labelled sandbox/testnet evidence. Filters, search and receipt details
  work without dispatching payments or inference. `/merchant`, product URLs,
  checkout callbacks, OAuth discovery, JWKS and token endpoints remain available.
- Local: `/site/`, `/dashboard` and `/ledger` use the same frontend. The workspace
  embeds `/console?embedded=1`, retaining the existing operator controls, CSRF token
  and loopback restrictions. `/console` and `/` still provide the standalone console.
  The embedded console allows framing only from the same origin.

`tools/build_site_evidence.py` projects allowlisted fields from already-public
benchmark reports. It reads no private runtime files. `tools/build_merchant.py
--include-site` embeds the matching Vite output in the existing Worker. Credentials,
wallet files, private keys and the Python operator API are never hosted.

## Reproduce the checks

```text
cd apps/web
bun install --frozen-lockfile
bun run build
cd ../..
python tools/check_site_design.py
python -m unittest tests.test_merchant_service -v
```

The browser check starts an isolated simulator, blocks external requests, verifies
320/390/768/1024/1440px layouts, the full intro with skip and vault unmount, the Dashboard
vault transition and its skip, history, ledger
filters and receipts, touch navigation, reduced motion, the real embedded operator
console and session protection. It sends no financial transactions or model calls.
`tools/validate_release.py --browser --frontend` includes this check in fresh-source
validation. Screenshots and the browser report are written under `tmp/site-design`.

The public workspace is a recorded-evidence viewer. It does not imply Visa approval,
independent final clearing, completion of the interrupted comparison, or authority
for another paid operation. Those project boundaries remain as recorded in the
financial evidence and external-access documentation.
