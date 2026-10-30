# Simulator benchmark

Synthetic provider quality and estimated latency; these are not GPU/model or live-payment measurements.

Median across seeds [41, 42, 43, 44, 45], 200 tasks per seed. Costs include failed calls and verification.

| Policy | Cost USD | True success | USD / true-correct step | Estimated p95 ms | Retries | Calibration MAE |
|---|---:|---:|---:|---:|---:|---:|
| always-premium | 10.200 | 99.5% | 0.0513 | 360 | 0 | 0.000 |
| always-cheapest | 2.200 | 80.5% | 0.0137 | 980 | 0 | 0.000 |
| touchstone | 6.162 | 100.0% | 0.0308 | 1340 | 42 | 0.000 |

Verifier: `source-rules-v2`. Classification uses bounded source-evidence rules; unknown or ambiguous sources require review. These synthetic templates are within its supported scope. This does not establish semantic accuracy on arbitrary customer text.

The original membership-only baseline is retained in baseline-v1/. No cost or quality target was tuned to force a winning result.

Regenerate: `python -m touchstone benchmark`.
