# Repository cleanup audit — 14 November 2026

## Scope and baseline

This is a zero-spend maintenance audit, not financial qualification or a deployment.
Source baseline: `dd1b4af9cab6d2390996f7fbf02cd4e87d3051bb` on `master`; cleanup branch:
`cleanup/repository-audit-20261114`. The original worktree was **not clean**:
`README.md`, `apps/dashboard/index.html`, and `touchstone/server.py` were modified,
and `integrations/metal/dashboard-shell.test.mjs` was untracked. Those four files
were snapshotted and are excluded from this cleanup's commit. Baseline checks use
that actual working tree, including the redesign; the branch starts at the recorded
commit. No stashing, resetting, overwriting or committing unrelated work is allowed.

All **604 tracked files**, **35,276,562 working-tree bytes**, were enumerated,
read and SHA-256 hashed before cleanup. Counts/bytes include existing tracked user
edits; untracked files, ignored data, models, node_modules, dist and Git history are
excluded. This is logical file size, not disk allocation or compressed clone size.

| Area | Tracked files | Bytes before cleanup |
|---|---:|---:|
| `.env.example` | 1 | 687 |
| `.github` | 1 | 1,120 |
| `.gitignore` | 1 | 150 |
| `.openai` | 1 | 91 |
| `LICENSE` | 1 | 1,070 |
| `README.md` | 1 | 9,925 |
| `apps` | 43 | 608,311 |
| `bench` | 242 | 7,477,563 |
| `docs` | 99 | 25,641,991 |
| `integrations` | 39 | 148,612 |
| `pyproject.toml` | 1 | 227 |
| `tests` | 61 | 396,577 |
| `tools` | 61 | 382,444 |
| `touchstone` | 52 | 607,794 |

Discovery included Python AST imports and main guards; all CLI registrations;
JavaScript/TypeScript static imports and exports with `@/` and relative resolution;
checks for dynamic imports/globs; filesystem reads and subprocess commands; CI;
package/build scripts; Markdown links; public asset copying; and deployment bundling.
Literal-reference absence alone never qualifies a deletion. Text search excludes
binary payloads, which were still fully hashed. Near-duplicate media are not treated
as equivalent records.

## Entry points and protected paths

| Entry point / area | Role and disposition |
|---|---|
| `touchstone/__main__.py`, `touchstone/server.py` | CLI registrations, loopback API/SSE, local console; KEEP |
| `tools/run_mock.py`, `tools/run_project.py`, `tools/run_local.py` | Isolated demo, adapter launcher/status, thermally supervised model startup; KEEP |
| `ledger.py`, `engine.py`, `live.py`, `banked.py` | Reservations, atomic dispatch, recovery, independent banked workflow; KEEP |
| `procurement_approval.py`, Metal schema/verification/adapter/bridge/CLI/provider | Human EIP-712 trust, exact terms, replay/credit and protected payer guards; KEEP |
| Treasury/holds/checkout/FX/issuing/merchant modules | Sandbox banking and guest OAuth/MCP; KEEP |
| Router/verifier/invoice/qualification/comparison modules | Source and semantic checks, frozen criteria, policy studies; KEEP |
| `apps/dashboard/index.html`, `procurement.js`, cinematic sources/assets | Current console, signing UI, CSP/token/Host/Origin protections, reproducible visuals; KEEP |
| `apps/web/src/main.tsx` → App/Landing/Workspace/Director/BlackHole/VaultSequence | Active React entry graph and actual cinematic vault; KEEP |
| `apps/merchant/worker.mjs`, `site-assets.mjs`, `.openai/hosting.json` | Existing public Worker, site packaging and DB binding; KEEP |
| `.github/workflows/ci.yml`, manifests and lockfiles | Python 3.11/3.12 on Windows/Linux, pinned Node prerequisites and secret scan; KEEP |
| All tests and all `bench/` files | Discovery/glob-driven tests, measured/model/financial records and frozen inputs; KEEP |

`tools/bundle.py` uses the committed Git tree; `tools/build_merchant.py --include-site`
builds Vite assets and embeds them in the merchant Worker. Neither requires the
unreachable component chain proposed below. No Python function/module, SDK adapter,
security test or financial workflow was found safe to delete.

## Stage 1 — removal and retention inventory

Analysis completed before any removal. Proposed source removal:
**4 files / 28,092 bytes**. No archives are proposed. The initial unused
dependency candidate was `@samasante/liquid-glass`, imported only by Glass. A trial
removal changed generated CSS because Tailwind also scans unreachable source.
Glass and the dependency manifests/lockfile were restored exactly; they are KEEP.
The four accepted removals produce byte-identical frontend output.
All other frontend dependencies have active runtime, build or browser-QA consumers;
Python has no runtime third-party dependencies. Metal's pinned SDK/viem and its
lockfile are security-critical and remain untouched.

| File | Size (bytes) | Category | Evidence | References | Risk | Replacement | Action |
|---|---:|---|---|---|---|---|---|
| `apps/web/src/components/CardsScene.tsx` | 13,434 | Abandoned presentation experiment | No imports, dynamic loads, CLI/test/docs references; not reachable from main.tsx. Only consumer of Glass and ignored cards-scene fixture. | Full-path, basename, export and resolved import-graph search; no active callers | LOW | `Active Landing.tsx and Workspace.tsx` | DELETE |
| `apps/web/src/components/Lamp.tsx` | 6,818 | Abandoned presentation experiment | No imports, dynamic loads, CLI/test/docs references; absent from the active entry graph. | Full-path, basename, export and resolved import-graph search; no active callers | LOW | `Current navigation and cinematic Director` | DELETE |
| `apps/web/src/components/icons/index.tsx` | 6,151 | Orphaned icon experiment | No imports or path-based loaders; active UI imports components/Identity.tsx. Its theme consumer is also unreachable. | Full-path, basename, export and resolved import-graph search; no active callers | LOW | `apps/web/src/components/Identity.tsx` | DELETE |
| `apps/web/src/lib/theme.ts` | 1,689 | Orphaned theme implementation | Only imported by unused Lamp and icons/index; active main/index HTML uses dark and intro-init.js. No runtime loader. | Full-path, basename, export and resolved import-graph search; no active callers | LOW | `Existing active dark frontend styling` | DELETE |
| `apps/web/src/components/Glass.tsx` | 1,347 | Indirect Tailwind build input | Although unreachable from main.tsx, Tailwind scans its block and border strings. Trial removal changed generated CSS; restored exactly. Keep @samasante/liquid-glass and the lockfile unchanged pending a separate reviewed styling migration. | Repository-wide literal/reference and entry-graph inspection | MEDIUM | Existing file | KEEP |
| `apps/web/src/components/Vault.tsx` | 13,132 | Superseded presentation source | The import graph finds it unreachable, but docs/landing.md and tools/check_site_design.py describe/reference the original locker. Preserve design reproduction rather than conflate old and active vault implementations. | Repository-wide literal/reference and entry-graph inspection | MEDIUM | Existing file | KEEP |
| `apps/web/src/lib/utils.ts` | 93 | Scaffold helper | components.json explicitly configures its utils alias for developer-generated components. Not imported is insufficient evidence to delete a configured tool target. | Repository-wide literal/reference and entry-graph inspection | LOW | Existing file | KEEP |
| `apps/web/components.json` | 237 | Developer setup configuration | Component generator aliases and CSS configuration; not a runtime import. | Repository-wide literal/reference and entry-graph inspection | LOW | Existing file | KEEP |
| `apps/web/public/logo.png` | 137,661 | Unreferenced public asset | Copied verbatim by Vite and published as a public URL; deleting changes observable asset availability and branding. | Repository-wide literal/reference and entry-graph inspection | MEDIUM | Existing file | KEEP |
| `apps/web/public/theme-init.js` | 275 | Legacy public asset | No current HTML import, but Vite copies it to a public URL. Preserve public URL availability. | Repository-wide literal/reference and entry-graph inspection | MEDIUM | Existing file | KEEP |
| `tools/check_policy_outage.py` | 2,120 | Specialized study CLI | Read-only attestation used to investigate a bound injected outage; preserves study reproduction/diagnosis even without a literal caller. | Repository-wide literal/reference and entry-graph inspection | HIGH | Existing file | KEEP |
| `tools/finalize_live_proofs.py` | 7,968 | Historical evidence tooling | Reads journals and chain receipts to assemble financial proof; not a dead library import. | Repository-wide literal/reference and entry-graph inspection | HIGH | Existing file | KEEP |
| `tools/finalize_policy_completion.py` | 4,914 | Historical evidence tooling | Reconstructs completion view from measured comparison; retain evidence reproducibility. | Repository-wide literal/reference and entry-graph inspection | HIGH | Existing file | KEEP |
| `tools/prepare_live_completion.py` | 8,625 | Operator workflow CLI | Prepares scopes/quotes/cost counts; an intentional standalone entry point. | Repository-wide literal/reference and entry-graph inspection | HIGH | Existing file | KEEP |
| `tools/reconcile_qualification_metadata.py` | 5,125 | Research provenance tooling | Restores cost metadata from original delivery evidence; cannot be replaced by a new inference run. | Repository-wide literal/reference and entry-graph inspection | HIGH | Existing file | KEEP |
| `tools/renew_policy_mandate.py` | 3,181 | Operator workflow CLI | Dedicated renewal workflow with original approval limits; do not remove financial-control tooling based on import reachability. | Repository-wide literal/reference and entry-graph inspection | HIGH | Existing file | KEEP |
| `tools/restore_policy_metadata.py` | 3,264 | Research provenance tooling | Restores allowlisted metadata from cached deliveries without inference; supports auditability. | Repository-wide literal/reference and entry-graph inspection | HIGH | Existing file | KEEP |
| `tools/verify_merchant.py` | 8,624 | Integration verification CLI | Guest OAuth/MCP and catalog read checks; preserve independent operational diagnosis. | Repository-wide literal/reference and entry-graph inspection | HIGH | Existing file | KEEP |

`apps/web/src/data/cards-scene.ts` exists locally but is ignored by the repository's
`data/` rule and is not tracked. Its only consumer is CardsScene. It is not deleted,
added, read as financial data or included in cleanup metrics. This also explains
why preserving the abandoned component would not provide reproducible fixture code.
`Vault.tsx` is retained despite being absent from the current entry graph because
its documentation/reproduction role is established. `utils.ts` remains a configured
developer-tool target. Do not expand cleanup into active CSS or rewrite components.

## Exact duplicate groups — all retained

Six SHA-256 groups contain 16 files (10 redundant copies by content). Similarity
does not erase independent experiment paths or provenance. No canonical financial
record is substituted and no saved report is regenerated.

| Files | Size | Action | Evidence |
|---|---:|---|---|
| `bench/results/completion-20261109/issuing-current.json`<br>`bench/results/completion-20261110/issuing-current.json`<br>`bench/results/validation-20261107/issuing-readiness.json`<br>`bench/results/validation-20261109/issuing-readiness.json` | 191 each | KEEP | Independently located financial/research or saved validation artifacts; provenance paths and historical records are protected. SHA-256 `fd5fa7b6169128ceb65529e8db5a0aa6e49ce3ab98fedaa65040f6b4519e46a6`. |
| `bench/results/completion-20261110/issuing-diagnosis-current.json`<br>`bench/results/features/card-readiness.json` | 1,472 each | KEEP | Independently located financial/research or saved validation artifacts; provenance paths and historical records are protected. SHA-256 `30eb2dcb5739d07241e51f7abeee4bb49358fcef86571e2c6f9315e1eec3e570`. |
| `bench/results/completion-20261110/profiles/balanced-qualified-study.json`<br>`bench/results/m3/profiles/balanced-source-spans-20261110.json` | 566,810 each | KEEP | Independently located financial/research or saved validation artifacts; provenance paths and historical records are protected. SHA-256 `0d44bf32dabf600ebb999f1c0235971d3ec3c291de57ff615a134b36129acf1a`. |
| `bench/results/features/browser-validation.json`<br>`bench/results/package/browser-tests.txt` | 953 each | KEEP | Independently located financial/research or saved validation artifacts; provenance paths and historical records are protected. SHA-256 `3fac85f77cde942a5bef01d49170ae2a90d9b9c2ec55625e0c03a344c67f298c`. |
| `bench/results/m4-v2/comparison-draft-seller-schedule.json`<br>`bench/results/m4-v2/final-plan-seller-schedule.json`<br>`bench/results/m4-v2/qualified-plan-seller-schedule.json` | 578 each | KEEP | Independently located financial/research or saved validation artifacts; provenance paths and historical records are protected. SHA-256 `77334b87d28e5b524242271d438d3c83676005f0bccc315638aa991f20c1da0a`. |
| `bench/results/m4/proposed-plan-seller-schedule.json`<br>`bench/results/validation-20261107/m4-plan-seller-schedule.json`<br>`bench/results/validation-20261109/m4-plan-seller-schedule.json` | 570 each | KEEP | Independently located financial/research or saved validation artifacts; provenance paths and historical records are protected. SHA-256 `bd46f8a81d83588bd720c164eff3ee0b727474f7411113bb219e1dcfce8f0fe7`. |

## Media, documentation and generated artifacts

All tracked media in `docs/evidence/cinematic/`, its `regression/` subdirectory,
`docs/evidence/design-phase1/`, and `docs/recordings/` are retained. They are not exact
duplicates. Their adjacent READMEs, capture tools, saved browser reports and hashes
explain independent states, viewports and historical checks. Captures are historical
evidence, not a claim that today's redesigned DOM passed those old browser scripts.
The canonical `docs/recordings/touchstone-demo.webm` and transcript remain unchanged.
No build cache, private wallet, live database or node_modules tree is tracked.
Ignored caches/output are outside this cleanup; deleting them would not shrink a
clone and could disrupt the operator's environment.

Every existing Markdown document under docs was inspected and categorized in
[the documentation index](README.md). Historical reports/runbooks/design iterations
stay at their original paths so links and provenance remain valid. The index directs
judges to current feature/security/evidence documents first and labels history.

## Baseline and validation method

Checks run with AIRWALLEX, METAL, ANTHROPIC, agent keys and local runtime settings
removed from child environments and `TOUCHSTONE_IGNORE_LOCAL_CONFIG=1`. Node/viem
dependencies were already installed; no provider services, GPU models or paid tests
are started. Mock servers use temporary data directories and browser checks abort
external requests. Ordinary unit tests use controlled adapters, including tests whose
fixture mode string says LIVE TESTNET; that label is not external activity.

Baseline browser failures, before removal:

- `python tools/check_dashboard.py`: the redesign removed `.disclosure`; locator timeout.
- `python tools/check_signed_mandates.py`: its old linear-page flow does not select
  the redesigned Approvals tab, so `#human-authorization` is hidden.
- `python tools/check_site_design.py`: the embedded console's shared hash/history
  selects a view that hides `#start`; the old embedding assertion times out.

These failures must remain visible in the results. No tests or user UI are altered
to turn them green under this cleanup. A separate current-layout mock smoke check
can exercise explicit navigation, transactions, approval controls and ledger/audit
reconciliation, but does not replace those failed required checks.

Final test results, byte-preservation checks, Git diff and live-site observations
are recorded below after Stage 2. Local detailed logs and full SHA-256 inventory are
under ignored `tmp/cleanup-20261114/`; committed results below must state exact
commands and failures so review does not require those local files.

## Production and live-use boundary

The public deployment is a saved-evidence viewer and sandbox merchant, not the
protected loopback operator service. HTTP 200 or a successful mock demo does not
prove current paid inference, Airwallex transaction readiness, Visa approval or
production credential isolation. No cleanup operation requalifies models, renews
spending approval, executes recovery against a real rail, or relabels old receipts.
Human signatures remain enforced at the existing protected dispatch boundaries;
the fully compromised host/key-access limitations in Signed Mandates remain.

## Stage 2 — accepted changes and validation

Removed only CardsScene.tsx, Lamp.tsx, icons/index.tsx and lib/theme.ts listed above.
The initial five-file trial also removed Glass and its dependency. Its CSS delta
removed Tailwind `.block`, `.border` and border-style registration. Glass and both
dependency files were restored exactly before accepting the cleanup. All **19**
final Vite outputs (HTML, JS, CSS, fonts, public assets and saved evidence projection)
match the baseline SHA-256 map byte-for-byte. Neither lockfile is changed.

All **462** tracked backend, tools, tests, integration, dashboard, merchant and
benchmark files match their initial working-tree SHA-256 values, including **all
242 benchmark files**. The four pre-existing modified/untracked user files match
their starting bytes. Cleanup commits exclude those files. The user's later request
to diagnose/fix an integration status label is separate from these cleanup changes.

| Command / check | Before cleanup | After cleanup |
|---|---|---|
| `python -m unittest discover -s tests` | PASS: 438; 347.045 s | PASS: 438; 383.266 s |
| `python tools/metal.py test` | PASS: 64 | PASS: 64 |
| Node `--test apps/merchant/merchant.test.mjs` | PASS: 9 | PASS: 9 |
| `bun run build` in apps/web | PASS | PASS; all 19 final outputs unchanged |
| `python tools/check_dashboard.py` | FAIL: missing `.disclosure` | SAME baseline failure |
| `python tools/check_signed_mandates.py` | FAIL: Approvals panel hidden | SAME baseline failure |
| `python tools/check_site_design.py` | FAIL: embedded `#start` hidden | SAME baseline failure |
| `python tools/demo_signed_mandates.py --output tmp/cleanup-20261114/after/signed-proof.json` | Not rerun as baseline | PASS: unsigned blocked / signed one MOCK dispatch / tampered blocked |
| `python tools/scan_secrets.py --json` | Not rerun as baseline | PASS: no findings; 1,663 blobs; 9 oversized and 133 binary exclusions |
| Markdown relative-link validation | Inspected links | PASS: 47 Markdown files; 413 links; no missing targets |
| `git diff --check` on cleanup paths | No cleanup yet | PASS |

The 64 Node tests include the user's eight untracked dashboard-shell tests; those
tests are retained but not silently added to this cleanup commit. The existing
committed Node suite contains 56 tests. Unit coverage includes signature, replay,
concurrency, restart, recovery, invoice roles and audit controls. No unrun platform
matrix (Linux, Python 3.11) is claimed: this run uses Windows and Python 3.12.

Supplementary current-layout browser smoke: six navigation views, all three MOCK
jobs, transaction/receipt/charge drawer, search, 64-row CSV and matching totals,
valid audit, matched reconciliation, and 320/390/768/1440 widths pass with zero
external requests or JavaScript errors. A separate in-memory adaptation of the
signed-wallet browser scenario selects the Approvals tab and omits the removed
theme-toggle click; genuine ephemeral EIP-712 signing, tamper rejection and MOCK
dispatch pass. These checks do **not** turn the three original failed commands
into passes. No existing test file was changed.

`python tools/run_project.py --status --no-browser --output
tmp/cleanup-20261114/runtime-status.json` works as a read-only status entry point:
dashboard and model RUNNING, both sellers STOPPED, incomplete stack/nonzero status.
It does not start sellers. `tools/run_mock.py` launches the current local website
on 127.0.0.1:8088 with an isolated ledger; all four website/console routes return
200. The user separately requested GPU startup: the local Qwen balanced tier is
healthy under the unchanged 65°C start / 75°C stop thermal guard. No model call was
made; GPU availability is not qualification or live payment readiness.

## Read-only external observations and remaining limitations

At 05:50 UTC on 14 November, separate credential-bearing read-only checks (never
forwarded to tests) verified Airwallex sandbox authentication, balance/global-account,
checkout-session and FX reads, issuing reads (one existing card/cardholder), and
merchant-config readability. An existing USD 1 PaymentIntent reads SUCCEEDED with
USD 0.01 captured. This is a readback of an old completed operation, not a current
hold or permission for a new write. Metal RPC connects on chain 63825; no transaction
was sent. Issuing write readiness, a new merchant payment, Visa approval and a new
paid inference are not established by these reads. Both local paid sellers are off.

Sites reports existing public deployment v4 active/public. Unauthenticated GETs
to site, dashboard, ledger, merchant and OAuth discovery return 200; the public
procurement-approval API returns 404. The recorded deployment source is bdff6c9,
so it is not evidence that uncommitted local UI or Signed Mandates were published.
No website was deployed or financial operation dispatched by this cleanup.

Follow-up work remains separate: update obsolete browser selectors for the new
tabbed layout; investigate Glass/Tailwind build coupling before further deletion;
review public-URL compatibility before removing public assets; keep dated financial
reports and provenance duplicates. Account reads and HTTP health do not establish
a production-ready paid end-to-end run. Existing credential-isolation and Visa
approval limitations remain documented and unchanged.

## Metrics and review boundary

Original tracked files: **604**; final tracked files after adding the two documents: **602**.
Deleted: **4**; archived: **0**; source bytes removed: **28,092**.
Original logical tracked bytes: **35,276,562**; final: **35,279,178**.
Net logical tracked-byte reduction including documentation: **-2,616 bytes**
(a negative reduction means the audit/index add more bytes than the deleted source).

Logical tracked bytes count the current working tree and preserve the pre-existing
user changes. Git history and packfiles are not rewritten: deleting tracked files
does not immediately shrink historical packs. The added audit/index are deliberate
review documentation, not replacement experiment data. No files were archived.

The cleanup diff is exactly four unused source deletions plus this audit and the
documentation index. README, dashboard, server, all tests, all benchmark records,
both lockfiles and all financial/security code remain outside the cleanup diff.
No merge, default-branch push, force-push or history rewrite is authorized here.
