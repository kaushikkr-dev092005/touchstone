# Decide whether to buy inference

Current evidence, 13 November: Sonnet 5.5 is qualified for synthetic invoice review
drafts under unchanged criteria. Its untouched holdout produced 59/60 strictly
correct drafts, **0 candidates and 60 review cases**. Offline truth scoring does
not replace runtime semantic verification or authorize invoice payment. The
completed matched live comparison favors premium over the ladder on strict-correct
count and provider cost per correct output; it does not demonstrate an adaptive
routing advantage. See the [current qualification](../bench/results/m3-v2/sonnet-qualification-result.json)
and [live comparison](POLICY_LIVE_CONTINUATION.md).

The sections below preserve the earlier preflight experiments and their original
status. Statements about no qualified model or no paid result describe those
earlier experiments, not the current Sonnet qualification and integrated proof.

M3 update, 3 November: the new `invoice_extraction` contract accepts raw text plus typed PO/payment records, with no pre-supplied extraction labels. `python tools/m3.py build` generates 180 synthetic sources and measures tool-only coverage before model calls. The separate offline scorer uses known generated truth; the online checker uses exact spans and integer arithmetic only. Current result: 24/180 tool extractions, zero model measurements and no qualified M3 model. Historical model profiles do not qualify this domain. See [M3 report](M3_REPORT.md) and [runbook](M3_RUNBOOK.md).

M3 retains the existing deduplicated Wilson lower-bound target (95%, at least 20 sources), requires the complete 120-source calibration set and a separate complete 60-source held-out validation with at least 95% exact extraction and zero observed false accepts. Neither MOCK profiles, stale provenance nor an incomplete/stopped profile can qualify. No demo-tier relaxation is enabled. The Planning panel is a no-payment preview. Explicit engine/paid-profiler integration tools remain operator tests requiring their own spend mandate; offline eligibility never grants financial permission.

Touchstone now has an executable preflight planner alongside the financial simulator. It solves a small set of typed tasks locally and pauses on unsupported inputs. Run `python -m touchstone plan` for the authored examples, or pass `--input path/to/tasks.json` for public tasks. Decisions are written to `data/local-plan.json`; no account credentials, network requests or payments are used.

## Supported contracts

| Task | Local tool accepts | Otherwise |
|---|---|---|
| Arithmetic | 1–1000 nonnegative integer cent amounts; a nonnegative discount no greater than the sum; total at most 10^12 cents; exactly the documented fields | Review |
| Invoice | A complete, anchored USD invoice template with one invoice ID, positive quantity, integer unit price and tax; bounded total | Review |
| Ticket | One of the three exact documented fixture messages | Review |

Unknown fields, booleans as money, float amounts, extra invoice text, foreign currency, paraphrases, quotations and ambiguous tickets do not qualify. These contracts are intentionally narrow. The online simulator verifier remains a separate component; its broader source rules are not used to enlarge the tool's supported domain.

Example input:

```json
{
  "id": "invoice-calculation-001",
  "kind": "arithmetic",
  "source": {"amounts_cents": [1250, 275, 499], "discount_cents": 24}
}
```

This returns `LOCAL_TOOL` and `{"total_cents": 2000}`. An unfamiliar request such as “My transfer is pending, but the beneficiary says their bank returned it” returns `REVIEW_REQUIRED`, with no accepted answer. Review is an unresolved task, not success.

## Model evidence gate

`python -m touchstone procurement-evidence` screens the actual measured profiles by task type. It checks source-code hashes, paired case identities and decoding configuration before analyzing outputs. Model and runtime hashes accompany the report. Stale artifacts are not shown as current evidence in the dashboard.

Seeds 41 and 42 supply calibration observations; seed 43 supplies separate evaluation observations. Because all profiles were inspected in earlier work, this is a retrospective partition, not an untouched prospective holdout. A fresh evaluation is still required before a deployment claim.

Repeated identical sources count once. A repeated source counts as correct only if all its calibration outputs are correct. This prevents the three ticket templates from masquerading as many independent examples. Similar templates still introduce dependence, so deduplication does not establish representative independent sampling.

The default screen requires at least 20 unique sources and a lower endpoint of the two-sided 95% Wilson interval at or above 95% success. Meeting the minimum sample count alone cannot pass the screen: even 20/20 correct is insufficient. `Task.min_quality` is a per-response check score and is not reused as a probability target. The formula follows [NIST's Wilson interval description](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

All six current provider/task combinations fail the screen. Passing this offline screen would still not authorize a financial transaction: source-domain validation, current provider identity, quote and ledger checks, funded adapter integration and recovery proof remain required. The standalone Metal CLI is an explicit integration test tool and is not governed by this offline report; it must not be described as an autonomous quality-gated buyer.

## Invoice-exception preflight

`python -m touchstone plan --input path/to/tasks.json` accepts a bounded `invoice_exception` task with an OCR text string, cited invoice fields and line items, one typed purchase order, and typed payment history. Every citation is a `{ "value": "...", "start": 0, "end": 0 }` character span whose value must match the source text exactly; verified spans are returned for review. The currently supported currency is USD with explicit two-decimal amounts. Line totals, subtotal, tax and invoice total are recomputed with integer cents. Supplier/PO mismatches, duplicate or in-progress payments and purchase-order limit overruns are returned as review issues.

Even a clean match returns `REVIEW_REQUIRED` with `MATCHED_REQUIRES_HUMAN_APPROVAL`; exceptions return `EXCEPTION_REQUIRES_HUMAN_REVIEW`. Unsupported or malformed inputs abstain. The tool has no payment adapter and reports `payments_sent: 0` and `live_purchase_authorized: false`. The test fixtures are authored synthetic cases: this code is an initial deterministic baseline, not representative evidence, a prospective model evaluation, or payment authorization. See `tests/test_invoice_exceptions.py`.

## Public dataset assessment

FATURA2 is licensed CC BY 4.0, but its authors describe 10,000 generated invoices per background variant from 50 templates (200 instances per template). It can support a synthetic layout-generalization probe, not representative vendor/payment exception qualification ([Zenodo record](https://zenodo.org/records/10371464), [dataset paper](https://arxiv.org/abs/2311.11856)). Another public set contains 813 Portuguese invoices/receipts from one private company, with seller/buyer tax-ID annotations; its single-company and language scope is insufficient for the intended evaluation and needs a privacy review before use ([Zenodo record](https://zenodo.org/records/6371710)). Neither source provides the paired purchase-order/payment history required by the proposed exception workflow. No dataset files are retained in the repository, and no model was evaluated on either corpus.

## What the experiment changes

The generated workload is a useful accounting stress test, but a poor proof of the commercial value of buying model inference. Bounded tools solve 1,000/1,000 generated cases across seeds 101–105 with no inference purchases. This does not mean processing is free: CPU, maintenance, review and service charges are not priced in that baseline. The original model results and negative cheap-first replay remain intact.

The hackathon story should demonstrate three decisions: resolve a supported calculation locally; pause when evidence is insufficient; buy an eligible inference service within a customer mandate once the live integration is proven. Buying more inference is not itself a success metric.

## Next finance-operations experiment

Use an invoice-exception workflow with independently labeled, de-identified sources. Give the agent an invoice document plus typed purchase-order and payment records. The model's bounded responsibility is extracting fields and citing source spans from an unfamiliar layout. Deterministic tools then recompute totals and compare references. Uncertain extraction or contradictory evidence requires review; it never initiates a real bank transfer.

1. Define source formats, schema, currency handling, citations, rejection conditions and the review outcome before collecting measurements.
2. Split by document template/vendor before evaluating, so near-duplicate layouts cannot leak between calibration and evaluation. Retain a separate adversarial set for duplicate IDs, altered totals and instructions embedded in documents.
3. Compare code-only extraction, each model alone, and eligibility-gated procurement. Include abstentions, human-review workload, false acceptance, paid failures, latency and all charges.
4. Freeze prompts and tool versions before a new prospective evaluation. Current fixture profiles cannot authorize this new domain.
5. Connect one eligible provider to the per-job clearing wallet, preserve a receipt across a forced interruption, and link actual spend to sandbox capture. Expand to three concurrent holds only after that single-job proof.

M3 implements a synthetic first experiment with these extraction/checking boundaries, fixed layout split and conservative baseline. Representative documents, independent human labeling and a paid end-to-end result have not yet been produced. Decorative OCR-style noise in generated sources is not a real OCR qualification set.
