# Live workspace verification â€” 14 November 2026

**Current acceptance: locally operational zero-charge slice; public operator
deployment and remote financial execution are not complete.** No new bank operation,
testnet payment, funding, card creation or paid model call was made.

## Before-state

Starting source: dd1b4af9cab6d2390996f7fbf02cd4e87d3051bb. The working tree already
contained README/dashboard/server edits and an untracked dashboard-shell test.
They were retained. Cleanup was isolated in e1151c1, removing four unreachable
presentation files while retaining Glass (an indirect Tailwind input), all media,
all 242 benchmark files, financial code and lockfiles. The initial 438 Python and
64 Node tests passed. Three old browser scripts failed against the new tabbed DOM.
Their controls/selectors have now been adapted without removing financial assertions.

## Implementation and boundary

- `operator_auth.py`: scrypt login, persistent opaque sessions, expiry/idle/rotation,
  revocation, CSRF and rate controls. No financial keys.
- `operations.py`: validated immutable custom tasks, idempotency, local-tool planning,
  actual source verification, zero-charge persistence/audit, pause/resume, immutable
  read-only quote observations. Unknown sources block; there is no synthetic fallback.
- `operator_server.py`: bounded authenticated API/SSE, Host/Origin/CSP checks,
  replay, explicit route allowlist, safe errors and integration-snapshot expiry.
- React `ControlRoom`: actual sign-in/create/start/status/ledger/events and snapshot
  controls. Existing public/evidence/dashboard routes remain separate.
- `quote-probe.mjs`: existing SDK discovery and offer validation without opening a
  wallet or sending a payment signature. Failed readiness remains BLOCKED.
- `run_operator.py` / `operator_backup.py`: explicit offline provisioning, exclusive
  owner lease, persistent storage and backup/restore with session invalidation.
- `check_integrations_readonly.py`: explicit private sandbox/RPC read checks;
  credentials are never forwarded to the new remote service or automated tests.
- Docker/Caddy files: TLS gateway, non-root application, persistent volume and no
  publicly bound Python port. Container/proxy execution is not verified locally.

The backend has **no remote pay, capture, transfer, deposit, card-issue or approval
proxy route**. New browser controls cannot invoke the private loopback console.
The existing ledger/Node signed-mandate dispatch and recovery boundaries are unchanged.
Current provider qualification is stale, so no remote paid eligibility is claimed.

## Executed observations

The actual authenticated browser scenario passed job creation, output 2000 cents,
source verification, backend events, browser refresh, process restart, persistent
session, audit integrity, logout revocation and widths 320/390/768/1440. It used
temporary credentials/data and made zero external requests, payments or model calls.
Its generated screenshots/report are under ignored `tmp/operator-browser/`.

The updated existing dashboard browser check passed the three-job MOCK demo,
halt/resume/close, Host/Origin/token rejection, billing policy, reconciliation and
128 transaction rows including drawer/search/filter/pagination/CSV checks. No
existing benchmark was regenerated to obtain these results.

Private read-only checks at 07:45 UTC authenticated Airwallex sandbox and verified
balance/global-account, checkout and FX reads, issuing reads (one existing card
and cardholder), and merchant config readability. The existing USD 1 PaymentIntent
reads SUCCEEDED with USD 0.01 captured. The hold flow label now correctly names
**SAVED SANDBOX CAPTURE** when its backend evidence matches the account; it never
claims a currently active hold. Without matching evidence it remains unverified.
Metal RPC connects on testnet chain 63825. Local paid seller services are stopped.

The current public deployment is **Sites version 6**, successfully published at
11:56:55 UTC on 14 November 2026:
https://touchstone-sandbox-merchant.sublimeoak1.chatgpt.site/dashboard

Application source: `0f8481acb3d8b69f6a8bbd0b664e16429d659f05`.
Sites artifact-source commit: `07b1fcc9d83f77911df937f5a99583eaba5de07b`.
Deployment: `appgdep_6af84c7a571481919baa35bcd1086050`.

This replaces the older public React evidence layout with a read-only projection
of the current canonical dashboard. External GET checks returned 200 for landing,
dashboard, ledger, generated dashboard HTML and reports; procurement approvals and
operator jobs returned 404. Public browser checks confirmed 43 saved attempts,
receipt inspection, all four policies / 64 outcomes, mobile layout and zero page
errors. `/control-room` correctly reports **Backend not connected**, with no sign-in
form. Publishing the new design does not deploy the authenticated Python backend.

Current source validation (financial credentials stripped; local config disabled):

| Command | Actual result |
|---|---|
| `python -m unittest discover -s tests` | 464 passed; 349.859 seconds |
| `python tools/metal.py test` | 67 passed |
| Node merchant tests | 9 passed |
| `bun run build` in `apps/web` | TypeScript and Vite build passed |
| `python tools/check_site_design.py` | Passed: vault, public ledger/CSV, 320/390/768/1024/1440 widths, private console/CSRF |
| `python tools/check_dashboard.py` | Passed: existing private controls and 128-row transaction explorer |
| `python tools/scan_secrets.py --json` | 1,728 blobs scanned, no findings; heuristic exclusions reported |

The initial updated browser check found a missing confirmed-unpaid filter. The
public projection gained that filter and the check passed on rerun. No assertion
was removed to obtain passing results. All benchmark files and the pre-existing
canonical dashboard remain unchanged relative to `6f7318b`.

The broader archive release validator's earlier run at `6f7318b` passed Python/Node
checks but failed the M2 controlled CLI proof's six-purchase assertion: that legacy
harness does not install independent test-signing fixtures. It was not rerun or
represented as passing in this dashboard release. Historical financial evidence
was not regenerated to work around this failure.

## Outstanding release gates

- An approved persistent Python host and operator domain/TLS were not supplied.
- Docker API is unavailable: `dockerDesktopLinuxEngine` named pipe not found.
  Dockerfile, proxy/TLS behavior and remote-volume persistence need host validation.
- The operator must explicitly provision their own password; no real user account
  or external account was automatically created.
- External providers, fresh qualification, allocations, independent human signatures
  and new transaction scopes/caps are still required for a paid private run.
- Visa approval remains pending. No local signing key is presented as Visa-approved.
- Single-operator authentication is not enterprise RBAC. No independent penetration
  test or fully compromised-host guarantee is claimed.

The application revision above identifies the deployed build. Later documentation-only
commits do not change that artifact. The feature branch requires review before merge.
