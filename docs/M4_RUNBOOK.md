# M4 matched comparison runbook

**Implementation ready; live gate BLOCKED.** The earlier approval covered exactly one purchase up to 0.05 USDZ. It does not authorize this experiment, funding, withdrawals or upstream hosted usage. Commands work from the repository root in PowerShell and Bash unless specified.

## Prepared experiment

[The proposed plan](../bench/results/m4/proposed-plan.json) uses scope `m4-nov04`, one seed, 16 matched sources per policy and four policies: tools-only, always-cheapest, always-premium and Touchstone's qualified ladder. There are **64 logical policy steps**, not 64 purchases. With no eligible models the ladder buys nothing; the two paid baselines would normally purchase 32 calls. Failed outputs remain charged. The plan permits at most 40 purchases and conservatively reserves service price plus the 0.001 SIMULATED checking fee inside a proposed 2.04 aggregate envelope. This amount is a proposal, not approval.

Source index 3 has a local-provider outage; index 7 has a local-provider quality drop. Both use the same sources and indices for every policy. Premium remains available. Each seller loads the same immutable schedule; readiness checks its hash. A scheduled outage rejects unsigned requests before payment and returns an explicit fault/hash attestation. An already paid request can still deliver its original result. Quality corruption occurs after actual inference and is retained in the cached delivery, with `chaos_mode=quality-drop`.

## Local preparation, no money

To create a new plan, use a fresh output and wallet scope. The command writes public generated sources and a schedule, performs no network request and never reads keys. Optional `--local-profile` and `--premium-profile` arguments accept the raw M3 measurement files. Complete qualification and current provenance are required; missing profiles do not become eligible. Keep the fixed M3 thresholds.

```text
python -m touchstone compare prepare --scope m4-new-scope --aggregate-cap-usdz 2.04 --price-cap-usdz 0.05 --max-purchases 40 --steps 16 --seeds 20261120 --output bench/results/m4/new-plan.json
```

The paired schedule is named `new-plan-seller-schedule.json`. The prepared proposal uses `proposed-plan-seller-schedule.json`. Never overwrite a plan after approval or a partially executed scope. Implementation changes invalidate its fingerprint. To request five seeds, list five distinct integers after `--seeds`; increase the proposed call/budget envelope only with separate approval. A truncated study stays incomplete. The report states n and includes per-seed tables; one seed is not five independent measurements.

## Human configuration gates

The operator starts llama.cpp and both sellers. Configure public model IDs and, for the local qualified ladder, the actual GGUF SHA256 from the M3 profile. Hosted credentials stay in the seller environment. Partner-credit availability/approval is a human gate; the declaration below does not verify the credit balance. Do not paste credentials into commands or the chat.

Local seller, PowerShell:

```powershell
$env:TOUCHSTONE_PROVIDER_ID = 'local-gpu'
$env:TOUCHSTONE_PROVIDER_MODE = 'model'
$env:TOUCHSTONE_PROVIDER_PORT = '8092'
$env:TOUCHSTONE_PROVIDER_SCENARIO_FILE = (Resolve-Path 'bench/results/m4/proposed-plan-seller-schedule.json').Path
python tools/metal.py provider
```

Local seller, Bash:

```bash
export TOUCHSTONE_PROVIDER_ID=local-gpu TOUCHSTONE_PROVIDER_MODE=model TOUCHSTONE_PROVIDER_PORT=8092
export TOUCHSTONE_PROVIDER_SCENARIO_FILE="$PWD/bench/results/m4/proposed-plan-seller-schedule.json"
python tools/metal.py provider
```

In a separate operator shell, premium seller, PowerShell:

```powershell
$env:TOUCHSTONE_PROVIDER_ID = 'hosted-premium'
$env:TOUCHSTONE_PROVIDER_MODE = 'anthropic'
$env:TOUCHSTONE_PROVIDER_PORT = '8095'
$env:TOUCHSTONE_HOSTED_FUNDING_SOURCE = 'PARTNER_CREDITS'
$env:TOUCHSTONE_PROVIDER_SCENARIO_FILE = (Resolve-Path 'bench/results/m4/proposed-plan-seller-schedule.json').Path
python tools/metal.py provider
```

Premium seller, Bash:

```bash
export TOUCHSTONE_PROVIDER_ID=hosted-premium TOUCHSTONE_PROVIDER_MODE=anthropic TOUCHSTONE_PROVIDER_PORT=8095
export TOUCHSTONE_HOSTED_FUNDING_SOURCE=PARTNER_CREDITS
export TOUCHSTONE_PROVIDER_SCENARIO_FILE="$PWD/bench/results/m4/proposed-plan-seller-schedule.json"
python tools/metal.py provider
```

Set `LOCAL_MODEL`, `LOCAL_MODEL_SHA256`, `LOCAL_INFERENCE_URL`, `ANTHROPIC_MODEL` and credentials through the existing local configuration. Both sellers must have the global chaos mode `none`; only the bound schedule injects the experiment's faults. Health identity is seller-reported, not remote hardware attestation.

Provide a dedicated, existing funded clearing scope matching the plan. M4 never generates a wallet, deposits or withdraws. Any required funding needs its own written approval and stated cap. Do not replace an existing funding wallet. A wallet with unrelated historical purchases or a pending invoice is refused.

## Read-only preflight

```text
python -m touchstone compare preflight --plan bench/results/m4/proposed-plan.json --output bench/results/m4/operator-preflight.json
```

The saved [initial preflight](../bench/results/m4/preflight.json) is BLOCKED: the proposed local/premium endpoints did not supply healthy seller records and the dedicated `m4-nov04` wallet does not exist. RPC was not probed after these prerequisites failed; `rpc_chain_63825=false` means unconfirmed, not a new measured wrong-chain finding. Zero payments were sent.

Passing requires the correct seller/model types, schedule hash, chain 63825, partner-credit declaration, an existing wallet with no unresolved invoice, enough clearing spendability and two valid signed quotes. The balance is an operator estimate, not a claim of chain finality. Do not execute if actual additional protocol charges cannot be bounded by the approved cap.

## Paid execution — requires new written approval

Only after setup, passing preflight and a written approval covering the aggregate envelope, maximum purchase count, experimental unqualified baselines and hosted partner-credit usage:

```text
python -m touchstone compare run --plan bench/results/m4/proposed-plan.json --state-dir data/m4 --aggregate-cap-usdz 2.04 --max-purchases 40 --allow-unqualified-baselines --execute --output bench/results/m4/live-report.json
```

`--allow-unqualified-baselines` acknowledges that these fixed experimental policies can buy unqualified model outputs for evaluation. It never changes the ladder's gate. The ladder uses tools first, then a profile-matched eligible local tier, eligible premium, and review. Cheapest selects the lowest currently valid quoted price, not a hardcoded provider.

A durable scope binding, wallet-wide owner, worker lease and existing versioned dispatch transaction protect the run. Every call reserves price plus checking fee before dispatch. The purchase cap counts attempted reservations conservatively, including failed outcomes. Uncertain outcomes retain their reservation and stop every policy. Repeating a complete run does not buy anything; repeating one with a pending invoice is refused. Do not change scope or delete the journal to escape uncertainty. Original invoices, signed receipts and deliveries remain in the existing private SDK store. Recovery is a separate operator action against the original invoice, requiring its applicable execute flag and approval; this runner never automatically recovers or buys a replacement.

Read the saved report without executing:

```text
python -m touchstone compare report --plan bench/results/m4/proposed-plan.json --state-dir data/m4
```

The run directory contains `journal.json`, the ledger, `preflight.json`, `environment.json`, `report.json` and `comparison.md`. Failed calls, orphaned charged attempts, unresolved exposure, raw outputs and the audit head remain visible. Receipt read-back failures produce BLOCKED reconciliation rather than deleting results. No customer capture or Airwallex action occurs.

## Measurement scope

Correctness labels are read only by offline scoring after dispatch. Report both false-accept count/accepted denominator and refusals. Cost per verified-correct step requires an accepted, independently truth-correct output. Unresolved cost leaves that metric null. Provider USDZ, SIMULATED check fees and unmeasured upstream dollars remain separate; any combined demo-rate cost is labelled SIMULATED.

Latency includes quotes, payment/delivery, checking and failed calls. The experiment-only outage-attestation probe is recorded separately and excluded. A reconstructed timing stays null if unavailable. Environment records include code/lock hashes, model identity, buyer runtime/GPU where readable, and explicit unmeasured provider telemetry. Upstream API invoice cost, CPU/electricity and human review remain unpriced.

For one seed the live gate requires complete matched rows and 30–50 paid calls; the multi-seed envelope permits up to 50 times the requested seed count with at least 30 total. Always inspect the actual per-seed counts. It also requires an observed scheduled outage, a paid quality-drop delivery, matched receipt accounting, no pending purchases and zero observed control violations. This gate is not a confidence interval, a proof of no bugs, model qualification or an Airwallex/token bridge.

## Offline reproduction

```text
python -m unittest discover -s tests -v
python tools/metal.py test
python tools/prove_m4.py
```

The last command uses only temporary MOCK adapters. It copies labelled implementation evidence into `bench/results/m4/mock/`; no wallet, provider, credentials or network is used. It cannot pass the live gate.
# Current matched-workload support, 10 November 2026

`python -m touchstone compare prepare` now accepts `--corpus` for a frozen difficult
workload, `--qualification-corpus` for current model provenance, and
`--hosted-credit-cap-usd` for a separate prepaid-credit ceiling. A frozen workload
must use its manifest seed. `bench/results/m4-v2/dataset` was frozen with seed
202611102 before model output; it is separate from the qualification corpus.

The report separates candidates, review and rejected; strictly correct review
drafts; USDZ provider cost per strictly correct output; and published-rate API
credit estimates. Failed calls stay charged. Pending calls retain exposure and
prevent a final unit-cost claim. API billing remains unreconciled. The live runner
refuses missing credit approval or an unpriced hosted model.

No new live comparison is approved or executed. Finish qualification first, then
prepare a fresh plan, verify an existing dedicated wallet and provider readiness,
estimate funding/API costs and obtain specific final approval. Qualification's
caps cannot fund this separate experiment. Historical MOCK reports below are
implementation evidence only. See [current review](REVIEW_20261110.md).

---
