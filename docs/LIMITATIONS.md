# Financial invariants and practical limitations

## Enforced locally

Amounts are integer micro-USD; no binary floating-point arithmetic is used for ledger money. Reservations use SQLite `BEGIN IMMEDIATE` and include provider price plus checking charge. Spent plus active reservations cannot exceed the job budget or customer hold. A per-call cap applies to the inference price; checks consume the total budget separately. Allocations across jobs cannot exceed a run's initial operator float.

Every attempt binds job, approved source task, step, attempt number, provider and quoted price to one key. An existing key cannot authorize changed purchase terms. Receipt amount, quote and provider must match. A reserved or paid step cannot acquire a second parallel attempt. Escalation is bounded to three attempts and higher tiers, and baseline policies make one attempt.

Customer capture is simulated, idempotent and blocked while a purchase is unresolved. Partial closure captures only actual accounted cost and releases the unused hold. The mock rail retains results independently, so recovery can retrieve the same receipt and result before further purchases.

## Conditional guarantees

The demonstrated at-most-once effect is for the mock rail under the tested crash boundaries and concurrent reservation cases. External rails require their own durable replay/recovery semantics. This repository does not prove exactly-once blockchain, network or Airwallex effects.

The kill switch prevents newly authorized dispatches after its check; it cannot reverse a request already in flight. There is a small check-to-dispatch race in this prototype. A live sidecar needs a serialized dispatch barrier, reservation/mandate version binding and clear in-flight status. Do not describe the kill switch as an atomic cancellation of external payments.

The independent rail database is durable locally but shares a machine with the ledger. It is a useful recovery test, not independent third-party attestation. Audit triggers and hash chaining expose ordinary mutation but do not resist an administrator who can replace the database and recompute hashes. Periodic externally anchored heads are future work.

## Verification and evaluation

Source-based arithmetic and invoice checks are exact only for the constrained generated formats. Classification now uses bounded evidence rules; contradictory labels fail, and ambiguous or unsupported sources pause for review. These lexical rules are not a general semantic judge and can miss contexts outside their coverage. A score of 1.0 is a passed check, not calibrated confidence or a universal correctness guarantee. `min_quality` describes the check threshold, not measured semantic confidence. Original membership-only results remain in baseline-v1/.

These generated tasks also admit deterministic solutions. The current workload validates payment and verification controls; it does not prove that buying model inference is necessary for these tasks. The cited invoice-consistency checker recomputes supported arithmetic from cited source spans, while the deliberately noisy checker is only a fault-injection experiment. A production evaluation needs a code-only baseline and representative sources such as OCR text or genuinely ambiguous language before making a business savings claim.

All provider reliability, quotes and service latencies in the main dashboard demo are synthetic. The separate live Metal adapter now quotes from current queue depth and reports its latency estimate with the count of completed-delivery samples; no paid integrated timing measurement has been made. The simulator provider independently derives responses from public task sources; only the offline scorer reads the separate answer map. There is no LLM planner, statistically calibrated Thompson policy, reference-model judge or production invoice/OCR pipeline yet.

The five-seed benchmark compares a one-attempt premium policy, a one-attempt cheapest policy and a bounded-retry Touchstone policy. Every policy uses the same source workload, chaos indices and verifier, with random provider outcomes keyed by seed/task/provider/attempt. This evaluates a whole policy including retry cost, not routing alone. No tuning or repeated-seed selection is used to promise a win.

Cost includes every paid provider attempt and a fixed simulated internal verification charge. Customer capture currently includes that charge. This is an assumed service-pricing model, not a real invoice, FX fee, gas estimate or external verifier bill. Cost per true-correct step counts only accepted outputs matching offline truth.

The benchmark's duplicate-payment count is a summary consistency check, not a substitute for crash/replay tests. Detection delay is reported only when the selected policy actually queries a degraded provider and a checker detects its failure; absence of a detection is not zero delay.

## Operational scope

The server binds loopback, validates Host and Origin on mutations and requires a per-process session token. It is a development dashboard with no user authentication, multi-user access controls, production TLS, encrypted database, retention policy or deployment hardening. Do not expose it directly to the internet or feed it real customer data.

There is one active orchestrator worker per server. Multiple server processes against the same job are unsupported. Atomic reservations prevent budget races but do not constitute distributed worker leasing. The demo's float belongs to each run; different runs represent isolated simulations, not a shared real merchant wallet.

A separate integrated sandbox/testnet orchestrator is implemented and tested with controlled adapters. One funded Metal GPU inference purchase and original receipt/delivery replay are verified. Airwallex authentication/read access passes, but merchant configuration blocks PaymentIntent creation; actual bank authorization/capture remains unverified. The three-job scenario still uses mocks. Funded probe jobs sharing the EVM account are serialized and are not a demonstration of three concurrent external customer holds.

The live probe has zero checking fees, captures whole cents by rounding down and records any remainder as merchant expense. Gas is merchant expense. A separate Airwallex treasury module implements wallet balance reads, quote/conversion APIs, request-ID journaling and wallet-history reconciliation, but it has not been configured or executed. It does not bridge fiat into USDZ or reconcile customer holds/captures. Actual Airwallex hold increments, refunds and external float top-ups are not implemented. The dashboard now supports an audited, versioned increase for simulator-only mandates; it cannot authorize a card hold or add live funds. Resume alone preserves limits. An `empty` SDK withdrawal can reflect unfinalized funds; only actual non-deferred claims count toward returned allocation. A receipt remains preconfirmed until finality is independently established.

The local configuration and wallet files contain credentials in ignored development storage. They are excluded from the source bundle and never sent to the model worker. This is not a production secret-management or multi-user custody design.
