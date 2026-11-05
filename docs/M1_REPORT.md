# M1 — implementation and external blocker, 2 November 2026

## Current evidence — 5 November 2026

**MEASURED: M1's real write/read-back gate PASSED.** Exactly one sandbox FX
conversion sold **1.00 USD for 0.89 EUR**, settled, and matched both wallet-history
entries. Observed USD cash debit: exactly 1.00. Its request-ID index returned 404;
the report explicitly records a bounded read-only scan matching the conversion ID.

One separately authorized hosted card session completed **1.00 USD authorization**
and **0.01 USD capture**. The intent is SUCCEEDED; 0.99 was left uncaptured by final
partial capture. Issuer release/credit timing is **UNMEASURED**. Exactly one session
create and one capture request occurred; no cancel request was needed. Both
transaction approvals are consumed. Historical native PaymentIntent errors do not
establish the current account's hosted entitlement.

Evidence: [FX](../bench/results/m1/live-fx-single-conversion.json),
[separate treasury accounts](../bench/results/m1/live-treasury-job.json),
[closed hosted authorization](../bench/results/m1/current-hosted-card-proof.json).
Airwallex and Metal remain separate; the treasury demo-token entry is SIMULATED.
Treasury audit head: `1855dc7889c605a2a406bb6cfa2df5a54ec544f7317869178ddbf86cae873e6c`.

Fixes cover supported smoke pagination, token reuse, strict official sandbox-host
validation, completed-capture read-back, account-bound readiness and exact FX-source
reconciliation. Controlled regression tests exercise each path. No runtime dependency
was added. [Current validation](VALIDATION.md).

Allowed: these sandbox writes and their read-backs. Not allowed: issuer refund timing,
an integrated three-customer banking run, enabled native checkout, a real hold increase,
or a fiat/token bridge. No further M1 transaction is authorized or needed for this proof.

## Historical report

The dated observations below describe their original runs; the current evidence above supersedes their readiness statements.

Exit: **documented blocker path**. The authorized implementation is complete and locally tested; a real sandbox write/read-back remains **BLOCKED**. No live quote, conversion, hold, capture, release, withdrawal or retirement was performed. M1 stops here for the required report.

## What changed

- Environment-only `airwallex-doctor` checks account context and optionally probes balances/history/conversion reads. It never reads private config/wallet files or claims read success proves Conversion Write.
- `treasury-job prepare/run/reconcile/report` binds a customer budget currency, quote, unique FX request ID and explicitly SIMULATED demo rate to a job. Reconciliation matches settled FX with both wallet-history entries before creating append-only account entries and an audit event. Unknown/mismatched results cannot credit float.
- Treasury state is visible in the dashboard and can be required by `banked-job --treasury-request-id`. Actual Metal funding is independently checked. Airwallex fiat, customer mandate, SIMULATED demo USDZ and actual testnet funding are separate.
- PaymentIntent 4xx `configuration_error` creates become `REJECTED_NO_OBJECT`. Duplicate request IDs become consumed and are not replayed. New `airwallex-retire` requires matching rejection/support evidence, a complete empty fresh lookup, and a fresh replacement scope; the old UUID is preserved behind a permanent tombstone.
- Added execute guards for hold/checkout/banked operations and an explicit sell-currency/amount cap on FX execution. Historical Metal standalone commands still need their M2 guard review before any execution.
- Prepared the [operator runbook](M1_RUNBOOK.md) and [Airwallex support draft](AIRWALLEX_SUPPORT_REQUEST.md). No support message was sent. Virtual cards were not started because issuing enablement is unconfirmed.

## Evidence and test results

| Label | Evidence | Result |
|---|---|---|
| BLOCKED | [Environment doctor](../bench/results/m1/airwallex-doctor.json) | Required Airwallex variables absent in the agent's process; no API requests made. User reports another configured terminal. |
| MEASURED | [Python test log](../bench/results/m1/python-tests.txt) | 148 passed, including 15 new M1 tests against controlled adapters |
| MEASURED | [Node test log](../bench/results/m1/node-tests.txt) | 24 passed, including dashboard parsing, account labels, escaped content and unavailable-evidence handling |
| MOCK | [Treasury and retirement proof](../bench/results/m1/controlled-treasury.json) | One controlled conversion despite repeat execution; separate account entries; local retirement with preserved UUID; no remote calls |
| MEASURED | [Heuristic secret scan](../bench/results/m1/secret-scan.json) | No findings or sensitive committed paths in the reported scope; private data excluded |

The saved MOCK audit-chain head is `712bf299c355482369d50ef25aa8c062d662f9bbd6d2db93b202a766e6443d9a` (three events). Reproduction generates a new head because timestamps differ. No live financial audit head is claimed.

**MEASURED hosted CI:** all four Ubuntu/Windows × Python 3.11/3.12 jobs passed on implementation commit `7dcd212c867527ea71fef9be3e17937f03be9d1d`, including Python tests, pinned Node installation/tests and the full-history heuristic secret scan. [CI run](https://github.com/kaushikkr-dev092005/touchstone/actions/runs/41498024314) · [saved CI metadata](../bench/results/m1/ci.json). Hosted success covers controlled tests, not live financial execution.

## Claims now allowed and not allowed

Allowed: tested account/scope diagnostics; guarded FX workflow and job accounting against the documented API contract; tested consumed-ID handling and evidence-based local retirement; visible separate-account stages with explicit MOCK/SIMULATED/BLOCKED labels.

Not allowed: verified Airwallex FX write, successful customer authorization/capture, enabled acquiring or issuing, a retired historical live scope, actual token funding from fiat, or completed M2 live crash recovery. Historical authentication/read evidence remains historical; the current doctor did not authenticate.

## Authorized follow-up

Written approval is now recorded for exactly one sandbox USD→EUR conversion, maximum aggregate USD debit **1.00 including fees**. The [latest redacted doctor recheck](../bench/results/m1/authorized-recheck.json) remains BLOCKED: all three required variables are absent from the execution environment, so no API request or conversion was attempted. Account, balances, quote, minimum amount and fee-inclusive debit must all be verified before execution. If the total debit cannot be bounded at USD 1.00, stop. No automatic uncertain retry and no other transaction is authorized. This supersedes the earlier pending-approval wording below and in the original runbook.

## What is needed from the user

Make the replacement scoped credentials and account ID available in the execution environment; share only setup status or redacted doctor output. Confirm accepted registration and submission schema in the portal and send the prepared support request. Spend approval does not need repeating. The runbook commands require a verified fee-inclusive debit within the approved cap, not merely a sell amount of USD 1.00.

The spend approval is required by the user's Money safety rule, which requires both an execute-style flag and written chat approval with a cap. Environment setup or “proceed with M1” does not specify that cap.
