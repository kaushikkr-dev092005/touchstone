# Authenticated operational workspace

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

The public Worker cannot execute the Python/SQLite service. Deploy this service on
an approved persistent Linux/Docker host with its own operator HTTPS domain. No
such approved host/domain has been supplied during this implementation. Docker's
daemon is also unavailable in the current Windows environment; container execution
and public operator availability must not be claimed as verified.

`deploy/operator/compose.yaml` provides a non-root, read-only application container,
private proxy network, outbound quote network, named persistent database volume,
health check, dropped capabilities and Caddy TLS proxy. Python port 8089 is **not
published**. Only proxy ports 80/443 are public. There are no payer/bank secrets or
wallet mounts. The image includes the pinned Node dependencies for read-only quote
validation. Pin deployment images to reviewed digests before production hardening;
the supplied tags and Docker build have not been validated on this machine.

On the approved host, point the domain's DNS at that host and copy the reviewed
repository. Copy `deploy/operator/.env.example` to `deploy/operator/.env`, then set
the domain and exact reviewed Git commit. These values are not financial secrets.

```text
docker compose --env-file deploy/operator/.env -f deploy/operator/compose.yaml build
docker compose --env-file deploy/operator/.env -f deploy/operator/compose.yaml run --rm -it operator python tools/run_operator.py init --config /var/lib/touchstone/operator-config.json --origin https://YOUR_OPERATOR_DOMAIN --environment SANDBOX
docker compose --env-file deploy/operator/.env -f deploy/operator/compose.yaml up -d
```

Replace the domain placeholder. Do not put the password in a command, environment
variable, image layer, shared log or Git. Initialization creates only the local
operator identity the administrator explicitly requests. No bank or model action
runs during deployment. Limit network ingress to the proxy; restrict allowed quote
egress at the host firewall. Do not mount the private payer's filesystem.

Validate externally before announcing deployment:

```text
curl --fail https://YOUR_OPERATOR_DOMAIN/healthz
curl -i https://YOUR_OPERATOR_DOMAIN/operator-api/jobs
```

Health must identify `touchstone-operator`, the configured environment, source
revision and disabled financial dispatch. Anonymous jobs must return **401**.
Sign in through the browser, execute the arithmetic example, reload, restart the
container and verify that history and audit remain valid. Test HTTPS cookies and
SSE through the actual proxy. Do not use curl flags that print cookies or passwords.

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
