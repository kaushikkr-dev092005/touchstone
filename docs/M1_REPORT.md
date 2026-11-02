# M1 — implementation and external blocker, 2 November 2026

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

## What is needed from the user

Run the doctor from the terminal containing all three environment variables; share only its redacted result. Confirm accepted registration and submission schema in the portal. Send the prepared support request through your channel. To perform the proposed FX proof, provide written approval for **one sandbox USD→EUR conversion, maximum and aggregate sell amount USD 1.00, no Metal or customer-payment operations**. This cap has not been approved. Exact preview, execution and read-back commands are in [M1_RUNBOOK.md](M1_RUNBOOK.md).

The spend approval is required by the user's Money safety rule, which requires both an execute-style flag and written chat approval with a cap. Environment setup or “proceed with M1” does not specify that cap.
