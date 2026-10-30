# Touchstone — submission draft

## One sentence

Touchstone controls an agent's inference purchases within a customer mandate, verifies outputs, recovers paid deliveries and accounts for failed calls.

## Problem and approach

Agents can buy a cheap answer that is wrong, pay again after a timeout, or confuse a customer's authorization with available operating cash. Touchstone separates these decisions. Bounded tools handle supported calculations without a model purchase. Provider evidence screening rejects unqualified model/task combinations. Financial controls reserve an exact quote within approved limits before dispatch. Every paid attempt remains an expense, including answers rejected by the verifier.

The financial stress scenario uses three customer holds totaling $2.50 with only $1.50 operator float. It demonstrates limited allocations, price and latency changes, review/policy pauses, kill/resume, charged failures, partial closure and reconciliation. This multi-job scenario is explicitly simulated.

## What has actually run

- A real Metal chain-63825 RPC connection and faucet-funded dedicated wallet.
- A 0.10 testnet USDZ clearing deposit and one 0.01 testnet USDZ x402 inference purchase through the supported SDK.
- Local GPU inference, a signed preconfirmed receipt, identical cached replay and original delivery retrieval using the paid receipt.
- Rejection of the purchased model's incorrect arithmetic answer, with the charge retained.
- Airwallex sandbox authentication and balance/Global Account reads.
- Two local model profiles, an honest negative cheap-first cost result, a 1,000-case bounded-tool baseline, and a source-deduplicated eligibility screen.
- Local failure tests for lost payment/capture responses, changed mandates, receipt mismatches, uncertain outcomes and unavailable withdrawal float.

The actual Airwallex hold/capture is blocked by a merchant `configuration_error`. The integrated workflow is implemented and tested with controlled adapters, but the full external banking loop is not yet demonstrated. Unused testnet float has not been confirmed returned. Keep these limits visible in the final submission unless later evidence supersedes them.

## Differentiation

The product's decision is whether an inference purchase is warranted, not just which provider has the lowest price. It connects output quality to an explicit financial trail while preserving the difference between authorization, operator liquidity, a preconfirmed receipt and returned funds.

## Demonstration

Run `python -m touchstone serve` and open `http://127.0.0.1:8088`. Show the local-tool/review preview, then the financial stress scenario. Open the real testnet evidence panel and explain that the purchased answer failed verification. Finish with the banked-job journal and the precise Airwallex merchant blocker. Use `docs/DEMO_SCRIPT.md` for timing and `docs/VALIDATION.md` for evidence boundaries.

## Required work before submitting

Resolve sandbox merchant configuration and record actual authorization/capture; qualify a model on representative finance-operations sources if claiming useful autonomous inference; verify finality of the paid inference receipt; confirm the signed-in hackathon submission requirements; add the team details and video URL. The testnet withdrawal has returned; the repository has been pushed privately to `https://github.com/kaushikkr-dev092005/touchstone`; public publication and hackathon submission have not been performed.
