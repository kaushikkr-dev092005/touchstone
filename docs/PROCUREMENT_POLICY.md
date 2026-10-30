# Decide whether to buy inference

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

This defines the next experiment; representative documents, independent labeling and a paid end-to-end result have not yet been produced.
