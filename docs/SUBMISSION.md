# Touchstone — submission draft, 6 November 2026

## One sentence

The financial trust layer for autonomous agents: pay for proof, not promises.
Reserve an approved mandate, buy inference when justified, check the result,
recover uncertain payments and account for every attempt. Payment precedes checking.

## Proven with saved evidence

- **MEASURED testnet:** historical 0.01 USDZ paid inference, incorrect answer,
  rejection and identical receipt/delivery replay. Historical unused 0.09 USDZ
  was returned separately.
- **MEASURED sandbox:** exactly 1 USD → 0.89 EUR FX settled/history-matched;
  separate hosted 1 USD authorization captured 0.01 USD. Issuer release timing
  remains unmeasured.
- **MEASURED testnet:** a new 0.02 USDZ funded job wallet made one 0.01 USDZ engine
  purchase, survived hard process death and recovered twice without another charge.
  The remaining 0.01 USDZ was not withdrawn. The answer failed verification.
- **MEASURED historical fault evidence:** buyer-signed commitment and reproducible
  1,250/2,000-cent counterexample with original payment signatures checked. The
  historical provider output was unsigned. No refund or actual credit was issued.
- **MEASURED on SIMULATED sources:** both local models measured on 180 sources each,
  both ineligible. Deterministic extraction coverage is 13.3%; useful paid inference
  remains blocked.
- **MEASURED local controls:** Python/Node/browser checks, audit chain, immutable
  billing, atomic reservation and recovery. Controlled financial adapters are MOCK.

All Metal receipts here are preconfirmed, not independently proven finally settled.
The three-job short-float financial story remains SIMULATED: 2.50 USD holds,
1.50 USD operator float, immutable customer-pays/merchant-absorbs policies.
[Evidence index](EVIDENCE_INDEX.md), [validation](VALIDATION.md).

## New extensions and boundaries

Signed fault receipts bind independently checkable evidence; signatures alone do
not prove provider fault or cause a refund. FX-aware comparison includes currencies,
fees, quality and retry assumptions; provider prices are illustrative and no fiat
merchant dispatch is authorized. GPU samples are real; uncalibrated price markups
are disabled. CardRail has guarded issuing/reconciliation, but real issuing reads
return 401. Controlled RFC 9421 signed intent uses a local identity, rejects replay
and establishes no Visa credentials, approval, payment or award eligibility.
[Implementation report](FEATURES.md).

The Kit 12 inference-sourcing story follows the [organizer guide](https://airwallexdev.com/guide).
Do not claim Kit 11 dispute settlement or real mandate rebalancing from a simulation.
Airwallex fiat and Metal USDZ are separate accounts; there is no bridge.

## Demonstration and packaging

Python 3.11+ only, Windows/macOS/Linux: `python tools/run_mock.py`, then
http://127.0.0.1:8088. Private configuration is ignored and no money moves.
Installed model stack: `python tools/run_project.py`. [Demo script](DEMO_SCRIPT.md),
[runtime](RUNNING.md). `python tools/bundle.py` packages an explicit committed tree;
the manifest records its commit and hashes. A local bundle is not submission.

## Outstanding human/external gates

1. Hosted credentials/partner-credit authorization and an actually qualified model.
2. Fresh aggregate caps and funding for M4; no 30–50-call live comparison or live
   outage/quality study has been recorded. Earlier transaction approvals are consumed.
3. Issuing permissions, a separate card cap and supported merchant flow; genuine
   Visa credentials/trust before claiming TAP interoperability or an award.
4. Observed throughput/calibration before capacity-based economic pricing claims.
5. Accepted registration, personal portal deadline/schema, sponsor tooling eligibility,
   video limit, operator recording, manual submission and receipt confirmation.

## Submission status

Repository github.com/kaushikkr-dev092005/touchstone was verified public on
2 November; MIT licensing is included. Local commits are not a remote push or a
GitHub CI result. Feature freeze is scheduled for 11 November. Internal submission
deadline is 13 November 18:29 UTC / 23:59 IST; the previously fetched official page
listed 15 November build completion, so confirm the signed-in portal deadline.
No registration, recording or submission has been performed by the agent.
