# Build roadmap, rebased 29 October 2026

The public event page lists build completion on **13 November, 18:29 UTC / 23:59 IST**. Target submission by 18:00 IST. Registration is listed as closed on 25 October; verify accepted participation in the signed-in portal now. No registration or submission has been performed by this agent.

## Completed foundation

- [x] Read and review all 17 proposal pages and inspect rendered architecture/tables.
- [x] Check the current Kit 12 recipe and official sandbox/clearing documentation.
- [x] Rebase the concept around customer holds and short operator float.
- [x] Build dependency-free local control plane and dashboard.
- [x] Atomic budget/float reservation, receipt matching and capture/release simulation.
- [x] Crash-recovery tests, including a subprocess exit between remote and local commit.
- [x] Source-based checks, classification blind-spot disclosure and independent truth scorer.
- [x] Seeded three-policy simulator benchmark command.
- [x] Read-only Airwallex smoke adapter and opt-in local inference profiler.

## Progress on 30 October

- [x] Replace classification membership checks with bounded source evidence and explicit review pauses.
- [x] Preserve the original simulator baseline; regenerate all three policies over five seeds using verifier v2.
- [x] Implement standalone sandbox pre-authorization/capture/cancel with immutable terms and read-based recovery.
- [x] Install verified portable Node and lock the supported Metal SDK dependencies.
- [x] Implement a Windows-compatible SDK wallet, guarded clearing purchases and recovery commands.
- [x] Read current public Metal deployment metadata successfully; no payment sent.
- [x] Add account setup guide, readiness command and dashboard readiness indicators.
- [x] Configure supplied credentials locally, verify RPC chain 63825 and Airwallex authentication/read scopes.
- [x] Fund a dedicated testnet wallet, deposit 0.10 USDZ, purchase one 0.01 USDZ GPU inference call and replay its original receipt/delivery.
- [ ] Validate a real sandbox authorization/capture: merchant PaymentIntent creation currently returns `configuration_error`.
- [x] Measure two model sizes on the RTX 3050; preserve raw outputs and paired replay results.
- [x] Add task-specific offline eligibility screening with deduplicated sources and a separate retrospective evaluation partition.
- [x] Execute a deterministic-tool baseline on 1,000 new-seed tasks and 24 authored boundary cases; expose tool/review decisions in the dashboard.
- [ ] Collect representative finance-operations sources and prospective evaluation evidence; qualify an inference provider for that domain.
- [x] Implement the integrated `banked-job` workflow, real SDK process bridge, local x402 provider and original-delivery recovery.
- [ ] Qualify useful paid inference and prove the complete external sandbox banking loop after merchant configuration is enabled.

The real paid proof rejected an incorrect answer (1250 cents instead of 2000), retained the failed-call charge and demonstrated both cached and provider-side replay without another payment. Receipt assurance is preconfirmed; unused float is not yet confirmed returned. Actual Airwallex authentication, balance reads and Global Account reads pass. PaymentIntent creation fails before authorization. See LIVE_PROOF.md for the precise evidence and blocker.

The updated simulator has 100% median true success for Touchstone at $6.162 versus premium's 99.5% at $10.200 on supported synthetic templates. This is a bounded-rule regression result; general semantic accuracy and real model savings remain unproven.

The real model profiles are materially weaker: 22.2% strict correctness for 0.5B and 48.9% for 1.5B on 90 paired calls each. A replay of cheap-first escalation reaches 50.0% at a higher assumed cost per correct result than balanced-first. Keep these results as evidence against blind cheap-first routing. Choose appropriate models/tools and require measured eligibility before enabling autonomous paid calls.

The deterministic baseline solves 1,000/1,000 generated tasks without a model call. All six measured provider/task combinations fail the offline eligibility screen. The three classification templates count as only three unique sources. The planning preview resolves supported calculations locally and defers unsupported sources for review. See PROCUREMENT_POLICY.md for the next invoice-exception experiment and the limits of the retrospective split.

See VALIDATION.md and saved results for what was actually executed. A checked foundation item is not a live-service completion claim.

## 29–31 October: prove the external integrations

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

The archived membership-only simulator baseline was 86% median true success. The current source-rules-v2 simulator reaches 100% on supported templates, which bounded tools can also solve. Neither simulator result establishes accuracy on unfamiliar documents. Require representative model evidence and an appropriate tool-only comparison before pitching quality-preserving savings.

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

1. Freeze features by 11 November. Keep the simple router if bandit calibration is unfinished.
2. Rehearse the five-minute story with a recorded backup. Show one changed decision and the resulting financial state.
3. Keep finality/withdrawal evidence prerecorded if chain timing exceeds the video window. Show whether a receipt is preconfirmed or final.
4. Review README setup from a clean checkout and verify required submission assets in the portal.

## 12–13 November: submit

Record the final video on 12 November. Submit the repository, working demonstration and requested materials on 13 November with several hours to spare. Confirm receipt in the portal. The private repository was pushed on 30 October 2026; public publication and hackathon submission remain pending.

## Cut order

Drop PDF export, per-token precision switching, extra provider types, reference-model summaries, Thompson sampling and FX embellishments before cutting the paid-call proof, customer hold lifecycle, verification, recovery, evidence or mode disclosures. The current synthetic tasks are intentionally narrow; one credible finance-ops workflow is enough for the first demonstration.

## Unresolved dependencies

Sandbox credentials and accepted registration are user-controlled. Metal needs a funded testnet key, RPC access and current deployment details. A verified local runtime and two licensed model files are installed and profiled, but no measured provider is approved for autonomous paid inference. Official judging rubric, submission schema and license requirements must be confirmed in the portal.
