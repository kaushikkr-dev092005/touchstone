# Current operational feature matrix

Status is based on code and executed checks, not the age of a README claim.
`LIVE VERIFIED` below names its scope; local operational processing is not a live
bank transaction. Historical measured operations remain historical.

| Feature | Status | Evidence / precise remaining gate |
|---|---|---|
| HTTPS public landing, dashboard, ledger, merchant | LIVE VERIFIED — public saved evidence | Existing Sites v4 GET checks return 200; new operator backend is separate |
| Existing cinematic design and responsive frontend | IMPLEMENTED / CONNECTED | Vite build and browser checks; prior assets retained |
| Operator authentication, CSRF, strict Host/Origin | IMPLEMENTED / locally LIVE VERIFIED | Actual HTTP + browser sign-in/session/logout tests; no public TLS deployment yet |
| Source submission and persistent jobs | CONNECTED / locally LIVE VERIFIED | React → operator API → SQLite → audit; custom source, idempotency, owner checks |
| Deterministic arithmetic/invoice/classification | locally LIVE VERIFIED | Real bounded local tool and existing source verifier; zero model/bank calls |
| Unfamiliar sources and invoice extraction | BLOCKED / review | Local tool abstains; no synthetic answer or automatic invoice payment |
| Actual SSE, replay and refresh | CONNECTED / locally LIVE VERIFIED | Durable event IDs; browser job events, refresh and backend-restart persistence |
| Local pause/resume/start | CONNECTED | Pause prevents Start; Resume only queues; concurrent completion executes once |
| New operational transaction explorer | CONNECTED | Persistent actual job/output/verdict and zero charges; currencies remain separate |
| Existing financial transaction drawer/search/CSV | CONNECTED / SIMULATED main loop | Retained details; real controlled browser verifies 128 rows and charge totals |
| Saved 64-outcome policy comparison | LIVE VERIFIED — historical testnet evidence | All original benchmark files unchanged; not a new run or savings claim |
| Provider discovery and x402 quotes | IMPLEMENTED; external readiness BLOCKED | Operator origin allowlist + existing SDK offer validation; sellers currently stopped |
| Provider qualification | BLOCKED | Existing source-provenance gates stale; current service never promotes them to eligible |
| Remote paid inference/escalation | BLOCKED / NOT IMPLEMENTED remotely | No financial dispatch capability or payer credentials in the remote service |
| Private Engine / LiveSession / Banked / Metal paths | IMPLEMENTED | Existing approval/recovery tests; needs fresh scope, qualification, funds and actual signed terms |
| EIP-712 human wallet signing and negative cases | IMPLEMENTED / controlled verified | Existing private dashboard and real viem tests; no new paid call or genuine human-wallet live proof |
| EIP-712 remote approval/payer proxy | NOT IMPLEMENTED | Deliberately absent; must not expose the loopback console as a shortcut |
| Airwallex auth, balances, FX/checkout reads | LIVE VERIFIED — read-only sandbox | 14 November explicit private read check; no conversion or authorization created |
| Airwallex historical customer capture | LIVE VERIFIED — readback | Existing USD 1 intent reads SUCCEEDED / USD 0.01 captured; not a current active hold |
| Airwallex issuing and merchant config reads | LIVE VERIFIED — read-only sandbox | One existing card/cardholder; config readable; new writes/payments not tested |
| Airwallex writes in remote workspace | BLOCKED | No endpoints/keys; requires new approved scope and private workflow |
| Metal RPC | LIVE VERIFIED — read-only testnet | Chain 63825; no transaction sent |
| Local GPU | LIVE VERIFIED — local service health | User-requested thermally guarded model; availability is not qualification |
| Metal fault acknowledgement / recovery proof | LIVE VERIFIED — historical | Existing signed receipt/evidence; rejected credit remains rejected; no refund claim |
| Visa registration / agent trust | BLOCKED_EXTERNAL_APPROVAL | Application pending; local RFC 9421 verification remains distinct |
| Backups, restore, session revocation | IMPLEMENTED / controlled verified | SQLite backup + exclusive owner lease; fresh destination; audit checked |
| Docker/Caddy deployment configuration | IMPLEMENTED / execution BLOCKED | Docker daemon unavailable on current host; image/proxy execution not verified |
| Public authenticated Python service | BLOCKED | Approved persistent backend host, domain/TLS and operator provisioning not supplied |
| Production financial operations | DISABLED | PRODUCTION config rejected; no ambiguous LIVE flag or frontend override |

This is a working authenticated **zero-charge vertical slice**, not completion of
all financial deployment criteria. See [deployment](LIVE_DEPLOYMENT.md),
[judge interactions](LIVE_JUDGE_DEMO.md), and [verification](LIVE_VERIFICATION_REPORT.md).
