# Current dashboard delivery

The canonical dashboard design is `apps/dashboard/index.html`. Previously the
local `/console` used this design while public `/dashboard` rendered a separate,
older React evidence layout. Publishing React alone did not include the redesign.

`bun run build` in `apps/web` now generates `public/dashboard/index.html` from
the canonical console and embeds it at public `/dashboard` and `/ledger`.
Generated assets stay ignored; fresh repository builds reproduce them.

The generated page retains the console's CSS, icons, cards, navigation and panels.
It removes every original script and the operator token. A dedicated read-only
renderer loads only committed, projected evidence under `/site/`. It never opens
an operator API, SSE stream or wallet, and has no signing or dispatch path.
Public CSP permits only same-origin framing of this generated HTML. Other pages
retain their existing framing restrictions.

The public ledger retains all 43 published purchase attempts, receipt references,
individual policy decisions, separate USDZ charges and API-credit estimates,
search, outcome filters, sorting, CSV export and record inspection. Candidate,
review, rejected, confirmed unpaid and unresolved outcomes remain distinct. The
completed 64-outcome comparison and the separately labelled simulated benchmark
remain available in Evidence. Original benchmark and financial files are unchanged.

The local `/dashboard` still detects the loopback operator context and embeds the
original `/console`; its existing details, controls and security rules are retained.
The separate authenticated `/control-room` requires its Python backend and is not
made operational by publishing this read-only frontend.

Build and check without spending:

```text
cd apps/web
bun install --frozen-lockfile
bun run build
cd ../..
python -m unittest discover -s tests -p test_public_dashboard.py
python tools/check_site_design.py
python tools/check_dashboard.py
python tools/metal.py test
```

`tools/build_merchant.py --commit <reviewed-commit> --include-site` packages the
matching frontend, public dashboard and Worker. It refuses uncommitted changes
to the canonical dashboard and evidence inputs. Publishing must use that exact
artifact; refreshing an older deployment cannot load a newer Git revision.

Repository changes are reviewed on a feature branch. The default branch remains
unchanged until its pull request is approved and merged. No historical transaction
is relabelled as a new live or cryptographically human-approved purchase.

Verified public release: Sites version 6, application source `0f8481a`, published
14 November 2026. Public desktop/mobile inspection confirmed the current design,
43 attempts, receipt inspection and the complete comparison. The public operator
backend remains disconnected. Full current Python tests: 464 passed; Node: 67;
merchant: 9. No financial transaction or model call was initiated.
