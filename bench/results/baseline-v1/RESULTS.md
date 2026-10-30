# Simulator benchmark

Synthetic provider quality and estimated latency; these are not GPU/model or live-payment measurements.

Median across seeds [41, 42, 43, 44, 45], 200 tasks per seed. Costs include failed calls and verification.

| Policy | Cost USD | True success | USD / true-correct step | Estimated p95 ms | Retries | Calibration MAE |
|---|---:|---:|---:|---:|---:|---:|
| always-premium | 10.200 | 99.5% | 0.0513 | 360 | 0 | 0.000 |
| always-cheapest | 2.200 | 80.5% | 0.0137 | 980 | 0 | 0.070 |
| touchstone | 5.833 | 86.0% | 0.0335 | 980 | 26 | 0.120 |

The classification checker validates label membership only, so accepted and truly correct outputs differ. No cost or quality target was tuned to force a winning result.

Regenerate: `python -m touchstone benchmark`.
