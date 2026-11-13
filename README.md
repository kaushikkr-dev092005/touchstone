# Touchstone

Budgeted inference procurement with source checks, durable receipts and payment recovery.
An agent reserves an approved budget, buys a result, verifies it, and accounts for
every attempt. A rejected answer can still cost money.

## For judges

Watch the [captioned demonstration](docs/recordings/touchstone-demo.webm)
([transcript](docs/recordings/demo-transcript.md)): saved measured proofs and a
separately labelled simulated workflow. No new live purchase is made in the video.

Run the dashboard without accounts, keys, model downloads or spending. Python 3.11+
is sufficient:

```text
python tools/run_mock.py
```

Open **http://127.0.0.1:8088** and select **Run three-job demo**. Watch jobs share
limited float, pause at their budgets, and close with reconciled receipts. Inspect
the transaction drawer and audit trail. A paused simulator job can receive a
versioned human limit approval using its existing float.

The three-job scenario is **SIMULATED**. Saved real evidence is displayed separately.
The dashboard does not silently turn a failed live service into a simulation.

| Evidence | What ran | Boundary |
|---|---|---|
| [Airwallex hosted checkout](bench/results/m1/current-hosted-card-proof.json) | Sandbox USD 1 authorization and USD 0.01 capture | Separate historical sandbox run; issuer release timing unmeasured |
| [Metal recovery](bench/results/m2/live-single-call-final.json) | A 0.01 USDZ purchase survived process death and recovered without another charge | Testnet; purchased answer failed verification |
| [Current fault acknowledgement](bench/results/completion-20261110/current-seller-fault-acknowledgement.json) | Real signed delivery, reproduced wrong answer, signed seller response | Seller rejected credit; no refund moved |
| [Role-aware verifier review](docs/REVIEW_20261110.md) | Labels selected as field values now fail semantic checks independently of arithmetic | Bounded source grammar; unfamiliar/ambiguous roles require review |
| [Recorded qualification](bench/results/m3-v2/sonnet-qualification-result.json) | Sonnet 5.5: 120/120 calibration, 59/60 untouched holdout trials strictly correct | Holdout: 0 candidates, 60 review cases; useful synthetic review drafts, no automatic invoice payments |
| [Integrated financial proof](bench/results/m3-v2/integrated-receipt.json) | One qualified paid draft, sandbox USD 1 hold / USD 0.01 capture, 0.01 USDZ provider charge, customer closed | Correct draft requires human review; unused tokens retained; no fiat/token bridge |
| [Matched live comparison](bench/results/m4-live-20261112/actual-financial-results.json) | 64/64 outcomes; 32 actual paid receipts and 10 confirmed-unpaid failures; 0.263390 USDZ | Real model calls and testnet payments; premium scored 7/16 strict correct, ladder 3/16; no general savings claim |
| [Paid qualification status](bench/results/m3-v2/paid-qualification-status.json) | 1.32 USDZ deposited; 0.01 USDZ bought one correct hosted result; next request confirmed unpaid | Stopped without retry; API usage estimate separate from USDZ |

**Candidate, review and rejected are separate outcomes.** A candidate is a checked
extraction, not authorization to pay an invoice. Statistical qualification criteria
have not been lowered. Re-scoring old answers is never presented as a fresh model run.

**The live routing strategy is fixed escalation.** In `touchstone/router.py`,
`real-touchstone` prefers local GPU quotes and can escalate to hosted premium after
verifier rejection, within spending limits. That branch does not use learned
quality estimates or Thompson sampling. Those other strategies exist in code;
their presence is not evidence of improved live financial outcomes.

The completed comparison's ladder has a separate implementation in
`touchstone/comparison.py`: tools first, defer known duplicate references, then
qualified model tiers. The unqualified local tier was skipped by the ladder. Premium
produced 7/16 strictly correct outputs at 0.018571 USDZ per correct output; the ladder
produced 3/16 at 0.020000 USDZ. Lower total ladder spend does not establish better
cost effectiveness. These provider-only costs exclude separately reported API
credits and unpriced review. Adaptive routing superiority remains unproven.

**59/60 means correct human-review drafts, not automated invoice payments.**
Offline scoring compares outputs with the synthetic dataset's known truth; the
runtime verifier has no access to that truth and cannot certify unfamiliar source
roles. All 60 holdout trials required review, including the interrupted trial
counted incorrect. Zero false accepts with zero candidates does not establish
acceptance precision. Even a checked candidate never authorizes invoice payment.

Airwallex fiat and Metal USDZ stay separately accounted. This project performs no
fiat-to-token bridge. Metal receipt preconfirmation is not independent proof of final
settlement. [Evidence index](docs/EVIDENCE_INDEX.md) · [Serious review and remaining gates](docs/REVIEW_20261110.md).

## Features

- **Signed mandates:** independent human-wallet EIP-712 approval of exact task,
  quote, provider, caps and verifier policy; atomic ledger enforcement and an
  independent Node payer check. New real purchases fail closed without approval.
  [Security design and no-spend demo](docs/SIGNED_MANDATES.md) ·
  [MOCK/local proof](bench/results/signed-mandates/local-proof.json).
- Integer micro-unit ledger, atomic reservations, per-call and aggregate caps,
  idempotency conflicts, durable recovery and a hash-chained audit.
- Source-based arithmetic and invoice-role checks, PO/payment exception review,
  separate offline truth scoring and unchanged statistical qualification gates.
- Local tools, hosted and GPU provider adapters, explicit escalation, and matched
  tools-only / cheapest / premium / ladder policy comparison.
- Guarded Airwallex sandbox authorization/capture, hosted checkout, FX reconciliation,
  issuing-readiness diagnostics and a unified integration receipt.
- Signed fault evidence and seller acknowledgement, with refunds tracked separately.
- Responsive dashboard, transaction search/export, live/simulated disclosures and
  conservative GPU temperature supervision.

Issuing creation is verified: one READY synthetic delegate and one capped sandbox
card, without a merchant charge. Agentic Commerce merchant configuration is active,
100 synthetic products are uploaded, and guest OAuth/MCP discovery passes.
[Open the sandbox merchant](https://touchstone-sandbox-merchant.sublimeoak1.chatgpt.site/merchant).
Visa approval remains pending. [Proofs and boundaries](docs/EXTERNAL_ACCESS.md).
The matched comparison and submission status are recorded in the
[current review](docs/REVIEW_20261110.md). [Detailed feature boundaries](docs/FEATURES.md).
The [12 November comparison completion](docs/POLICY_LIVE_CONTINUATION.md) supersedes
the earlier 12/64 stop. Conservative total Claude exposure is $4.229541 against the
user's updated $4.50 ceiling; estimated reported usage and uncertainty stay separate.

## Operator and developer paths

Start installed account adapters and the dashboard while keeping the GPU model off:

```text
python tools/run_project.py --skip-model
```

Full local model startup uses `python tools/run_project.py`. The launcher refuses
hot startup and stops its own inference process at the configured temperature limit.
[Runtime/setup guide](docs/RUNNING.md) · [Account setup](docs/ACCOUNT_SETUP.md).

Zero-cost checks:

Signature tests use the existing Node/viem dependencies; install them with
`npm ci --ignore-scripts --no-fund` inside `integrations/metal` first.

```text
python -m unittest discover -s tests
python tools/check_dashboard.py
python tools/fault_proof.py verify --input bench/results/faults/current-paid-fault-20261110.json --check-network
```

The last command performs read-only signature/chain/operator checks. It neither
pays nor refunds. The [release validation](bench/results/m3-v2/release-validation.json)
records the tested revision and check counts; controlled adapters remain MOCK
evidence. [Validation runbook](docs/VALIDATION_RUNBOOK.md).

Financial execution requires a concrete, explicitly approved scope and caps.
Qualification approval is not approval for a comparison, card issuance or merchant
payment. [Invoice qualification](docs/M3_RUNBOOK.md) · [Policy comparison](docs/M4_RUNBOOK.md).

The [public website](https://touchstone-sandbox-merchant.sublimeoak1.chatgpt.site)
shares its landing page, dashboard and ledger on one origin. A cinematic vault intro
ignites into a ray-marched black hole behind the hero, and the same vault plays before
workspace entry ([landing notes](docs/landing.md)). Public views show saved evidence only.

For the same interface locally, run `bun install --frozen-lockfile` and `bun run build`
in `apps/web`, start the Python server, and open `/site/`. `/dashboard` and `/ledger`
embed the existing local operator console with its session protections. `/console`
and the legacy root dashboard still work without a frontend build.
[Website behavior and checks](docs/WEBSITE.md).

Built for Airwallex Agentic Banking Hackathon Kit 12. [Submission draft](docs/SUBMISSION.md)
· [Demo script](docs/DEMO_SCRIPT.md) · [MIT license](LICENSE).
