# Final live proof review, 10 November 2026

**12 November update:** the matched comparison now has 64/64 outcomes and 32 actual
paid receipts. [Current comparison results and $4.50 guard](POLICY_LIVE_CONTINUATION.md)
supersede the incomplete comparison and credit totals in this historical snapshot.

The qualified-model sandbox integration completed. The matched comparison stopped
at its credit guard after repeated clearing refusals. Capped issuing creation is
now verified. Merchant onboarding, Visa approval and signed-in portal submission
remain external requirements.

## Completed evidence

- **Semantic verification:** role-bound source values, independent arithmetic,
  identifier/PO checks and candidate/review/rejected metrics. Adversarial coverage
  includes labels selected as values, swapped roles, ambiguous headers, OCR noise,
  duplicate IDs/rows and mismatched purchase orders. No review becomes acceptance.
- **Qualified useful model:** Sonnet 5.5 scored 120/120 calibration trials, Wilson
  95% lower bound 96.90%, then 59/60 fresh holdout trials. One interrupted request
  counts as incorrect and was not retried. There were zero false accepts, zero
  holdout candidates and 59 correct review drafts beyond the deterministic parser.
  Prompts and statistical criteria were unchanged. Sources are synthetic.
- **Integrated proof:** the approved sandbox test-card checkout authorized USD 1;
  one Sonnet result cost 0.01 USDZ; the extraction was a correct human-review draft;
  customer capture was USD 0.01; the workflow reached `CLOSED_FLOAT_RETAINED`.
  Remaining 0.01 USDZ stayed in the original wallet. No invoice was paid.
- **Dispute assurance:** the real paid 1,400/2,000-cent fault has verified buyer,
  provider-delivery and operator signatures and a current signed seller response.
  Seller decision `ACKNOWLEDGED_REJECTED`, credit `NONE`, refund false.

[Qualification](../bench/results/m3-v2/sonnet-qualification-result.json),
[unified receipt](../bench/results/m3-v2/integrated-receipt.json),
[current fault](../bench/results/faults/current-paid-fault-20261110.json),
[seller response](../bench/results/completion-20261110/current-seller-fault-acknowledgement.json).

## Matched comparison: incomplete, no savings claim

The frozen separate corpus has one familiar control and 15 difficult sources,
matched across tools-only, cheapest, premium and qualified ladder policies. Twelve
of 64 policy outcomes completed: three sources per policy. Eight purchase attempts
produced three charges and five confirmed-unpaid failures. No failed request was
repeated; each counts as an incorrect trial. Local baselines were explicitly
authorized as experimental and did not become qualified.

| Policy | Strict correct / completed | Candidate / review / rejected | Charged USDZ | USDZ / strict correct |
|---|---:|---:|---:|---:|
| Tools only | 1/3 | 1 / 2 / 0 | 0 | 0 |
| Cheapest | 1/3 | 1 / 2 / 0 | 0.005 | 0.005 |
| Premium | 1/3 | 1 / 2 / 0 | 0.010 | 0.010 |
| Touchstone ladder | 1/3 | 1 / 2 / 0 | 0.010 | 0.010 |

This partial sample does not establish a policy ranking. Tools won the familiar
control at zero provider cost; no correct novel-layout draft was measured in this
partial comparison. Qualification results must not be substituted for these trials.
Hosted API estimates and unreported allowances are separate from USDZ; unknown
per-policy API cost remains null. All failed calls and charges remain in the report.

A diagnostic captured HTTP 409 from clearing `/context` before payment. Read-only
SDK inspection found no pending invoice/new receipt for each failed request. The
operator balance matches three charges. Five local reservations were voided with
this protocol evidence, not on the basis of an empty remote lookup. Untouched
tasks continued under the original approval until the conservative credit guard
could not reserve another call. No cap was raised. The planned outage/quality-drop
indices were not reached, so the 30–50-purchase live gate remains unmet.

[Raw report](../bench/results/m4-v2/live-report.json),
[exact plan](../bench/results/m4-v2/final-plan.json),
[read-only readiness](../bench/results/m4-v2/clearing-readiness.json),
[sanitized HTTP observations](../bench/results/m4-v2/clearing-http-observations.json).

## Financial and GPU controls

The user's **$3 total Claude ceiling** supersedes the historical $8 authorization.
Current reported-usage estimates total **$2.011917**; retained unreported-usage
allowances total **$0.9072**; conservative exposure is **$2.919117**. Remaining
allowance is **$0.080883**, insufficient for the next conservative Sonnet reservation.
This is not independently reconciled API billing. New hosted cash: **$0**.

Final-proof deposits were exactly **0.57 USDZ** in two wallets. Confirmed new provider
spend was **0.035 USDZ**: 0.01 integration and 0.025 comparison. Remaining **0.535
USDZ** is retained, not withdrawn or refunded. The earlier qualification wallet's
1.31 USDZ is separate. On-chain funding transactions, actual native fees and each
paid/failed request are recorded in the final status artifact. Clearing receipts
are preconfirmed; no independent finality or fiat/token bridge is claimed.

The local model used a 65°C startup refusal and a 75°C stop, with five-second
supervision and no automatic thermal restart. Sampled peak during this run was
**51°C**. The owned model process was stopped afterwards. Software supervision
cannot guarantee a hardware temperature under every condition.

[Final controls, wallet balances and call log](../bench/results/completion-20261110/final-proof-status.json),
[GPU samples](../bench/results/m4-v2/gpu-monitor.json).

## Remaining external steps

Issuing reads and the approved one-delegate/one-card writes are verified. The
single-use USD 0.01 card has its original controls and an earlier server-truncated
expiry. There was no merchant charge. Agentic Commerce configuration is now active,
100 synthetic products were uploaded without failures, and guest OAuth/MCP plus a
read-only catalog lookup pass. See the
[exact account setup and prepared support requests](EXTERNAL_ACCESS.md).
Visa registered-agent onboarding/trust remains unverified. The
signed-in hackathon portal must provide registration/submission access and confirm
required fields/video limits. The local recording, source archive and submission
draft are reviewable deliverables, not a confirmed portal submission. A future
study needs reconciled credit availability and a fresh scope if its terms change;
these consumed approvals never authorize extra purchases.
