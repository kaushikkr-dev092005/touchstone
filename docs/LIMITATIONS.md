# Financial invariants and practical limitations

M3 adds a synthetic invoice-extraction corpus and a controlled optional second extraction, not a production OCR pipeline or an independent semantic judge. Exact spans establish textual support; role interpretation can still be wrong. Known generated truth is read only in offline scoring. The 13.3% parser coverage is one conservative baseline, not evidence that other deterministic tools cannot solve the rest. Both local models have complete 180-call M3 measurements, zero strict-correct extractions and zero eligibility; no paid reference has run. Partner-credit funding is operator-declared, with upstream dollar cost UNMEASURED. See [M3 report](M3_REPORT.md).

## Enforced locally

Amounts are integer micro-USD; no binary floating-point arithmetic is used for ledger money. Reservations use SQLite `BEGIN IMMEDIATE` and include provider price plus checking charge. Spent plus active reservations cannot exceed the job budget or customer hold. A per-call cap applies to the inference price; checks consume the total budget separately. Allocations across jobs cannot exceed a run's initial operator float.

Every attempt binds job, approved source task, step, attempt number, provider and quoted price to one key. An existing key cannot authorize changed purchase terms. Receipt amount, quote and provider must match. A reserved or paid step cannot acquire a second parallel attempt. Escalation is bounded to three attempts and higher tiers, and baseline policies make one attempt.

Customer capture is simulated, idempotent and blocked while a purchase is unresolved. Partial closure captures only actual accounted cost and releases the unused hold. The mock rail retains results independently, so recovery can retrieve the same receipt and result before further purchases.

## Conditional guarantees

The demonstrated no-duplicate observations cover the mock rail under tested crash boundaries/concurrency and one real Metal after_rail hard-kill/recovery, repeated against the same receipt. External rails require their own durable replay/recovery semantics. This repository does not prove exactly-once blockchain, network or Airwallex effects.

The unified engine rechecks halt status, mandate version, expiry and worker ownership in the same transaction that marks an attempt `DISPATCHING`. A halt prevents subsequent authorizations; an already authorized request can still complete and must be reconciled. This is not atomic cancellation of an external payment. The legacy banked-job adapter remains separate from this engine barrier. M2's barrier is validated with controlled adapters; one live hard-kill/recovery also passed. This does not prove every external failure mode.

The independent rail database is durable locally but shares a machine with the ledger. It is a useful recovery test, not independent third-party attestation. Audit triggers and hash chaining expose ordinary mutation but do not resist an administrator who can replace the database and recompute hashes. Periodic externally anchored heads are future work.

## Verification and evaluation

Source-based arithmetic and invoice checks are exact only for the constrained generated formats. Classification now uses bounded evidence rules; contradictory labels fail, and ambiguous or unsupported sources pause for review. These lexical rules are not a general semantic judge and can miss contexts outside their coverage. A score of 1.0 is a passed check, not calibrated confidence or a universal correctness guarantee. `min_quality` describes the check threshold, not measured semantic confidence. Original membership-only results remain in baseline-v1/.

These generated tasks also admit deterministic solutions. The current workload validates payment and verification controls; it does not prove that buying model inference is necessary for these tasks. The cited invoice-consistency checker recomputes supported arithmetic from cited source spans, while the deliberately noisy checker is only a fault-injection experiment. A production evaluation needs a code-only baseline and representative sources such as OCR text or genuinely ambiguous language before making a business savings claim.

All provider reliability, quotes and service latencies in the main dashboard demo are synthetic. The separate live Metal adapter now quotes from current queue depth and reports its latency estimate with the count of completed-delivery samples; one paid integrated delivery reported 714 ms provider latency, not end-to-end settlement latency or a benchmark. The simulator provider independently derives responses from public task sources; only the offline scorer reads the separate answer map. There is no LLM planner, statistically calibrated Thompson policy, validated reference-model judge or production invoice/OCR pipeline yet.

The five-seed benchmark compares a one-attempt premium policy, a one-attempt cheapest policy and a bounded-retry Touchstone policy. Every policy uses the same source workload, chaos indices and verifier, with random provider outcomes keyed by seed/task/provider/attempt. This evaluates a whole policy including retry cost, not routing alone. No tuning or repeated-seed selection is used to promise a win.

Cost includes every paid provider attempt and a fixed simulated internal verification charge. Customer capture currently includes that charge. This is an assumed service-pricing model, not a real invoice, FX fee, gas estimate or external verifier bill. Cost per true-correct step counts only accepted outputs matching offline truth.

The benchmark's duplicate-payment count is a summary consistency check, not a substitute for crash/replay tests. Detection delay is reported only when the selected policy actually queries a degraded provider and a checker detects its failure; absence of a detection is not zero delay.

## Operational scope

The server binds loopback, validates Host and Origin on mutations and requires a per-process session token. It is a development dashboard with no user authentication, multi-user access controls, production TLS, encrypted database, retention policy or deployment hardening. Do not expose it directly to the internet or feed it real customer data.

There is one dashboard worker per server. Unified engine jobs now use process-owned local leases, which prevent another engine worker from executing or recovering that job until its owner exits. No timer can steal a lease from a stalled network call. The OS lock releases after process death; the next owner recovers pending attempts before new work. Multi-host distributed execution remains unsupported. `metal-batch` funds job wallets sequentially, then runs separate job workers concurrently; this path is tested with mocks. Testnet allocations remain assigned to their wallets after simulated customer settlement and cannot receive simulated cross-wallet top-ups. The dashboard's run float remains an isolated simulation.

A separate integrated sandbox/testnet orchestrator is implemented and tested with controlled adapters. One funded Metal GPU inference purchase and original receipt/delivery replay are verified. Airwallex authentication/read access passes; a separate hosted sandbox 1.00 USD authorization and 0.01 USD capture completed; unused issuer release timing is unmeasured. Historical native merchant errors do not prove current native API entitlement. The three-job scenario still uses mocks. Funded probe jobs sharing the EVM account are serialized and are not a demonstration of three concurrent external customer holds.

The live probe has zero checking fees, captures whole cents by rounding down and records any remainder as merchant expense. Gas is merchant expense. A separate Airwallex treasury module implements wallet balance reads, quote/conversion APIs, request-ID journaling and wallet-history reconciliation, and one approved 1.00 USD → 0.89 EUR conversion settled and matched wallet history. It does not bridge fiat into USDZ or reconcile customer holds/captures. Actual Airwallex hold increments, refunds and external float top-ups are not implemented. The dashboard now supports an audited, versioned increase for simulator-only mandates; it cannot authorize a card hold or add live funds. Resume alone preserves limits. An `empty` SDK withdrawal can reflect unfinalized funds; only actual non-deferred claims count toward returned allocation. A receipt remains preconfirmed until finality is independently established.

The local configuration and wallet files contain credentials in ignored development storage. They are excluded from the source bundle and never sent to the model worker. This is not a production secret-management or multi-user custody design.
