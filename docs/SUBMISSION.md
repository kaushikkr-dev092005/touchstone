# Touchstone — submission draft, 10 November 2026

Budgeted AI procurement with source verification, durable payment recovery and
signed fault evidence. An approved mandate controls spending; every failed attempt
and actual charge remains visible.

Repository: https://github.com/kaushikkr-dev092005/touchstone

## Run in three minutes

Python 3.11+, no credentials, model download or spending:

```text
python tools/run_mock.py
```

Open http://127.0.0.1:8088 and select **Run three-job demo**. Inspect budgets,
halt/resume, transaction filters, receipts and closure. New financial actions in
this path are SIMULATED. Saved sandbox/testnet proofs have separate labels.

## Measured results

- Sonnet 5.5 qualified with unchanged criteria: 120/120 strictly correct calibration
  trials and 59/60 fresh holdout trials. An interrupted request counts incorrect.
  The 59 correct review drafts exceed the bounded parser's coverage. Synthetic
  sources; no automatic invoice payment or real-world accuracy claim.
- One integrated run linked a customer-approved Airwallex sandbox USD 1 hold,
  qualified 0.01 USDZ model result, review verdict, USD 0.01 capture and controlled
  closure. Unused tokens stayed in their original wallet. No fiat/token bridge.
- A real paid wrong answer has a reproducible signed fault proof and current
  seller acknowledgement. The seller rejected credit; no refund moved.
- Earlier hard-kill/recovery evidence shows one paid receipt recovered twice
  without another purchase. Clearing preconfirmation is not final settlement.
- The matched four-policy study stopped safely after clearing refusals and the
  conservative credit guard: 12/64 policy outcomes, 3 actual charges, 5 confirmed
  unpaid failures, no pending invoice. It supports no savings claim.

[Final review](LIVE_PROOFS_20261110.md), [raw evidence](EVIDENCE_INDEX.md),
[controls and costs](../bench/results/completion-20261110/final-proof-status.json).

## Controls and validation

Role-aware value binding prevents authentic citations of the wrong field from
passing. Candidate, review and rejection are separate. Integer micro-unit
accounting, atomic reservations, idempotency conflicts and a hash-chained audit
preserve charges and uncertain exposure. Per-call, aggregate, API-credit and native
fee caps are separate. No automatic top-up or withdrawal occurred in final proofs.

The $3 total Claude ceiling is enforced; conservative exposure is $2.919117,
including $0.9072 of uncertainty allowances. New hosted cash was $0. GPU startup
is refused at 65°C and owned inference stops at 75°C/throttling/missing telemetry.
The sampled run peak was 51°C and the model was stopped afterwards.

[Release validation](../bench/results/m3-v2/release-validation.json) records the
exact tested source revision, Python/Node tests, controlled financial proofs,
frontend build, browser security, mobile layout and offline asset checks.
[Captioned recording and reproduction](DEMO_SCRIPT.md).

## Submission fields still controlled by the operator

This is prepared material, not a submitted entry. The signed-in portal must confirm
registration, team identity, category, video requirements and submission receipt.
Airwallex issuing writes/merchant access and Visa onboarding/trust are external
access requirements. Kit 12's inference-sourcing story is the target; no completed
Kit 11 settlement, real Visa merchant payment or production certification is claimed.
