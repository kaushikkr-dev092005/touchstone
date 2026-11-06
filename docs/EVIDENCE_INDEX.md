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
| [Issuing doctor](../bench/results/features/card-readiness.json) | BLOCKED | Real read returned 401; no card created |
| [Signed intent](../bench/results/features/tap-probe.json) | MOCK identity / MEASURED protocol check | Controlled HTTP acceptance and replay rejection; no Visa trust/approval or payment |
| [Feature tests](../bench/results/features/validation.json) | MEASURED local | Test counts, artifact hashes, browser/security checks |
| [Clean source verification](../bench/results/package/clean-checkout.json) | MEASURED Windows | Exact committed archive, pinned install, 247 Python/47 Node tests and browser checks |
| [Offline mock smoke](../bench/results/package/mock-smoke.json) | MEASURED local | One-command launch, reduced motion on/off, no external requests and SSE restart/reconnect |

The committed source bundle is produced by `python tools/bundle.py`. Its manifest
in `dist/bundle-manifest.json` records an exact Git commit and file hashes; the
archive excludes dirty working-tree files, private configuration and wallet data.
That artifact is local, not uploaded or submitted. A clean-checkout report records
the exact packaged revision separately.
