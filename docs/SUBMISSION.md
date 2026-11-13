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
  All 60 holdout cases required human review: 0 automatically accepted candidates.
  The 59 correct drafts exceed the bounded parser's coverage, but offline truth
  scoring is separate from runtime verification. Synthetic sources; no automatic
  invoice payment or real-world accuracy claim. Zero false accepts with no
  candidates does not establish acceptance precision.
- One integrated run linked a customer-approved Airwallex sandbox USD 1 hold,
  qualified 0.01 USDZ model result, review verdict, USD 0.01 capture and controlled
  closure. Unused tokens stayed in their original wallet. No fiat/token bridge.
- A real paid wrong answer has a reproducible signed fault proof and current
  seller acknowledgement. The seller rejected credit; no refund moved.
- Earlier hard-kill/recovery evidence shows one paid receipt recovered twice
  without another purchase. Clearing preconfirmation is not final settlement.
- The matched four-policy study completed 64/64 outcomes on 16 sources: 32 actual
  paid receipts, 10 confirmed-unpaid failures and no pending invoice. Real provider
  spend was 0.263390 USDZ. Premium scored 7/16 strictly correct, ladder 3/16; this
  does not support a general savings claim. [Current results](POLICY_LIVE_CONTINUATION.md).

The live `real-touchstone` router uses fixed local-first escalation after verifier
rejection, not learned quality selection. The separate comparison's ladder tries
tools, defers known duplicates and uses only qualified tiers; it skipped the
unqualified local model. Premium beat the ladder on strict-correct count and
provider USDZ per correct output in this study. Implemented sampling/quality-based
strategies have no demonstrated live financial advantage here.

[Final review](LIVE_PROOFS_20261110.md), [raw evidence](EVIDENCE_INDEX.md),
[controls and costs](../bench/results/completion-20261110/final-proof-status.json).

## Controls and validation

Signed mandates now bind a separate allowlisted human EOA's EIP-712 signature to
the exact inference task, quote, provider, spending limits and verifier policy.
The ledger consumes approval atomically with dispatch authorization; the Node
payer independently checks it. Unsigned and tampered proposals are blocked. This
feature is **controlled/local validated**, with real cryptography and MOCK rails;
historical financial proofs are not relabelled signed. [Design, tests and demo](SIGNED_MANDATES.md).

Role-aware value binding prevents authentic citations of the wrong field from
passing. Candidate, review and rejection are separate. Integer micro-unit
accounting, atomic reservations, idempotency conflicts and a hash-chained audit
preserve charges and uncertain exposure. Per-call, aggregate, API-credit and native
fee caps are separate. No automatic top-up or withdrawal occurred in final proofs.

The updated $4.50 total Claude ceiling is enforced; conservative exposure is $4.229541,
including $2.027200 of retained uncertainty allowances. New hosted cash was $0. GPU startup
is refused at 65°C and owned inference stops at 75°C/throttling/missing telemetry.
The sampled continuation peak was 60°C and the model was stopped afterwards.

[Release validation](../bench/results/m3-v2/release-validation.json) records the
exact tested source revision, Python/Node tests, controlled financial proofs,
frontend build, browser security, mobile layout and offline asset checks.
[Captioned recording and reproduction](DEMO_SCRIPT.md).

## Submission fields still controlled by the operator

This is prepared material, not a submitted entry. The signed-in portal must confirm
registration, team identity, category, video requirements and submission receipt.
Sandbox issuing creation/card controls, merchant configuration, 100 synthetic
products and guest OAuth/MCP are verified. Visa onboarding/trust remains external.
[Current account checks and completed issuing proof](EXTERNAL_ACCESS.md)
separate those results. Kit 12's inference-sourcing story is the target; no completed
Kit 11 settlement, real Visa merchant payment or production certification is claimed.
