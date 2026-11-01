# Detailed review of the 17-page proposal

Reviewed 29 October 2026. Source: the user's PDF, “Touchstone Quality-Verified Inference Procurement for Autonomous Agents-1.pdf”, prepared 22 October. All 17 pages were extracted; the architecture, tables and roadmap were also rendered for inspection.

## Recommendation

Keep Touchstone and its quality-aware procurement thesis. Put a concrete banking decision at the center: which customer job gets scarce prepaid inference float, when can it buy a better model, and when must it stop before exceeding authorization? Quality verification changes those financial decisions and creates an auditable result.

The original plan is strong on engineering depth but too broad for the remaining build window. Its largest gap is that the current Kit 12 recipe uses customer pre-authorizations and short operator float; wallet reads and optional FX alone do not demonstrate that cycle. The event links the developer lab guide, although that guide explicitly says it is not official API documentation. Exact payloads must come from official API references.

## Implementation update — 1 November 2026

The earlier review described missing features, not live evidence. The code now has a separate Airwallex treasury path for balance reads, FX quotes/conversions with a unique request ID, and reconciliation against wallet balance history. The account ID remains unset, so scoped access and all FX operations are still unverified. The engine now uses a unified Mock/Metal rail contract, has an explicit real Metal tier, queue-sensitive signed quotes and conservative recovery. Local outage/quality chaos switches and process-kill recovery are implemented but have not been run against a configured live provider. Source-cited invoice consistency checks remove the hidden-answer dependency; a seeded noisy checker now has a measured synthetic false-accept curve. See [validation](VALIDATION.md) and [live evidence](LIVE_PROOF.md) for executed versus pending items.

## Corrections before implementation

1. **Payment is not contingent on verification.** The proposed loop pays before output checks. A failed check prevents acceptance and may change the next purchase; it does not reverse the previous charge. Count all attempts. A credit receivable is not spendable money until confirmed.
2. **Customer authorization is different from operator liquidity.** A $1 customer hold is not $1 of available Metal funds. Enforce both independently. Add three jobs, per-job allocations, a shared float reserve, capture of actual cost and release of unused authorization.
3. **Exactly-once effects are conditional on the rail.** A unique local key cannot prevent a remote duplicate by itself. Recovery needs the original request/receipt and the rail's supported replay semantics. Unknown outcomes must remain reserved and block rerouting.
4. **The current clearing flow is not the mandate CLI flow.** Use the live clearing SDK's wallet, cap and recovery semantics. Do not imply that a direct-payout mandate also controls every clearing request without testing that claim.
5. **Receipt, settlement and finality are distinct.** A clearing receipt may be preconfirmed with an empty transaction hash. Preserve the invoice, signed receipt, deployment and epoch; never invent a transaction hash for each call.
6. **Airwallex is not a token bridge.** Reconcile customer holds/capture against the merchant ledger, and provider spend against Metal records. Explain any sandbox funding simulation. Do not label unrelated wallet deltas a matched three-way reconciliation.
7. **Confidence is not a verification score.** Label membership proves that a label is allowed, not that it is correct. A deterministic arithmetic check can prove more on constrained sources. Show accepted outputs and independently correct outputs separately.
8. **The router cannot promise a hard statistical quality floor without calibrated evidence.** Start with explicit priors and a simple observed-quality rule. Add confidence bounds or Thompson sampling only after profiling and cold-start behavior are defined. A low observed price is never authority to relax a spending cap.
9. **Reconciliation has pending states.** Outstanding holds, reserved attempts, delivered outputs, provider payments, verification costs and customer captures must each be represented. A local total matching a mock total does not prove an Airwallex integration.
10. **The proposed Node 20 minimum is stale for the current Metal clearing wallet.** The reviewed clearing docs specify Node 22.13+ for `node:sqlite`. Pin a tested SDK/Node combination when wiring the sidecar.

## Review by proposal section

| PDF section / pages | Assessment | Decision |
|---|---|---|
| 1. Executive summary / 1 | Clear cost-per-correct-outcome thesis; payment claim overreaches | Keep thesis; correct “only pays for quality” |
| 2. Why this project / 1–2 | Quality plus real GPU can differentiate a generic router | Validate differentiation through measured evidence; do not claim competitors are all mocked |
| 3. Problem and users / 2–3 | Finance, platform engineering and audit audiences are coherent | Demo one finance-ops batch; make customer charging explicit |
| 4. End-to-end loop / 3 | Reserve-pay-verify is a solid backbone | Add authorize, float allocation, capture/release and uncertain-payment recovery |
| 5. Priorities / 4 | Too many must-haves for a solo sprint | Keep controls and verifier; cut broad task types, bandit, cards-for-non-x402 and PDF export |
| 6. Architecture / 5–6 | Useful modular boundaries | Implement the local control plane in dependency-free Python; retain a Node Metal boundary |
| 7.1 Providers / 6 | Load-priced local inference is valuable evidence | Profile one model first on detected 4 GB VRAM; two tiers after actual measurements |
| 7.2 Payment layer / 7 | Correct need for protocol/version testing | Current prototype is a durable mock, not protocol-compatible x402; live SDK remains a gate |
| 7.3 Ledger / 7 | Highest-priority technical asset | Implement atomic reservations, receipt binding and real process-death tests now |
| 7.4 Planner / 7 | LLM planning adds dependency without helping the first proof | Use typed deterministic tasks first; later allow validated LLM proposals |
| 7.5 Router / 8 | Useful adaptive direction, but quality floor and exploration conflict | Start with bounded deterministic scoring and documented synthetic priors |
| 7.6 Verifier / 8 | Separation from benchmark truth is essential | Separate public task sources from private truth; expose classification false acceptance |
| 7.7 Treasury / 8–9 | Wallet/FX is useful but not sufficient for current Kit 12 | Prioritize pre-auth/capture lifecycle; sandbox read smoke available first |
| 7.8 Workload and chaos / 9 | Strong reproducibility idea | Implement paired seeds and index-based chaos; defer summaries and reference judges |
| 7.9 Dashboard / 9 | Explaining decisions and modes is the right goal | Implement local SSE dashboard with explicit simulation labels |
| 8. Data model / 9–10 | Covers basic purchases but misses customer and float accounting | Add runs, hold/capture/release and allocations; separate mock rail database |
| 9. Safety / 10 | Correct code-enforced authority boundary | Enforce caps, approved tasks/providers, expiry, local controls and dispatch stop |
| 10. Real vs simulated / 10 | Critical section, but original “real” list describes aspirations | Replace with current evidence matrix, not roadmap promises |
| 11. Evaluation / 11 | Good metric choice and paired five-seed design | Include rejected attempts, checker charges, synthetic latency labels and semantic blind spots |
| 12. Video / 11–12 | Good failure story, ambitious live schedule | Compress testnet payment count; prepare prerecorded finality/recovery evidence |
| 13. Judging / 12 | Sensible hypotheses; not official criteria | Leave criteria unverified until organizer confirms |
| 14. Prerequisites / 13 | Access and hardware are the likely bottlenecks | Verify keys and Metal self-serve setup before adding more models |
| 15. Schedule / 13–14 | Preparation window has passed | Rebase to 29 October–13 November with earlier integration gates |
| 16. Risks / 14–15 | Good identification of scope, tier quality and access risks | Add working-capital scarcity and delayed withdrawal finality |
| 17. Day-one questions / 15 | Many remain relevant | Record source-backed answers and unresolved items in INTEGRATIONS.md |
| 18. Repository / 16 | Monorepo suggestion is optional | Match actual runtime; one tested Python package plus dashboard and docs |
| 19. Sources / 16–17 | Useful starting points, some stale links | Use current official API/Metal pages; distinguish event-linked guide from API authority |

## Build / measure / pitch

The best first proof is not a giant agent framework. It is one budget-constrained purchase, a failed result that remains charged, a better follow-up purchase only if funds permit, a process crash recovered from a receipt, and a final customer capture that respects authorization. The local prototype implements that proof with simulated external systems. Live integration and real GPU evidence are the next gates, not completed claims.

Avoid fabricated business savings and “bank-grade” production claims. The five-seed simulator comparison tests accounting and policy behavior. Real GPU results need model hashes, warm-up exclusions, actual power/temperature observations and repeated timings. User value must eventually be validated with a finance/platform team.

## Sources checked

- Event and dates: https://www.hackerearth.com/community/challenges/hackathon/agentic-banking-hackathon/
- Event-linked recipe and financial decision guidance: https://airwallexdev.com/guide#12-inference-sourcing-agent
- Official sandbox/authentication host: https://www.airwallex.com/docs/developer-tools/sandbox-environment
- Official current FX reference: https://www.airwallex.com/docs/api/transactional_fx/conversion
- Official Metal clearing/recovery semantics: https://docs.metalntwx.com/agents/clearing
- x402 reference implementation: https://github.com/coinbase/x402

The proposal's old Metal quickstart/glossary links were unavailable during review. Current clearing documentation was accessible. Registration acceptance, exact judging rubric and repository license rules cannot be inferred from the PDF or the unauthenticated event overview.
