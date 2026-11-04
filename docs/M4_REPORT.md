# M4 implementation report — 4 November 2026

**Implementation complete. Live comparison gate BLOCKED.** No additional testnet purchase, funding, withdrawal or hosted inference was executed. The previous one-purchase approval does not authorize M4.

## What changed

- Added `python -m touchstone compare prepare|preflight|run|report` with matched tools-only, cheapest, premium and qualified-ladder policies. Plans bind generated sources, seeds, policy order, prices/call caps, qualification evidence, fault schedule and implementation hashes.
- Added explicit per-source seller faults at shared indices, isolated to the local tier. An unsigned outage request is rejected before payment with a schedule attestation. The quality drop changes the real paid delivery after inference and remains cached for replay. Provider health exposes schedule/model identity; no dependency changed.
- Reused the existing ledger reservations, version fence, worker ownership, Metal quote/receipt normalization and SDK preservation. Added wallet-wide study ownership across state directories. No deposits, withdrawals, customer capture or automatic uncertain-payment retry occurs.
- Added independent offline truth scoring, false-accept denominators, refusals, cost per verified-correct output, latency p50/p95, per-seed breakdowns, failed/unfinished-call accounting and an environment manifest. Unknown exposure and missing timings remain explicit. The ladder does not spend on missing or mismatched model qualification.
- Added controlled tests for cap/approval refusal, paired faults, actual cheapest selection, unqualified abstention, qualified escalation, false accepts, incomplete charges, unknown-payment restart, scope ownership and immutable terms.

## Evidence

| Label | Artifact | Result supported |
|---|---|---|
| SIMULATED / BLOCKED | [Proposed plan](../bench/results/m4/proposed-plan.json), [seller schedule](../bench/results/m4/proposed-plan-seller-schedule.json) | One seed, 16 sources per policy, 64 logical steps; proposed maximum 40 purchases and 2.04 aggregate envelope; no approval inferred |
| BLOCKED | [Read-only preflight](../bench/results/m4/preflight.json) | Proposed endpoints unavailable/unverified; dedicated M4 wallet absent; RPC prerequisite not reached; zero payments |
| MOCK | [Controlled proof](../bench/results/m4/mock/proof.json), [raw results](../bench/results/m4/mock/report.json), [table](../bench/results/m4/mock/comparison.md) | 32 controlled purchases, 64 completed policy steps, zero duplicate calls on repeat and zero observed control violations |
| MOCK | [Environment](../bench/results/m4/mock/environment.json) | Code/lock/runtime provenance for the controlled run, explicitly unmeasured model/GPU values |
| MEASURED | [Test summary](../bench/results/m4/tests.json) | Full Python and pinned Node test results; financial tests use controlled adapters |

The controlled adapter emits generated expected outputs, plus the scheduled corruption. Its correctness/price/latency numbers are not measured model performance or savings. The study has **n=1**, not five seeds. The separate simulator benchmark is retained in its existing files.

Provider USDZ service amounts and internal SIMULATED checking fees are distinct. Upstream hosted dollar cost/credit balance, CPU, electricity and human review are unmeasured. The combined cost field is a SIMULATED demo-rate calculation. Airwallex fiat is not used or converted to USDZ. No model threshold changed and no provider became qualified through this experiment.

## Tests and audit

The full suite passes **189 Python tests and 34 Node tests**, including 12 M4 Python cases and two new Node schedule cases. All M4 calls in those tests are MOCK. The saved controlled audit head is printed in `mock/proof.json`; IDs/timestamps cause a new head on reproduction. No runtime dependency was added; existing Node versions remain pinned and locked.

## Claims allowed

Allowed: a guarded matched comparison implementation, shared fault scheduling, qualification-based abstention, separate cost ledgers, independent offline scoring and controlled proof of no duplicate purchases on a completed restart. The saved read-only check supports the stated configuration blockers only.

Not allowed: completion of M4's live gate, real model accuracy or savings, 32 real purchases, a live outage/quality-drop measurement, independent seller hardware attestation, real customer capture or a fiat/token bridge.

## Needed from the operator

Start and configure the local model and both sellers with the prepared schedule. Supply a dedicated funded M4 clearing wallet under separately approved funding terms. Supply any current M3 qualification profiles; absent profiles correctly keep the ladder at tools/review. Confirm hosted partner-credit availability and approval. Then provide a new written aggregate purchase cap and maximum call count; the proposed 2.04/40-call envelope is awaiting approval.

The [runbook](M4_RUNBOOK.md) contains exact commands, PowerShell/Bash setup and the uncertainty stop procedure. M1/M2 live gates and manual portal/video/submission steps remain unproven or human-controlled; M4 implementation does not close them.
