# M4 policy comparison

**MEASURED** · complete=True · n=1 seeds

USDZ service spend, published-rate API credit estimates and SIMULATED micro-USD check fees are separate. API billing is not reconciled. CPU and human review are unpriced.

| Policy | Steps | Verified correct | Refusals | False accepts / accepted | Provider USDZ | USDZ / verified correct | Demo check USD | p50 / p95 ms |
|---|---:|---:|---:|---|---:|---|---:|---|
| tools-only | 16 | 1 | 15 | 0 / 1 | 0.000000 | 0.000000 | 0.000000 | 0 / 6 |
| always-cheapest | 16 | 1 | 15 | 0 / 1 | 0.073390 | 0.073390 | 0.013000 | 19792 / 21896 |
| always-premium | 16 | 1 | 15 | 0 / 1 | 0.130000 | 0.130000 | 0.013000 | 20668 / 25896 |
| touchstone-ladder | 16 | 1 | 15 | 0 / 1 | 0.060000 | 0.060000 | 0.006000 | 9027 / 23324 |

Pending: 0; control violations: []; audit head: `7ce5c2ef2caa90ac95c77c6b45df986aa673ff0290309b6b379029eae1540882`.

Raw failures and unresolved exposure remain in report.json and the ledger. No null metric is a measured zero.

| Policy | Strictly correct outputs | Correct review drafts | Candidate / review / rejected | USDZ / strict correct | API credit estimate USD |
|---|---:|---:|---|---|---|
| tools-only | 1 | 0 | 1 / 15 / 0 | 0.0 | 0.0 |
| always-cheapest | 3 | 2 | 1 / 10 / 5 | 0.024463333333333333 | UNMEASURED |
| always-premium | 7 | 6 | 1 / 12 / 3 | 0.018571428571428572 | UNMEASURED |
| touchstone-ladder | 3 | 2 | 1 / 13 / 2 | 0.02 | UNMEASURED |

A strictly correct review draft still requires human review. Every charged failure remains in both cost denominators; unresolved costs are lower bounds.
