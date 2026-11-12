# Isolated policy study (frozen M4 workload)

**Labels:** model outputs MEASURED · call latency MEASURED · payments SIMULATED (mock rail) · prices ASSUMED · verification fee SIMULATED. Not a funded or live run; separate from the live M4 comparison.

**Progress:** 64/64 finished (64 completed, 0 failed with cost) · 0 censored by policy · 0 not started · state **COMPLETE** · complete pairs 16/16


| Policy | n/N | Censored |
|---|---:|---:|
| tools-only | 16/16 | 0 |
| always-cheapest | 16/16 | 0 |
| always-premium | 16/16 | 0 |
| touchstone-ladder | 16/16 | 0 |

## MEASURED outputs, SIMULATED payments — metrics on 16 complete pairs

| Policy | True success (accepted and correct) | Strictly correct outputs (incl. review drafts) | Assumed USD total | Assumed USD / true-correct | p95 ms | Escalations | False accepts | Provider failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| tools-only | 6.2% (1/16) | 1/16 | 0.0000 | 0.0000 | 0 | 0 | 0 | 0 |
| always-cheapest | 0.0% (0/16) | 0/16 | 0.1760 | undefined | 13885 | 0 | 0 | 0 |
| always-premium | 6.2% (1/16) | 7/16 | 0.3360 | 0.3360 | 3067 | 0 | 0 | 0 |
| touchstone-ladder | 6.2% (1/16) | 6/16 | 0.3200 | 0.3200 | 33504 | 10 | 0 | 0 |

## Uncertainty (paired bootstrap, 10,000 resamples, 95% interval)

| Reference vs other | Only reference correct | Only other correct | Δ true success | Δ assumed USD per step |
|---|---:|---:|---|---|
| touchstone-ladder vs tools-only | 0 | 0 | +0.000 [+0.000, +0.000] | +0.0200 [+0.0120, +0.0280] |
| touchstone-ladder vs always-cheapest | 1 | 0 | +0.062 [+0.000, +0.188] | +0.0090 [+0.0010, +0.0170] |
| touchstone-ladder vs always-premium | 0 | 0 | +0.000 [+0.000, +0.000] | -0.0010 [-0.0090, +0.0070] |

No winner declared; see per-policy metrics, paired counts and intervals. With 16 pairs from one frozen synthetic corpus, an interval that includes zero is not evidence of a difference.

Sessions: 5 · interruptions: 4 · resumes: 4 · ledger audit valid: True · pending attempts: 0 · rail receipts 52 = ledger payments 52.

Models: economy: Qwen/Qwen2.5-0.5B-Instruct-GGUF Q4_K_M sha256 74a4da8c9fdbcd15…; balanced: Qwen/Qwen2.5-1.5B-Instruct-GGUF Q4_K_M sha256 6a1a2eb6d15622bf… · llama.cpp b12000.

tools, then economy, then balanced on verifier rejection or provider failure. Qualification gate NOT applied in this mock-rail study; it remains enforced on the live path.
