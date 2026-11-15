# Authenticated operational workspace

For Oracle Always Free infrastructure, account gates and the actual deployment
status, see [Oracle deployment](ORACLE_DEPLOYMENT.md). No cloud deployment is
claimed until its external acceptance checks pass.

This release implements a working **zero-charge operational vertical slice**:
authenticated source submission, bounded local computation, deterministic verification,
SQLite persistence, hash-chained audit, real SSE, job controls and transaction inspection.
It is separate from the existing simulator and saved-evidence website. It does not
enable remote paid procurement. Read [the feature matrix](LIVE_FEATURE_MATRIX.md)
and [executed verification](LIVE_VERIFICATION_REPORT.md) before presenting it.

## Local operation

Python 3.11+ and the existing frontend toolchain are required. Build the UI:

```text
cd apps/web
bun install --frozen-lockfile
bun run build
cd ../..
python tools/run_operator.py init --origin http://127.0.0.1:8089 --username operator --environment DEMO
python tools/run_operator.py serve
```

Initialization asks for a unique password twice in a masked terminal; it does not
create an external account, a wallet or spending authority. Existing config files
are never overwritten. Open http://127.0.0.1:8089/control-room and sign in.
The existing local website/console on 8088 remains available with all its evidence,
transaction details and simulator controls. Never expose that loopback console
directly to the internet. The public merchant Worker has no operator API.

The operator configuration lives in ignored `data/private/operator-config.json`.
It contains an scrypt password hash/salt, origin, single operator identity,
environment, session limits and a provider-origin allowlist. It contains **no human
private key**. Protect its directory and database with an OS ACL (chmod is only
best effort on Windows). Use a dedicated OS user in deployment.

## Deployment boundary

The public merchant Worker cannot execute the Python/SQLite workspace. The
shared `deploy/operator/Dockerfile` builds the current React frontend and canonical
read-only dashboard. Its public routes use projected committed evidence; the
private loopback `/console` is never exposed by the operator service.

`deploy/operator/compose.yaml` uses a reviewed ARM64 image, separate unprivileged
application/proxy UIDs, read-only roots, dropped capabilities, bounded logs and
persistent data. Python has no public port. HTTPS is an explicit profile; without
an owned domain use `compose.tunnel.yaml`, which publishes Python on host loopback
only and requires SSH forwarding. No cloud/bank/model credentials or wallets are
mounted. Initialize the operator interactively in **DEMO** mode.

Follow [the exact Oracle setup and maintenance commands](ORACLE_DEPLOYMENT.md).
Build and verify committed source off-host with `tools/build_operator_image.py`
and `tools/check_operator_container.py`. The local image can be transferred over
SSH after its archive checksum and revision are verified; public registry
publication is not required. Local container checks do not establish public TLS
or Oracle host readiness.

## Authentication and security controls

The service uses one explicit operator identity; it is not an enterprise RBAC or
multi-tenant service. Passwords use scrypt. Random opaque sessions are hashed in
SQLite, expire after one hour, and time out after 15 idle minutes. Configuration or
password rotation invalidates old sessions. Logout revokes the server-side record.

HTTPS uses `__Host-touchstone` cookies with Secure, HttpOnly, SameSite=Strict and
Path=/. HTTP cookies are permitted only for loopback development. Host and Origin
must match the configured canonical origin. All writes additionally require a
session-bound CSRF header. There is no cross-origin CORS allowance or arbitrary
backend proxy. JSON rejects duplicate keys, extra fields, invalid amounts and
oversized inputs. Login and mutation limits persist in SQLite; request threads and
SSE subscribers are bounded. Errors exclude credentials/source data. The public
health check reveals no secrets. The existing private console's CSP is unchanged.

These choices follow [OWASP's session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet/).
The [Caddy proxy reference](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
documents streaming behavior; actual proxy/TLS operation remains a deployment gate.
This implementation has not undergone an independent penetration test. The
stdlib HTTP server must remain behind the configured TLS gateway; no claim of
production-grade financial isolation or resistance to a compromised host is made.

## Provider and banking connections

Provider allowlist entries are configured offline, for example:

```json
{"id":"local-gpu","origin":"http://127.0.0.1:8092"}
```

Add entries to the config's `providers` list; use HTTPS outside loopback. A browser
cannot supply a provider URL. The server constructs the task resource from its
stored source and the Node probe reuses the SDK's deployment/asset/network/cap
validation. It never opens a wallet or sends a payment signature. Quotes are
immutable observations, persist with their digest/expiry, and remain blocked for
purchase. Container loopback refers to the container, not the developer's GPU host;
configure an approved reachable origin rather than assuming port forwarding.

Current qualification provenance is stale; the remote service explicitly reports
`BLOCKED_REQUALIFICATION_REQUIRED`. A responsive endpoint or GPU profile is not
qualification. No model fallback or new qualification was run in this release.

On the **private credential-bearing operator host**, run the read-only checker:

```text
python tools/check_integrations_readonly.py
```

It authenticates to Airwallex sandbox and permits GET reads only after login,
checks existing capture/issuing/merchant configuration and Metal RPC, then writes
an ignored status snapshot. It does not load a payer private key, issue cards,
make conversions, create/capture holds or run inference. Set its `--output` to
the operational data directory's `readonly-integrations.json` when transferring
the redacted snapshot through an administrator-controlled channel. The authenticated
workspace reads that file; after five minutes it reports BLOCKED until a new
private check is made. The UI's snapshot button reads cached observations rather
than pretending to perform fresh bank authentication.

Sandbox reads do not establish write permissions. Visa remains
`BLOCKED_EXTERNAL_APPROVAL`: retain the application reference, obtain Visa's
approval/official registration instructions, provision independent trusted keys,
then verify the registered identity before enabling any claim or merchant workflow.
Locally verified Ed25519/RFC 9421 messages are not Visa-issued credentials.

## Persistence, backup and recovery

Use one service process per data directory. The existing SQLite owner lease
prevents competing operator processes. Job creation is idempotent per operator and
request key. Local execution updates the result and audit in one transaction:
crashing before commit leaves a queued task; after commit it remains completed.
Repeating Start on a completed job does not execute it twice. Pause blocks a queued
task; Resume queues it and still requires explicit Start. These controls do not
cancel already-dispatched external purchases.

The browser refetches durable state after SSE reconnect and deduplicates event IDs;
the server replays using Last-Event-ID and rechecks session expiry on each stream.
Backup/restore is offline to avoid swapping an active database:

```text
python tools/operator_backup.py backup --data-dir data/operator --archive tmp/operator-backup.sqlite
python tools/operator_backup.py restore --data-dir data/operator-restored --archive tmp/operator-backup.sqlite
```

The tool requires the service owner lease, uses SQLite backup, refuses overwrite,
checks integrity/audit on restore and revokes all restored sessions. Preserve the
separate operator config securely. Backups contain source data and session metadata;
encrypt them at rest and restrict OS access. Never commit them or restore over the
private financial ledger. The financial engine's original-invoice recovery and
approval consumption are unchanged; their tests and historical proof remain.

## Optional real financial run — not part of deployment

Use the existing [M3](M3_RUNBOOK.md), [M4](M4_RUNBOOK.md), and
[Signed Mandates](SIGNED_MANDATES.md) private workflows. First verify a currently
qualified model, actual quote, provider identity, network, wallet allocation and
balances. Obtain fresh explicit approval naming every rail/currency, provider/model,
amount, aggregate/per-call/API-credit/native-fee caps, source of funds, attempt
count and expiry. Then an independently controlled allowlisted human wallet must
sign the exact backend-generated terms. The protected Python ledger and Node payer
both enforce them. Historical approvals are consumed and provide no new authority.
Unknown payments reconcile the original invoice; they never authorize a retry.

The remote service has **no pay/capture/fund/issuing/approval-proxy endpoint**.
Connecting it to a protected payer is future, separately reviewed work. Do not
weaken this boundary or label this slice fully live financial procurement.
