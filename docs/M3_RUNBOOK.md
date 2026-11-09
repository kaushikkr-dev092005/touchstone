# M3 invoice-extraction runbook

All commands run from the repository root. Python commands below work in PowerShell and Bash.
The two saved local profiles each contain 180 measured calls and failed qualification.
Profiles whose code hashes differ from the current implementation must be remeasured;
historical results do not qualify the current seller. No eligibility threshold is relaxed.
Nothing in the dashboard dispatches this workload automatically.

## Reproduce the no-payment evidence

```powershell
python tools/m3.py build
python tools/prove_m3.py
python -m unittest discover -s tests -v
python tools/metal.py test
```

`build` freezes the deterministic 180-source corpus and runs only the tool baseline. `report` repeats offline scoring of profiles under `bench/results/m3/profiles/`. Neither command contacts models or payments. `prove_m3` uses MOCK adapters in temporary directories, with networking forbidden. Financial proof amounts are mock USDZ, and checker charges are simulated.

## Local model measurements — operator starts each model

In one terminal, start only the requested tier:

```powershell
python tools/run_local.py --tier economy --ctx-size 8192
```

In a second terminal:

```powershell
python tools/m3.py profile-local --tier economy --partition calibration --max-calls 120
python tools/m3.py profile-local --tier economy --partition holdout --max-calls 60
python tools/m3.py report
```

Stop that model, then repeat with `balanced` in both terminals. Do not start it over an existing model. The larger context is a requested configuration, not a claim it fits: profiling stops if GPU telemetry is unavailable or less than 20% of VRAM remains free. The running model path and GGUF hash must match `.tools/models/<tier>-manifest.json`. A 3B tier remains BLOCKED until a separate 4-GB fit/headroom proof exists; this command does not enable it.

Profiles append calibration and held-out responses in the same tier file, skipping IDs already recorded. Preserve stale profiles separately when changing code/model/prompt; a provenance mismatch refuses to append. Do not tune using the held-out labels. Sources and labels are synthetic and public repository artifacts; “offline truth” means labels are excluded from requests and online checks, not secret benchmark data.

## Hosted premium seller — configuration, no purchase

For a masked local setup window, run `python tools/configure_hosted.py`. This checks
model metadata only, saves the existing hosted tier's settings privately, and can
start services when the operator selects that option. It makes zero inference
purchases. Account-wide keys may also require `ANTHROPIC_WORKSPACE_ID`.

The existing Anthropic Messages adapter is the sole hosted premium tier. It uses the same x402 resource binding and source schema as the local seller. The adapter's structured-output format follows the [official Anthropic documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs). Compatibility, credentials and partner credits have not been tested with an API call.

Supply `ANTHROPIC_API_KEY` privately in the seller's environment; do not paste or put it in a tracked file. Configure the model ID and partner-credit declaration, then start the existing seller:

PowerShell:

```powershell
$env:TOUCHSTONE_PROVIDER_MODE = 'anthropic'
$env:TOUCHSTONE_PROVIDER_ID = 'hosted-premium'
$env:TOUCHSTONE_PROVIDER_PORT = '8093'
$env:TOUCHSTONE_HOSTED_FUNDING_SOURCE = 'PARTNER_CREDITS'
python tools/metal.py provider
```

Bash:

```bash
export TOUCHSTONE_PROVIDER_MODE=anthropic
export TOUCHSTONE_PROVIDER_ID=hosted-premium
export TOUCHSTONE_PROVIDER_PORT=8093
export TOUCHSTONE_HOSTED_FUNDING_SOURCE=PARTNER_CREDITS
python tools/metal.py provider
```

Set `ANTHROPIC_MODEL` privately to the intended model ID in that shell. Seller `/health` reports configured identity and funding declaration only; it does not prove working API credentials or available credits. The buyer never receives the hosted credential. This is an inference-service purchase, never authorization to pay the underlying invoice.

## Paid profiling — NOT CURRENTLY AUTHORIZED

First obtain written approval for a new M3 aggregate USDZ expenditure, inclusive of all fees, and a maximum call count. The M2 single-call allowance does not cover this study. Any funding deposit needs separate approval; the profiler requires an already-existing, confirmed funded clearing wallet and never generates/funds a replacement. Keep Airwallex accounts entirely separate.

Prepared command shape (replace every placeholder only after approval; not an instruction to execute now):

```text
python tools/m3.py profile-paid --wallet-scope APPROVED_SCOPE --provider-origin http://127.0.0.1:8093 --partition calibration --max-calls APPROVED_CALL_COUNT --budget-usdz APPROVED_AGGREGATE_CAP --price-cap-usdz APPROVED_SINGLE_PRICE_CAP --execute
```

The single price cap plus the fixed simulated checking charge must fit inside the aggregate allocation. For optional reference extraction add `--reference-scope DISTINCT_APPROVED_SCOPE --reference-budget-usdz APPROVED_REFERENCE_ALLOCATION`. That allocation is inside the total, not extra. Primary and reference purchases both consume `--max-calls` (maximum 180 per invocation/scope). A reference is requested only on an ambiguous/review result; agreement is not proof of independence or universal correctness.

To collect the held-out partition use a different approved wallet scope/cap and `--partition holdout --max-calls 60`; results merge into the default hosted profile only if provenance and model identity match, and previously bought source IDs are refused. Approval must cover the combined calibration and held-out scopes and any references. Each scope's terms are immutable. Approvals are human gates, not inferred from CLI flags.

The paid profiler records quote-bound reservation keys, receipt IDs, output, model/usage metadata, check charges, audit heads, and pending accounting in its output and ignored local ledger. Original invoices, signed receipts and deliveries remain in the Metal wallet's existing journal. An uncertain payment preserves its reservation and blocks a repeated invocation; it is never automatically retried or replaced. Use the M2 recovery procedure only with the original invoice and appropriate authorization. A stopped study cannot qualify a model. The profile's provider-reported latency covers inference only; upstream API dollar cost is UNMEASURED, even with declared partner credits.

After measurements, run `python tools/m3.py report`. The unchanged Wilson screen uses calibration sources only; all 120 calibration and all 60 held-out cases are required. The separately reported held-out exact-match threshold is 95% with zero false accepts. No demo-tier relaxation is enabled. Passing remains offline evidence and does not itself authorize a purchase, customer capture, banking action or representative business claim.
