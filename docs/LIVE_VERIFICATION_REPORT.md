# Live workspace verification — 14 November 2026

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

The existing public Sites v4 viewer and merchant returned HTTP 200 for landing,
dashboard, ledger, merchant and OAuth discovery; the procurement API returned 404.
That deployment corresponds to bdff6c9, not this new authenticated backend. No new
public operator deployment has yet succeeded. A working HTTPS evidence page is
not proof of public authenticated job processing.

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

Final source revision, exact full-suite/release results and PR will be appended
after validation. Unrun checks must not be represented as passing.
