# M2 single-call live gate

Status: **BLOCKED / NOT PASSED**.

The user approved exactly one Metal testnet inference purchase on chain 63825 with a maximum aggregate expenditure of **0.05 USDZ including applicable protocol and verification charges**. The approval does not authorize a 30–50-step run or any Airwallex operation. It remains recorded; do not ask for the same approval again.

The environment-only preflight found `METAL_RPC_URL`, `AGENT_PRIVATE_KEY` and `METAL_PROVIDER_URL` absent. Execution stopped before RPC, wallet, balance, provider, quote or fee checks. Zero network requests, purchases and financial operations were dispatched. No invoice, signed receipt or delivery was created. No private configuration or wallet file was read, and no financial control was changed to bypass this blocker.

Updated 3 November: that environment-only check missed the existing local fallback. The normal loader now finds the existing wallet key and RPC URL; the current RPC check fails and the provider URL remains unset. See [current preflight](../bench/results/m2/local-preflight.json). No payment was attempted. Implementation and controlled tests are complete; see [M2 report](M2_REPORT.md). The authorized call can also serve as the live `after_rail` crash/recovery proof without purchasing an additional call, once every prerequisite passes.

The targeted RPC diagnostic confirms HTTP **401** on `eth_chainId`, with the URL shape validated and endpoint details hidden. See [diagnostic evidence](../bench/results/m2/rpc-diagnostic.json).

Evidence: [redacted authorized attempt](../bench/results/m2/authorized-live-attempt.json).

Remaining: make the M2 configuration available privately, verify all required checks and the fee-inclusive cap, then execute the one authorized purchase. The full M2 milestone still needs paid engine evidence and an approved live process-kill/restart recovery demonstrating no duplicate charge. Existing controlled adapter proofs do not establish either live result.
