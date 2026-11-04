# M4 policy comparison

**MOCK** · complete=True · n=1 seeds

USDZ service spend and SIMULATED micro-USD check fees are separate. Upstream API dollars, CPU and human review are unpriced.

| Policy | Steps | Verified correct | Refusals | False accepts / accepted | Provider USDZ | USDZ / verified correct | Demo check USD | p50 / p95 ms |
|---|---:|---:|---:|---|---:|---|---:|---|
| tools-only | 16 | 3 | 13 | 0 / 3 | 0.000000 | 0.000000 | 0.000000 | 0 / 1 |
| always-cheapest | 16 | 8 | 8 | 0 / 8 | 0.170000 | 0.021250 | 0.016000 | 60 / 73 |
| always-premium | 16 | 8 | 8 | 0 / 8 | 0.320000 | 0.040000 | 0.016000 | 63 / 89 |
| touchstone-ladder | 16 | 3 | 13 | 0 / 3 | 0.000000 | 0.000000 | 0.000000 | 0 / 1 |

Pending: 0; control violations: []; audit head: `a25f6eabf11222e1a7d5eda9c8d8dfcdce348fa6d7323630a09e735c159bc821`.

Raw failures and unresolved exposure remain in report.json and the ledger. No null metric is a measured zero.
