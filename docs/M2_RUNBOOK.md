# M2 operator runbook

**5 November: the approved single-call proof is complete; do not rerun its funding or purchase.**
See [M2 current evidence](M2_REPORT.md) and [final redacted result](../bench/results/m2/live-single-call-final.json).
Both the one-purchase approval and separate deposit approval are consumed.
Scope `m2-live-single-20261105` retains one rejected paid invoice and 0.01 USDZ of
operator-estimated spendability. Recovery-only uses the same scope:

```text
python -m touchstone metal-batch recover --scope m2-live-single-20261105 --integration-probe --execute
```

This is recovery of the original invoice, not permission for another purchase.
The dedicated probe policy requires seller ID `metal-provider`; the ordinary
M3/M4 launcher uses `local-gpu`. Keep the saved provider identity and origin when
recovering. Do not change policy to overcome an incompatible seller.

## Historical runbook — commands below are not new authorization

The user approved **exactly one** inference purchase on Metal testnet chain **63825**, maximum aggregate expenditure **0.05 USDZ including protocol and verification charges**. This is not approval for deposits, withdrawals, extra calls or a 30–50-step trial. The call can be used for the requested `after_rail` crash/recovery demonstration without buying a second call.

Current state: **BLOCKED**. The existing funding key and RPC configuration load locally, but the RPC check fails and no provider URL is configured. No transaction was executed. Earlier environment-only checks missed the existing wallet fallback; do not generate a replacement funding wallet. See [preflight evidence](../bench/results/m2/local-preflight.json).

## Local configuration and preflight

Commands below run from the repository root. They work in PowerShell and Bash unless stated otherwise. Never echo keys or authenticated RPC URLs. The normal loader resolves process environment first, then `data/local-config.json`, then the existing `data/metal/funding-wallet.json`. `TOUCHSTONE_IGNORE_LOCAL_CONFIG=1` deliberately disables local-file loading in tests/CI; it must not be used to diagnose real setup readiness.

After the operator repairs the RPC and starts the local model and seller:

```text
python -m touchstone rpc-smoke
python -m touchstone metal-funding
python -m touchstone engine-metal --scope funded-proof-001 --steps 1 --budget-usd 0.05 --price-cap-usd 0.049 --provider-url http://127.0.0.1:8092 --quote-only
```

`metal-funding` checks the EVM funding wallet. It does not establish clearing-wallet spendability. Inspect the existing clearing scope's balance read-only with the adapter before executing. Preserve its identity and prior purchase history. A missing or insufficiently funded clearing wallet is a blocker, not authorization to deposit. Provider health must explicitly pass on testnet and its quote must bind the requested task, seller, network, asset and clearing deployment. Do not execute if protocol fees cannot be bounded within the cap.

The engine reserves provider price plus a fixed 0.001 internal checking charge; that checking charge is **SIMULATED**, not an external verifier bill. The 0.049 per-call cap leaves room for it within 0.05. Account separately for any additional actual protocol charge before dispatch. No Airwallex operation participates in this proof.

## One authorized paid call and recovery

Only after every preflight check passes and the existing clearing scope is confirmed usable:

```text
python -m touchstone engine-metal --scope funded-proof-001 --steps 1 --budget-usd 0.05 --price-cap-usd 0.049 --provider-url http://127.0.0.1:8092 --execute --kill-at after_rail
python -m touchstone engine-metal --scope funded-proof-001 --steps 1 --budget-usd 0.05 --price-cap-usd 0.049 --provider-url http://127.0.0.1:8092 --execute --recover --output bench/results/m2/live-single-call.json
```

The first command intentionally exits 86 after the adapter has persisted its signed receipt/delivery. The second reconciles the original reservation; it does not run another task. Keep scope, task inputs, policy and caps identical. If this scope already has different engine terms, stop and review those terms locally; do not replace or overwrite its journal. If either result is unknown, retain the invoice and reservation and stop. Do not rerun execution with a new scope to escape uncertainty.

The SDK retains the original invoice, signed receipt and delivery in the private job wallet store. Saved engine JSON contains redacted accounting links and verification results. Confirm exactly one newly paid invoice, unchanged receipt on repeated recovery, matching amount/quote/provider/reservation, no unresolved attempts and a valid audit-chain head. A rejected answer still counts as paid spend and is not permission to purchase a replacement.

## Sequential funding and concurrent jobs

These commands show the implemented multi-job path. They are **not authorized for live execution** by the single-call cap. Obtain explicit deposit and purchase caps first. `prepare` is local accounting only; customer mandates remain **SIMULATED**.

```text
python -m touchstone metal-batch prepare --scope m2-parallel-example --integration-probe --jobs 3 --steps 2 --wallet-budget-usd 0.04 --price-cap-usd 0.01 --aggregate-cap-usd 0.12
python -m touchstone metal-batch fund --scope m2-parallel-example --integration-probe --execute
python -m touchstone metal-batch run --scope m2-parallel-example --integration-probe --execute --output bench/results/m2/live-parallel.json
python -m touchstone metal-batch run --scope m2-parallel-example --integration-probe --execute --recover --output bench/results/m2/live-parallel-recovered.json
```

Funding finishes one distinct wallet before starting the next. A persisted uncertain deposit is checked for spendability without resubmission. No job runs until every wallet is marked funded. Purchases then run concurrently across job wallets, with one owner per job and SDK wallet. The aggregate cap bounds allocated USDZ; internal check charges consume each job budget. Funding transfers, native gas and purchases need appropriate written authorization separately. Actual withdrawals require separate approval and never happen automatically here. Completed jobs retain unreturned testnet allocation; no simulated return can fund another wallet.

## Reproduce offline implementation evidence

PowerShell:

```powershell
$env:TOUCHSTONE_IGNORE_LOCAL_CONFIG = '1'
python -m unittest discover -s tests -v
python tools/metal.py test
python tools/prove_m2.py
```

Bash:

```bash
export TOUCHSTONE_IGNORE_LOCAL_CONFIG=1
python -m unittest discover -s tests -v
python tools/metal.py test
python tools/prove_m2.py
```

These controlled runs use temporary stores and **MOCK** adapters. They do not fund or read real wallets, qualify an inference model, or pass the live M2 gate. The printed audit head belongs to the saved controlled proof.
