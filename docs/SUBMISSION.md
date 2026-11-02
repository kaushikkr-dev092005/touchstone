# Touchstone — submission draft

## One sentence

Touchstone buys inference only when bounded tools cannot resolve a task, verifies the paid result, recovers its receipt and records failed-call cost without charging beyond a mandate.

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
- A unified engine-facing Metal tier, queue-priced signed quotes, provider outage/quality chaos switches, and an abrupt process-kill recovery command. A quote-only live preflight and no-payment outage were exercised; there is still no paid engine run, quality-drop run or live kill/restart.
- A separate Airwallex treasury path for wallet balances, FX quotes/conversions with unique request IDs, and wallet-history spend reconciliation; no live quote or conversion has been attempted.
- An invoice consistency verifier using cited line arithmetic and a measured synthetic false-accept curve for a deliberately noisy checker.

The actual Airwallex hold/capture is blocked by a merchant `configuration_error`. The latest read-only smoke has `account_context_configured=false`; hosted Checkout Sessions and FX access remain untested. The integrated workflow is implemented and tested with controlled adapters, but the full external banking loop is not yet demonstrated. No 30–50-step paid engine run, paid quality-drop run or real Metal kill/restart has been executed; the live outage check spent nothing. The unused 0.09 testnet USDZ was returned through a finalized non-deferred claim; the paid receipt remains preconfirmed. Keep these limits visible in the final submission unless later evidence supersedes them.

## Differentiation

The product's decision is whether an inference purchase is warranted, not just which provider has the lowest price. It connects output quality to an explicit financial trail while preserving the difference between authorization, operator liquidity, a preconfirmed receipt and returned funds.

## Kit fit and claim boundary

The current three-job scenario maps to the official **Kit 12: Inference Sourcing Agent**: three concurrent jobs, $2.50 in holds, $1.50 in float, provider rerouting, and asking before exceeding a hold. The official guide labels **Kit 11** as x402 Business Agents, which instead requires separate sourcing/support/treasury agent mandates, signed customer orders, a dispute/refund path and treasury settlement. Touchstone does not yet implement that separate mandate/refund workflow, so do not claim Kit 11 based only on the three-job simulation. See the [current starter-kit guide](https://airwallexdev.com/guide).

## Demonstration

Run `python -m touchstone serve` and open `http://127.0.0.1:8088`. The first card is the historical real $0.01 USDZ GPU purchase: source total 2,000 cents, paid model output 1,250, verifier rejection, identical replays, and no customer capture. Then show the code-only planner and clearly labeled simulated three-policy stress test. The dashboard's simulator approval flow changes only a versioned local mandate and uses no new real funds. Finish with the Airwallex readiness blocker. Use `docs/DEMO_SCRIPT.md` for timing and `docs/VALIDATION.md` for evidence boundaries.

## Priority gates from the current review

1. Set the sandbox account ID and FX Conversion Write scope, then perform one explicitly approved small conversion and reconcile it against Airwallex wallet history. Do not wait on card-acquiring configuration for this treasury proof.
2. Configure a local small-model provider and a hosted premium provider with partner credits; configure a separate Metal origin for each live tier and approve an aggregate testnet budget before running policy measurements. The present dashboard table remains simulator-only.
3. Ask the sponsor whether sandbox Developer MCP/CLI usage qualifies as “Airwallex tooling.” The official AgentOS MCP and skills use production connectors, and no production account approval is available in this environment.
4. Keep the Kit 11 claim separate: the official guide labels this three-job scenario Kit 12; Kit 11 requires agent mandates, signed orders, dispute/refund handling and treasury settlement.

## Additional submission checklist

Before submission, set the Airwallex account context and verify Checkout Sessions/FX read and write scopes; exercise hosted authorization/capture and a small FX conversion/report; execute 30–50 testnet engine steps plus the chaos and kill/restart demonstrations only with an explicitly approved funded budget; qualify a model on representative finance-operations sources if claiming useful autonomous inference; verify finality of the paid inference receipt; and confirm the signed-in submission requirements. MIT license is included. Freeze features by 11 November, record on 12 November and submit by 13 November. The testnet withdrawal has returned. The repository `https://github.com/kaushikkr-dev092005/touchstone` is **public** (MEASURED: GitHub visibility rechecked on 2 November 2026). The history scanner found no secret-pattern matches within its documented heuristic scope; see [M0 report and scan limits](M0_REPORT.md). Hackathon submission has not been performed. The previously fetched official event page lists the build phase ending 15 November 2026 18:29 UTC; use **13 November 2026, 18:29 UTC / 23:59 IST** as the working deadline and confirm the personal deadline in the portal.
