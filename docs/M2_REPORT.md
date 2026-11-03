# M2 implementation report — 3 November 2026

Implementation is complete. The **live exit gate is BLOCKED / NOT PASSED**: no new Metal purchase or live kill/restart was executed. The existing single-call approval remains valid.

## What changed

- The unified engine binds every reservation to its mandate version. One SQLite transaction rechecks that version, expiry, halt status and worker ownership and changes `RESERVED` to `DISPATCHING`. Only one dispatch can win. This state remains reserved in budget, float and recovery accounting.
- Process-owned per-job leases exclude competing workers and fence stale owners. SQLite releases the OS lock on process death; the next owner must recover existing attempts before new work. There is no timeout-based stealing while an old network call could still be running. These are local-machine leases, not distributed coordination.
- `metal-batch prepare/fund/run/recover/report` assigns distinct clearing wallets, funds them sequentially under a shared funding lock, confirms spendability, then runs jobs concurrently. An unknown deposit stops later funding and cannot be resubmitted. SDK deposits and withdrawals also share a signer ownership lock across job wallets.
- Testnet allocations cannot receive simulated cross-wallet top-ups or become available float merely because local customer settlement completed. Unreturned assets remain allocated in their actual wallet. The batch never automatically withdraws.
- Python, Node bridge and standalone CLI money operations require explicit execution authorization. Recovery that may resubmit an existing SDK invoice also requires `--execute`. Recovery keeps the original quote resource. All engine policies can save redacted evidence with `--output`; receipts are linked to their reservation keys and mandate versions.
- Added controlled tests for contention, stale mandates/owners, process death, separate wallets, uncertain deposits, preserved testnet allocations, and sub-cent release without capture. Extended seeded ledger operations to include death after dispatch authorization.

## Evidence and test results

| Label | Artifact | Supported result |
|---|---|---|
| MEASURED | [Python tests](../bench/results/m2/python-tests.txt) | 162 tests passed; financial adapters are controlled fixtures |
| MEASURED | [Node tests](../bench/results/m2/node-tests.txt) | 27 tests passed, including shared funding ownership and execute guards |
| MOCK | [Controlled proof](../bench/results/m2/controlled-proof.json) | Three concurrent jobs, six receipts; a separate killed process recovers one receipt without a duplicate; eight seeds × 160 accounting operations |
| BLOCKED | [Current local preflight](../bench/results/m2/local-preflight.json) | Local loader finds the RPC and existing signer; RPC check fails and provider origin is unset. Zero purchases and no money moved |
| BLOCKED | [RPC diagnostic](../bench/results/m2/rpc-diagnostic.json) | A single read-only `eth_chainId` request returns HTTP 401; URL shape is valid but current RPC authentication is refused |
| MEASURED | [Heuristic secret scan](../bench/results/m2/secret-scan.json) | No findings or sensitive committed paths in the reported history/working-tree scope; private data excluded |
| BLOCKED | [Earlier authorized attempt](../bench/results/m2/authorized-live-attempt.json) | Historical environment-only check; it did not inspect the already-existing local fallback |

The controlled proof contains its audit-chain head and per-seed heads. Reproduction changes hashes because run IDs and timestamps differ. Test assets and all financial counts in that proof are **MOCK**. Internal verification charges and customer settlement are **SIMULATED**. No external verifier payment, Airwallex capture, fiat/token bridge or model qualification is claimed. Python runtime dependencies and pinned Node dependencies are unchanged.

Saved MOCK audit head: `fc97d27d58c5050f95f3d3cb32a7e1639a895e164a1dc2b42f3e0751b4a2ccda` (73 events).

## Claims now allowed and not allowed

Allowed: the dispatch barrier, local worker ownership, separate wallet orchestration, sub-cent release and the observed controlled recovery/invariant results. All saved controlled receipts reconcile to their ledger reservation.

Not allowed: a newly paid live engine call, real Metal kill/restart recovery, current RPC/provider readiness, funded job wallets, 30–50 live steps, three concurrent Airwallex authorizations, or representative useful inference quality. The earlier standalone real payment remains historical evidence.

The kill switch blocks authorizations that occur after its transaction. A request authorized as `DISPATCHING` may still complete after a halt and must be reconciled. The legacy banked-job adapter is separate from the unified engine barrier. Direct administration of SQLite files is outside the custody/security model.

## Remaining human gates

Repair or replace the sandbox Metal RPC configuration privately (the current request returns HTTP 401), set the provider origin and start the approved local provider/model. Verify chain 63825, the expected funding address, actual clearing-wallet spendability, provider health, quote validity and a total within 0.05 USDZ before the one authorized call. No repeated approval is needed for that same call. Funding deposits and larger paid runs require their own explicit authorization. Stop on any failed check; preserve uncertain invoices. See [M2 runbook](M2_RUNBOOK.md).
