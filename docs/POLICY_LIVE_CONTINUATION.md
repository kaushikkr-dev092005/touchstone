# Live policy comparison continuation, 12 November 2026

The live comparison is now **complete: 64/64 outcomes across 16 matched sources**,
with **32 actual paid Metal testnet receipts**, 10 confirmed-unpaid failures and
22 outcomes requiring no purchase. The original 12 outcomes were preserved; the
continuation added the missing 52. A separate local-model study with simulated
payments remains separate and was not used to complete this live comparison.

[Actual financial results](../bench/results/m4-live-20261112/actual-financial-results.json)
· [Raw outcomes](../bench/results/m4-live-20261112/live-report.json)
· [Current clearing balance](../bench/results/m4-live-20261112/clearing-balance.json)

| Policy | Outcomes | Strict correct | Actual provider USDZ | USDZ / strict correct |
|---|---:|---:|---:|---:|
| Tools only | 16/16 | 1/16 | 0 | 0 |
| Always cheapest | 16/16 | 3/16 | 0.073390 | 0.024463 |
| Always premium | 16/16 | 7/16 | 0.130000 | 0.018571 |
| Touchstone ladder | 16/16 | 3/16 | 0.060000 | 0.020000 |

Premium produced more strictly correct drafts and lower provider cost per correct
draft than the ladder in this workload. The ladder spent less in total and avoided
model purchases for known duplicates; that does not establish a general savings or
quality win. There were zero false accepts. Failed requests count as incorrect.
One small synthetic corpus is not a real-world invoice accuracy estimate.

Total comparison provider spend is **0.263390 USDZ**, including charged incorrect
answers. Continuation spend was **0.238390 USDZ**, with no new funding, retry,
withdrawal, bank operation or cash purchase. The original wallet retains **0.286610
USDZ**, an operator spendability estimate rather than independently finalized clearing.

Across qualification, integration and comparison, reported-usage API estimates total
**$2.202341**; retained uncertainty allowances are **$2.027200**. Conservative exposure
is therefore **$4.229541 / $4.50**. Newly reported continuation usage is **$0.190424**.
API billing remains independently unreconciled; unknown usage was not silently zeroed.

All measured completion controls pass, including 32 actual paid receipts, matched
receipt accounting, no pending invoice, a valid audit and the credit ceiling. The
original runner's fault-telemetry flag remains false: failed outage requests lost
their probe field during reconciliation, and extra local-model metadata was omitted
by the ledger allowlist. The final financial report supplements that telemetry with
a separately timed **post-run read-only outage attestation**, plus metadata restored
from the exact cached paid quality-drop delivery. No answer, charge or score changed;
no model was rerun. The raw flag and supplemental timing remain visible.

`tools/run_live_policy.py` is the live-only entrypoint that installs the unsigned
fresh-context wait before invoking the bound runner. It requires the exact approved
plan and `--execute`; it never launches the demo. Reopening this completed scope
returns its cached report without dispatching another purchase.

The local mandate initially expired before the first new purchase. Its continuation
copy received one audited, one-hour local renewal under the approved scope. The
original journal and all monetary limits stayed unchanged. Fresh-epoch waiting
repeats only unsigned context GETs; POST payments and inference requests are never
retried. A unit check verifies that transport boundary. The measured GPU peak was
60 C, below the 75 C stop; the owned model was stopped after completion.

The user raised the total Claude ceiling from $3 to **$4.50**, including all earlier
estimated usage and uncertainty allowances. The current conservative exposure is
$2.919117. Free token counts for the remaining sources estimate a maximum additional
$1.030268 for up to 27 hosted requests, for $3.949385 total conservative exposure.
These remain estimates, not independently reconciled API billing.

The original wallet reports 0.525 USDZ spendable, three historical payments and no
pending invoice. RPC chain 63825, current clearing admission, original model identity,
both real seller health records and signed quotes were checked without payment.
The local model is supervised at a 65 C start refusal and a 75 C stop; it does not
restart automatically after a thermal stop.

`tools/continue_policy_live.py` binds the exact remaining workload to a reviewable
approval plan. It carries the original outcomes and hash-chained ledger into a
separate continuation journal, keeps the original wallet and fault schedule, and
changes only the comparison's prepaid-credit allowance. The ladder's qualification
gate stays unchanged. Qwen remains an experimental, unqualified paid baseline;
Sonnet remains the qualified hosted tier.

The continuation permits at most 39 new purchase attempts, 27 hosted calls and
0.39 USDZ of provider charges within the existing original aggregate/per-call caps.
It creates or funds no wallet, retries no request, purchases no credits, and performs
no top-up, withdrawal or bank operation. Unknown outcomes stop dispatch. A proven
unpaid request is counted as incorrect and never requested again.

The original runner retains separately labelled hypothetical checking fees in its
raw ledger/report. They are excluded from actual cost metrics by
`tools/finalize_policy_live.py`. That finalizer also requires at least 30 actual
paid receipts for the live gate; an attempted or voided payment is not a paid call.
No simulated rail is permitted in the continuation.

Execution required `--execute` and the exact final approval phrase in
`bench/results/m4-live-20261112/continuation-plan.json`, as requested by the user's
earlier instruction to report zero-cost checks before obtaining final paid approval.
The raised ceiling alone does not remove that requirement.
