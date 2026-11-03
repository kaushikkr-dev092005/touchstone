# M2 single-call live gate

Status: **BLOCKED / NOT PASSED**.

The user approved exactly one Metal testnet inference purchase on chain 63825 with a maximum aggregate expenditure of **0.05 USDZ including applicable protocol and verification charges**. The approval does not authorize a 30–50-step run or any Airwallex operation. It remains recorded; do not ask for the same approval again.

The environment-only preflight found `METAL_RPC_URL`, `AGENT_PRIVATE_KEY` and `METAL_PROVIDER_URL` absent. Execution stopped before RPC, wallet, balance, provider, quote or fee checks. Zero network requests, purchases and financial operations were dispatched. No invoice, signed receipt or delivery was created. No private configuration or wallet file was read, and no financial control was changed to bypass this blocker.

Evidence: [redacted authorized attempt](../bench/results/m2/authorized-live-attempt.json).

Remaining: make the M2 configuration available privately, verify all required checks and the fee-inclusive cap, then execute the one authorized purchase. The full M2 milestone still needs paid engine evidence and an approved live process-kill/restart recovery demonstrating no duplicate charge. Existing controlled adapter proofs do not establish either live result.
