# Procurement evidence

Offline planning and real local tool execution. No payments sent.

Bounded tools solved 1000/1000 generated tasks over five new seeds with no model calls or provider spend. CPU p50 0.0015 ms; p95 0.0020 ms (single local run).

No provider purchase. CPU, development, review and service costs are not priced; this is not a zero-total-cost claim.

Authored boundary cases: 24/24 expectations met; 6 resolved and 18 deliberately deferred for review. Review is not task completion or measured real-world accuracy.

| Provider | Task | Unique calibration sources | Consistently correct | Wilson lower bound | Screen |
|---|---|---:|---:|---:|---|
| economy | invoice | 20 | 4 | 8.1% | BELOW_QUALITY_TARGET |
| economy | arithmetic | 20 | 0 | 0.0% | BELOW_QUALITY_TARGET |
| economy | classification | 3 | 1 | 6.1% | INSUFFICIENT_UNIQUE_SOURCES |
| balanced | invoice | 20 | 10 | 29.9% | BELOW_QUALITY_TARGET |
| balanced | arithmetic | 20 | 0 | 0.0% | BELOW_QUALITY_TARGET |
| balanced | classification | 3 | 3 | 43.9% | INSUFFICIENT_UNIQUE_SOURCES |

Screen target: 95% success and at least 20 unique calibration sources, separately for each task kind. No model has live purchase authorization.

Retrospective split of previously inspected profiles, not a pristine prospective holdout. Exact repeated sources are collapsed; template correlation remains. Evaluation rows do not enter the screen.

Wilson lower bounds are screening diagnostics on narrow fixtures, not deployment accuracy guarantees. Task.min_quality is a response-check score, separate from the 95% provider success target.

The classifier profile repeats only three distinct messages. Its 30 measurements per model do not represent 30 unique customer scenarios. Evaluation seed 43 has no unseen classification sources.

The simulator dashboard retains its original financial stress scenario. The planning preview and CLI execute bounded tools separately, with explicit review on unsupported input. Neither the statistical screen nor this report enables a paid adapter.

Next experiment: define representative de-identified finance-ops inputs and independent expected outcomes; freeze prompts/tools, collect a new prospective calibration/evaluation split, and measure a model only where deterministic tools abstain. Connect payment only after measured eligibility and funded recovery proof.

Wilson formula reference: [NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
