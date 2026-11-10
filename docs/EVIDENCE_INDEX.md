# Current evidence, 10 November 2026

- [Final live review and incomplete comparison](LIVE_PROOFS_20261110.md)
- [Final caps, actual charges, funding transaction IDs, balances and native fees](../bench/results/completion-20261110/final-proof-status.json)
- [Qualified Sonnet result, unchanged criteria](../bench/results/m3-v2/sonnet-qualification-result.json)
- [Raw Sonnet profile](../bench/results/m3-v2/profiles/sonnet-hosted-premium.json)
- [Integrated customer closure receipt](../bench/results/m3-v2/integrated-receipt.json)
- [Matched comparison: incomplete, no savings claim](../bench/results/m4-v2/live-report.json)
- [Sampled GPU temperatures and stop limits](../bench/results/m4-v2/gpu-monitor.json)
- [Latest exact-source release validation](../bench/results/m3-v2/release-validation.json)
- [Recording and submission material](DEMO_SCRIPT.md), [submission draft](SUBMISSION.md)

The dated snapshots below retain their original observations. They do not supersede
the current results above. Earlier $8 approval was lowered to $3; it is historical.

---

# Evidence index — 6 November 2026

Labels describe the evidence scope, not production readiness. Public artifacts
contain redacted observations; private runtime data is excluded from packaging.

| Evidence | Label | Supported claim / limit |
|---|---|---|
| [M1 FX](../bench/results/m1/live-fx-single-conversion.json) | MEASURED sandbox | Exactly 1 USD sold for 0.89 EUR, settled and history-matched |
| [Treasury job](../bench/results/m1/live-treasury-job.json) | MEASURED / SIMULATED | Actual fiat record; separate demo USDZ cannot fund Metal |
| [Hosted capture](../bench/results/m1/current-hosted-card-proof.json) | MEASURED sandbox | 1 USD authorization, 0.01 captured; release timing unmeasured |
| [M2 engine proof](../bench/results/m2/live-single-call-final.json) | MEASURED testnet | One paid-and-rejected call, hard kill, repeated recovery without duplicate; preconfirmed |
| [Historical purchase](../bench/results/metal-paid-proof.json) | MEASURED testnet | Incorrect 1,250-cent answer rejected against 2,000-cent source; replay preserved |
| [Fault receipt](../bench/results/faults/metal-fault.json) | MEASURED historical evidence | Buyer-signed reproducible counterexample; original provider output unsigned; no refund |
| [Controlled credit acknowledgement](../bench/results/features/controlled-credit-acknowledgement.json) | MOCK identity / MEASURED signatures | Accepted acknowledgement, no actual credit or cash settlement |
| [M3 report](../bench/results/m3/report.json) | MEASURED on SIMULATED sources | Both local models ineligible; no useful paid inference claim |
| [M4 report](M4_REPORT.md) | MOCK controlled study / BLOCKED live | Four-policy runner and fault schedule, no 30–50-call live comparison |
| [M5 financial story](../bench/results/m5/financial-story.json) | SIMULATED / MEASURED execution | Immutable billing policies, short float, separate expenses, valid audit heads |
| [Reference FX](../bench/results/features/fx-quote.json) | MEASURED quote / SIMULATED prices | Saved rate may be expired; no conversion or fiat merchant dispatch |
| [Controlled FX switch](../bench/results/features/controlled-fx.json) | SIMULATED / MOCK rates | FX changes preferred eligible illustrative offer; no payment |
| [GPU sample](../bench/results/features/telemetry.json) | MEASURED local hardware | Timestamped driver sample; no calibrated capacity markup or measured tokens/sec |
| [Issuing doctor](../bench/results/features/card-readiness.json) | MEASURED | Fresh Cards, Cardholders, Config and balance reads pass on 10 November; no card created; writes/Visa unverified |
| [Signed intent](../bench/results/features/tap-probe.json) | MOCK identity / MEASURED protocol check | Controlled HTTP acceptance and replay rejection; no Visa trust/approval or payment |
| [Feature tests](../bench/results/features/validation.json) | MEASURED local | Test counts, artifact hashes, browser/security checks |
| [Clean source verification](../bench/results/package/clean-checkout.json) | MEASURED Windows | Exact committed archive, pinned install, 247 Python/47 Node tests and browser checks |
| [Offline mock smoke](../bench/results/package/mock-smoke.json) | MEASURED local | One-command launch, reduced motion on/off, no external requests and SSE restart/reconnect |

The committed source bundle is produced by `python tools/bundle.py`. Its manifest
in `dist/bundle-manifest.json` records an exact Git commit and file hashes; the
archive excludes dirty working-tree files, private configuration and wallet data.
That artifact is local, not uploaded or submitted. A clean-checkout report records
the exact packaged revision separately.
# Latest review evidence, 10 November 2026

- [Completed Haiku calibration, ineligible; holdout untouched](../bench/results/m3-v2/haiku-qualification-result.json)
- [Historical Sonnet zero-cost preflight](../bench/results/m3-v2/sonnet-cost-preflight.json) and [superseded $8 plan](../bench/results/m3-v2/sonnet-qualification-plan.json)

- [Semantic verifier review and remaining gates](REVIEW_20261110.md)
- [Current role-aware study report](../bench/results/m3-v2/report.json)
- [Holdout frozen before model output](../bench/results/m3-v2/dataset/manifest.json)
- [Historical outputs re-scored, no new calls](../bench/results/m3-v2/historical-rescore.json)
- [Approved paid attempt and safe stop](../bench/results/m3-v2/paid-qualification-status.json)
- [Approved historical credit-only continuation plan](../bench/results/m3-v2/direct-continuation-plan.json)
- [Current signed fault proof](../bench/results/faults/current-paid-fault-20261110.json)
- [Current signed seller acknowledgement; no refund](../bench/results/completion-20261110/current-seller-fault-acknowledgement.json)
- [Separate frozen difficult comparison corpus](../bench/results/m4-v2/dataset/manifest.json)

Historical dated evidence follows. A re-score, frozen source or MOCK test is not a
new live model/payment result.

---
