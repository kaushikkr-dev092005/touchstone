# Touchstone

Budgeted inference procurement with source checks, durable receipts and payment recovery.
An agent reserves an approved budget, buys a result, verifies it, and accounts for
every attempt. A rejected answer can still cost money.

## For judges

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
| [Current qualification](bench/results/m3-v2/haiku-qualification-result.json) | Haiku 5.5: 107/120 strictly correct calibration trials; zero false accepts | Ineligible under unchanged criteria; fresh holdout remains unmeasured |
| [Paid qualification status](bench/results/m3-v2/paid-qualification-status.json) | 1.32 USDZ deposited; 0.01 USDZ bought one correct hosted result; next request confirmed unpaid | Stopped without retry; API usage estimate separate from USDZ |

**Candidate, review and rejected are separate outcomes.** A candidate is a checked
extraction, not authorization to pay an invoice. Statistical qualification criteria
have not been lowered. Re-scoring old answers is never presented as a fresh model run.

Airwallex fiat and Metal USDZ stay separately accounted. This project performs no
fiat-to-token bridge. Metal receipt preconfirmation is not independent proof of final
settlement. [Evidence index](docs/EVIDENCE_INDEX.md) · [Serious review and remaining gates](docs/REVIEW_20261110.md).

## Features

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

Issuing reads now pass; issuing writes/merchant access and Visa onboarding remain
external gates. A qualified model, authorized integrated financial run and live
matched comparison remain unfinished. [Detailed feature boundaries](docs/FEATURES.md).

## Operator and developer paths

Start installed account adapters and the dashboard while keeping the GPU model off:

```text
python tools/run_project.py --skip-model
```

Full local model startup uses `python tools/run_project.py`. The launcher refuses
hot startup and stops its own inference process at the configured temperature limit.
[Runtime/setup guide](docs/RUNNING.md) · [Account setup](docs/ACCOUNT_SETUP.md).

Zero-cost checks:

```text
python -m unittest discover -s tests
python tools/check_dashboard.py
python tools/fault_proof.py verify --input bench/results/faults/current-paid-fault-20261110.json --check-network
```

The last command performs read-only signature/chain/operator checks. It neither
pays nor refunds. Current local verification: **340 Python tests and 53 Node tests
passed**; controlled adapters remain MOCK evidence. [Validation runbook](docs/VALIDATION_RUNBOOK.md).

Financial execution requires a concrete, explicitly approved scope and caps.
Qualification approval is not approval for a comparison, card issuance or merchant
payment. [Invoice qualification](docs/M3_RUNBOOK.md) · [Policy comparison](docs/M4_RUNBOOK.md).

The optional landing page is at `/site/` after `bun install --frozen-lockfile` and
`bun run build` in `apps/web`. The dashboard requires no frontend build.

Built for Airwallex Agentic Banking Hackathon Kit 12. [Submission draft](docs/SUBMISSION.md)
· [Demo script](docs/DEMO_SCRIPT.md) · [MIT license](LICENSE).
