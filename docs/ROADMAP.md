# Build roadmap, M0 review 2 November 2026

The official event page (fetched 2 November 2026) lists build completion on **15 November, 18:29 UTC**; earlier notes cited 13 November. **Internal deadline: 13 November 18:29 UTC / 23:59 IST**, submitting well before it. Confirm the personal deadline in the portal. Registration is listed as closed on 25 October; verify accepted participation in the signed-in portal now. No registration or submission has been performed by this agent.

## Official kit mapping

The [current Airwallex developer-lab guide](https://airwallexdev.com/guide) maps the three-job, short-float inference sourcing story to **Kit 12**. Its **Kit 11** asks for spending-limit rebalancing when upstream prices rise and a dispute settled from signed orders. This project has a simulated, versioned human approval flow and one real signed x402 receipt, but no end-to-end Kit 11 dispute settlement or live limit rebalance. Do not claim Kit 11 as completed until those behaviors are implemented and evidenced.

## Done (updated 6 November 2026)

Current additions: M1 sandbox FX and hosted capture verified; M2 one-call paid engine and hard-kill/recovery verified; both M3 local profiles measured and refused. See [current evidence](RUNNING.md).

A checked item is not a live-service completion claim; see VALIDATION.md and LIVE_PROOF.md for exactly what ran.

- [x] Read and review all 17 proposal pages and inspect rendered architecture/tables.
- [x] Check the current Kit 12 recipe and official sandbox/clearing documentation.
- [x] Rebase the concept around customer holds and short operator float.
- [x] Build dependency-free local control plane and dashboard.
- [x] Atomic budget/float reservation, receipt matching and capture/release simulation.
- [x] Crash-recovery tests, including a subprocess exit between remote and local commit.
- [x] Source-based checks, classification blind-spot disclosure and independent truth scorer.
- [x] Seeded three-policy simulator benchmark command.
- [x] Read-only Airwallex smoke adapter and opt-in local inference profiler.
- [x] Replace classification membership checks with bounded source evidence and explicit review pauses.
- [x] Preserve the original simulator baseline; regenerate all three policies over five seeds using verifier v2.
- [x] Implement standalone sandbox pre-authorization/capture/cancel with immutable terms and read-based recovery.
- [x] Implement user-present hosted sandbox checkout with uncaptured authorization, durable recovery and reuse in the integrated job.
- [x] Install verified portable Node and lock the supported Metal SDK dependencies.
- [x] Implement a Windows-compatible SDK wallet, guarded clearing purchases and recovery commands.
- [x] Read current public Metal deployment metadata successfully; no payment sent.
- [x] Add account setup guide, readiness command and dashboard readiness indicators.
- [x] Configure supplied credentials locally, verify RPC chain 63825 and Airwallex authentication/read scopes.
- [x] Fund a dedicated testnet wallet, deposit 0.10 USDZ, purchase one 0.01 USDZ GPU inference call and replay its original receipt/delivery.
- [x] Return the remaining 0.09 testnet USDZ through a finalized non-deferred withdrawal claim; record queue and claim transactions.
- [x] Measure two model sizes on the RTX 3050; preserve raw outputs and paired replay results.
- [x] Add task-specific offline eligibility screening with deduplicated sources and a separate retrospective evaluation partition.
- [x] Execute a deterministic-tool baseline on 1,000 new-seed tasks and 24 authored boundary cases; expose tool/review decisions in the dashboard.
- [x] Implement the integrated `banked-job` workflow, real SDK process bridge, local x402 provider and original-delivery recovery.
- [x] Add a no-payment invoice-exception preflight with exact source citations, integer-total recomputation, purchase-order/payment checks and mandatory human review.
- [x] Add Airwallex wallet-balance reads, FX quote/conversion writes guarded by an explicit execute flag, durable request-ID journaling, and wallet-history reconciliation.
- [x] Add an invoice-consistency task whose checker verifies cited source spans and arithmetic without recomputing from a hidden answer map.
- [x] Measure a deliberately noisy invoice checker against offsetting line-item errors; remove the circular verifier calibration MAE from current benchmark output.
- [x] Unify the simulated and Metal payment rails in the engine, route an explicit Metal tier, and retain reservations when the live rail cannot prove non-payment.
- [x] Add queue-aware signed quote pricing, service-latency estimates with sample counts, opt-in provider outage/quality chaos, and a hard process-kill recovery switch.
- [x] Add MIT `LICENSE` with the requested 2026 Kaushik Kumar copyright.
- [x] Put the one real paid GPU failure and its unbilled probe outlay before the simulator on the dashboard; remove the deleted calibration metric and expose the noisy-checker chart.
- [x] Add audited versioned approvals for simulated limit increases; the job remains paused until a separate Resume, and no real hold or wallet is affected.
- [x] Add a guarded live quote-only engine preflight; exercise the local Vulkan model seller and Metal testnet quote with zero payments.
- [x] Run the live seller's outage chaos mode through quote-only; verify HTTP 503 before quote and zero payment dispatch.
- [x] Run the Airwallex read-only readiness check; authentication/balance/account reads pass, and account context is now configured (historical unset observation superseded).
- [x] Add an optional hosted Claude Messages API provider using schema-constrained JSON, a configurable model ID and provider-reported token usage.
- [x] Keep hosted credentials out of the buyer-side Metal bridge; on uncertain delivery, refuse to repeat a potentially billable hosted request.
- [x] Add three real-only Metal policies: local GPU only, hosted premium only, and local-first with verifier-triggered hosted escalation. Real policies exclude simulator offers and require both named live tiers in a no-payment quote preflight.
- [x] Persist a redacted per-scope policy report and expose a dashboard table grouped by identical task digest; the panel remains empty until paid real-provider runs are actually recorded.
- [x] M0 complete: README status labels, Bash equivalents, 133 local Python tests and 21 Node tests pass; all four GitHub Actions jobs on Ubuntu/Windows with Python 3.11/3.12 pass for `b8819d7`. See [M0 report](M0_REPORT.md).
- [x] MEASURED history scan: no secret-pattern findings or sensitive committed paths in the reported heuristic scope. Ignored private data is excluded; this is not a guarantee that no secret exists.
- [x] Repository is public (verified through the GitHub API on 2 November 2026).
- [x] M1 implementation and documented-blocker exit: environment-only doctor, guarded FX job accounting with separate demo USDZ, definitive create rejection/consumed-ID handling, evidence-based scope retirement, visible treasury stages, controlled tests and support draft. [M1 report](M1_REPORT.md). One sandbox FX write/read-back and one hosted authorization/capture are now measured; earlier blocker observations are historical.

- [x] M3 implementation and honest refusal evidence: 180 template-split synthetic sources, measured 13.3% parser coverage, citation/integer checker, local/hosted profilers, paid-reference accounting and three-task panel. Both local models measured on 180 sources each; zero eligible models; no useful paid inference claim. [M3 report](M3_REPORT.md).
- [x] M2 implementation and controlled recovery/invariant evidence are complete; its single-call live integration and hard-kill/recovery gates now pass; concurrent live jobs remain unmeasured. [M2 report](M2_REPORT.md).

- [x] M4 implementation: matched tools/cheapest/premium/qualified-ladder runner, capped durable dispatch, shared seller fault schedule, raw scoring, cost/latency tables and environment manifest. Controlled evidence is MOCK; no new live purchases. [M4 report](M4_REPORT.md).

- [x] M5 simulated financial story: immutable failed-call billing, separate provider/check expenses, short-float reconciliation and saved audit heads. [Report](M5_REPORT.md).
- [x] Signed fault evidence, controlled provider acknowledgements, guarded CardRail, controlled signed intent, FX-aware comparison and real GPU telemetry. [Scope and limitations](FEATURES.md).
- [x] Packaging implementation: committed-tree source bundle, private-data exclusions and credential-isolated one-command mock launch. Clean-checkout results are recorded separately.

## Not done

Local packaging/clean-checkout verification has passed for the explicit committed
source revision in [M7](M7_REPORT.md). This does not close the live or manual gates
below and does not establish current remote CI success.

- [ ] M4 live gate: ready sellers and a dedicated funded scope, new aggregate purchase/hosted-credit approval, then 30–50 real paid calls and fault/reconciliation evidence. The proposed setup currently fails readiness. [M4 runbook](M4_RUNBOOK.md).

- [ ] M3 useful inference: both measured local tiers failed the unchanged qualification gate. Hosted credentials/partner credits and a separate paid-study cap remain human gates. The negative-result exit is met; useful inference is unproven.

- [ ] Full M2/M4 live scale: one-call Metal integration/recovery passed; a larger concurrent/30–50-step study needs fresh funding/purchase/upstream approvals and eligible models. Existing one-purchase and deposit approvals are consumed.

- [ ] Native acquiring entitlement remains unverified; separate hosted sandbox authorization/capture is complete. Issuing reads return 401 and require separate enablement.
- [ ] Collect representative finance-operations sources and prospective evaluation evidence; qualify an inference provider for that domain. No measured model passes the eligibility screen.
- [ ] Larger live paid comparison/quality-chaos remains unrun; the separate one-call hard-kill/recovery proof is complete. Fresh aggregate approvals and eligible providers are required.
- [ ] Configure hosted premium credentials and both provider origins, then run the matched three-policy paid trial (hosted API invoice is separate from the USDZ metric).
- [ ] Ask the sponsor whether sandbox Developer MCP/CLI counts as Airwallex tooling; AgentOS MCP/skills need a production connector and the official CLI has no Windows build.
- [ ] Kit 11 (price-rise limit rebalance, signed-order dispute settlement) is not implemented; do not claim it.
- [ ] Replace dashboard simulated inference with real inference (the simulator remains labelled SIMULATED).
- [ ] Real Airwallex hold increase for mandate-limit approval does not exist; the approval is a simulated, versioned local mandate only.

## Evidence summary

The real paid proof rejected an incorrect answer (1250 cents instead of 2000), retained the failed-call charge and demonstrated both cached and provider-side replay without another payment. The remaining 0.09 testnet USDZ has now returned through a non-deferred claim; the receipt assurance remains preconfirmed. Actual Airwallex authentication, balance reads and Global Account reads pass. The historical direct-create error is separate from the now-completed hosted sandbox authorization/capture. See LIVE_PROOF.md for the precise evidence and blocker.

The updated simulator has 100% median true success for Touchstone at $6.162 versus premium's 99.5% at $10.200 on supported synthetic templates. This is a bounded-rule regression result; general semantic accuracy and real model savings remain unproven.

The real model profiles are materially weaker: 22.2% strict correctness for 0.5B and 48.9% for 1.5B on 90 paired calls each. A replay of cheap-first escalation reaches 50.0% at a higher assumed cost per correct result than balanced-first. Keep these results as evidence against blind cheap-first routing. Choose appropriate models/tools and require measured eligibility before enabling autonomous paid calls.

The deterministic baseline solves 1,000/1,000 generated tasks without a model call. All six measured provider/task combinations fail the offline eligibility screen. The three classification templates count as only three unique sources. The planning preview resolves supported calculations locally and defers unsupported sources for review. See PROCUREMENT_POLICY.md for the next invoice-exception experiment and the limits of the retrospective split.

See VALIDATION.md and saved results for what was actually executed. A checked foundation item is not a live-service completion claim.


## Milestone order approved on 2 November

Work stops for a report at each milestone gate. Feature freeze is 11 November; the working submission deadline is **13 November 2026, 18:29 UTC / 23:59 IST**. The signed-in portal remains the human source of confirmation.

| Milestone | Dates | Exit evidence |
|---|---|---|
| M0: truth and hygiene | 2 Nov | Reconciled docs, history scan, green Python/Node CI on Ubuntu and Windows |
| M1: Airwallex action | 2–3 Nov | Approved sandbox FX write/read-back, or documented external blocker and support request draft |
| M2: Metal engine/recovery | 3–4 Nov | Approved paid engine run and real kill/restart without duplicate charge |
| M3: useful inference | 4–6 Nov | Template-split invoice evaluation; an eligible model adds value or the gate honestly refuses all models |
| M4: live comparison | 6–8 Nov | Approved paid policy measurements, raw results, environment manifest and control checks |
| M5: financial story | 8–9 Nov | Failed-call policy, P&L, short-float scenario and separate-account reconciliation |
| M6: dashboard | 9–10 Nov | Light polish only after M1–M4 gates; retain session token and evidence badges |
| M7: packaging/freeze | 10–11 Nov | Clean-checkout setup, truthful evidence index and demo script; no critical bugs |
| Human recording/submission | 12–13 Nov | Portal-confirmed format, uploaded video and confirmed submission receipt |

All money movement requires an execute-style flag plus written chat approval with a stated cap. See [M0 human gates](M0_REPORT.md). The dated sections below retain the earlier roadmap as historical planning, superseded by this milestone order.

## Historical plan: 29–31 October, external integrations

1. Confirm accepted hackathon registration and exact submission requirements in the portal.
2. Create or use the Airwallex sandbox. Set scoped Client ID/API key in the local shell. Run `python -m touchstone airwallex-smoke`.
3. Use official API schemas to implement pre-authorization create/confirm/retrieve/capture/cancel. Prove a hold reaches the expected capture-ready state before scheduling any job against it. Persist operation UUIDs and unknown outcomes.
4. Install Node 22.13+ and create the Metal sidecar with the documented SDK version and an exact lockfile. Create a fresh clearing wallet for each job and run one real testnet paid call.
5. Save redacted evidence: sandbox object IDs, the clearing invoice and receipt, deployment/network, SDK lockfile and actual response statuses. Keep private keys and tokens out of the repo.

**Exit gate:** one actual sandbox authorization/capture/release and one real testnet receipt linked to a ledger reservation. If either fails by 31 October, prioritize the integration over extra dashboard or routing work. Keep truthful fallback labels.

## 1–3 November: measure a real local provider

1. Start a small instruct model on the 4 GB RTX 3050 with limited context, one slot and 20% VRAM headroom. Record model license, GGUF hash, model revision, driver, context, sampling, clocks, temperatures and power.
2. Use `profile-local` to check structured output correctness and measured latency. Compare a second model size only after the first is stable. Do not assume Q4/Q8 on the same model yields a large quality gap.
3. Replace one synthetic provider with the profiled model and measure actual queue depth. Quote a bounded maximum call price and never bill beyond it without a new approval.
4. Implement a second verification pass for uncertain classifications; account for its real cost. Keep ground truth offline and measure false acceptance.

The archived membership-only simulator baseline was 86% median true success. The current source-rules-v3 simulator reaches 100% on supported templates, which bounded tools can also solve. Its prior tautological calibration MAE is removed; invoice false-accept results now come from explicit fault injection. Neither simulator result establishes accuracy on unfamiliar documents. Require representative model evidence and an appropriate tool-only comparison before pitching quality-preserving savings.

**Exit gate:** paid local-model call with measured latency, linked receipt and verifier result. A paid quote must stay valid through dispatch or be re-quoted without silently changing the authorized purchase.

## 4–6 November: close the banking loop

1. Execute three concurrent jobs under separate customer holds and separate clearing wallets. Parallelize across wallets; serialize within each wallet.
2. Allocate only funded operator float. Top up only when capacity is confirmed; hold increments require explicit customer authorization before a larger budget is usable.
3. Implement settlement-aware resume: unresolved payment is retried against its original provider, URL and price before rerouting. Retain reservations while uncertain.
4. Capture actual authorized customer cost once, including documented service/checking fees; release the unused hold. Close failed jobs too.
5. Reconcile provider receipts, internal checking charges and customer captures as separate accounts. Unfinalized withdrawals remain unavailable float.

**Exit gate:** no job exceeds its hold, no allocation exceeds funded float, all captures link to final spend, and every uncertain purchase is recovered or remains visibly pending.

## 7–9 November: produce evidence

1. Rerun identical workloads across at least five seeds for each policy. Start with 30–50 real paid requests; hundreds of clearing payments can exceed a five-minute demo.
2. Preserve the simulator benchmark for regression checks; publish GPU/testnet measurements in separate result files.
3. Inject price/latency/quality changes at shared task indices. Plot false acceptance and cost per truly correct output, including failed calls and paid reference checks.
4. Demonstrate an actual process kill/restart, and show the original request is not paid twice. Keep the complete receipt trail.
5. Validate UI disclosure badges from actual configuration and successful health checks. A failed live service must not silently become a mock with a LIVE badge.

**Exit gate:** reproducible raw results, environment manifest, zero observed control violations, and an honest account of statistical uncertainty. Do not tune only one seed or hide policies that perform well.

## 10–11 November: freeze and rehearse

1. Freeze features by 11 November. Thompson sampling is implemented as an optional policy but remains uncalibrated; do not treat it as production routing evidence.
2. Rehearse the five-minute story with a recorded backup. Show one changed decision and the resulting financial state.
3. Keep finality/withdrawal evidence prerecorded if chain timing exceeds the video window. Show whether a receipt is preconfirmed or final.
4. Review README setup from a clean checkout and verify required submission assets in the portal.

## 12–13 November: submit

Record the final video on 12 November. Submit the repository, working demonstration and requested materials on 13 November with several hours to spare. Confirm receipt in the portal. The repository is public; hackathon submission remains pending.

## Cut order

Drop PDF export, per-token precision switching, extra provider types, reference-model summaries and any claim that the uncalibrated Thompson policy is production-ready before cutting the paid-call proof, customer hold lifecycle, verification, recovery, evidence or mode disclosures. The current synthetic tasks are intentionally narrow; one credible finance-ops workflow is enough for the first demonstration.

## Unresolved dependencies

`AIRWALLEX_ACCOUNT_ID`, Checkout Sessions/Transactional FX permissions, active payment methods and accepted registration are user-controlled. The live testnet provider URL is not configured and the previously funded wallet was withdrawn; one old paid proof and returned-float evidence remain recorded. No representative finance-operations evaluation set or qualified provider is available. Record the demo on 12 November and submit by 13 November with hours to spare, after verifying portal requirements. MIT is selected; official judging rubric, submission schema, team details and video requirements still need portal confirmation.
