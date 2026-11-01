# Paired local model profile replay

Actual model outputs and call timings; assumed procurement prices; no financial payments.

| Policy | True success | Assumed USD total | Assumed USD / true-correct | Replayed p95 ms | Escalations |
|---|---:|---:|---:|---:|---:|
| always-economy | 22.2% | 0.990 | 0.0495 | 620 | 0 |
| always-balanced | 48.9% | 1.890 | 0.0430 | 410 | 0 |
| verify-then-escalate | 50.0% | 2.460 | 0.0547 | 681 | 70 |

Same paired model outputs and seeds. Online source checks choose escalation; private truth scores decisions afterward. Actual call latency is replayed, not newly measured concurrent service latency. Model prices are assumptions.

This is a narrow synthetic-source experiment, not a general invoice/OCR benchmark or a funded x402 run. Raw profiles retain model hashes, runtime version, GPU telemetry, outputs and per-call latency.
