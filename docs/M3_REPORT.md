# M3 implementation report — 3 November 2026

## Current evidence — 5 November 2026

**MEASURED on SIMULATED sources:** both installed local models now have complete
**180-call** profiles, each with **120 calibration / 60 held-out sources** and at
least 20% measured GPU-memory headroom. Both produced **0 strict-correct extractions**
and **0 checker accepts** in each partition. Calls returned structured outputs;
these are citation/role correctness failures, not missing measurements or service errors.

The unchanged qualification gate correctly refuses both models. **Zero eligible models**;
useful paid inference and the hosted/reference tier remain BLOCKED. The conservative
tool baseline remains **24/180 (13.3%)** with zero observed false accepts; twelve of
those extractions still need exception review. Synthetic truth is offline and is not
evidence of representative invoice/OCR performance. No paid M3 call was made.

Evidence: [study report](../bench/results/m3/report.json),
[1.5B raw profile](../bench/results/m3/profiles/balanced.json),
[0.5B raw profile](../bench/results/m3/profiles/economy.json).
This satisfies the honest negative-result alternative, not the useful-inference goal.
No threshold was lowered. Hosted credentials, intended credit source and separate
aggregate call/spend approval remain human gates. M1/M2 now have their own independent
live proofs; they do not qualify a model for this workload.

## Historical report

The dated observations below describe their original runs; the current evidence above supersedes their readiness statements.

Implementation is complete. **BLOCKED: useful paid inference has not been demonstrated.** The alternative gate is an honest refusal: **zero current M3 models measured, zero eligible models, zero live purchases**. Models were not rejected on newly measured accuracy; their required measurements are missing. M1's real FX write and M2's live engine/recovery gates remain open.

## What changed

- Added 180 unique synthetic invoice sources across 12 layouts, with fixed template/vendor groups: 120 calibration sources and 60 held-out sources. Scenarios cover reordered/unfamiliar layouts, decorative OCR-style noise, missing fields, duplicate payment references and conflicting purchase orders. Known generated labels are saved separately from public model inputs.
- Added a bounded extraction contract, exact character citations, complete ITEM-row coverage, integer-cent arithmetic and typed PO/payment checks. Missing evidence or ambiguity requires review. No extraction verdict authorizes paying an invoice. Citations alone do not establish the semantic role of a span; offline scoring measures errors that the checker could accept.
- Added local profiling for the installed 0.5B/1.5B models, matching the running model to its installed GGUF hash and checking at least 20% GPU-memory headroom before/after calls. The operator starts the model. A completed call survives a later hardware-check failure. The optional context setting supports the larger extraction contract. No 3B model was installed or fit-tested.
- Extended the existing hosted Anthropic tier behind the same x402 seller. Premium profiling requires an explicit execute flag, a separately approved aggregate cap, an existing funded wallet, correct seller/network identity and a partner-credit declaration. The declaration is not verification of the upstream credit balance. Upstream dollar cost remains UNMEASURED.
- Optional reference extraction is a second paid request with its own receipt and wallet allocation. Both calls count toward the aggregate call limit and budget; failed answers remain charged. Disagreement or an uncertain payment stops/defers the result. Original invoice/receipt/delivery remain in the existing ignored Metal wallet journal; no automatic payment retry, deposit or withdrawal is performed.
- Calibration and held-out profiles merge without buying the same source again. Code/model provenance changes refuse a merge. Qualification retains the existing deduplicated 95% Wilson lower-bound target with at least 20 unique sources, requires the complete 120-case calibration partition and separately checks all 60 held-out cases (at least 95% exact extraction and zero observed false accepts). The threshold was not lowered.
- Added the three-task Planning panel: a known total uses a deterministic tool, an unfamiliar invoice stays BLOCKED without a qualified model, and an ambiguous duplicate requires a human. These are previews; they dispatch no payments. The session-token/SSE flow is retained.

## Evidence and test results

| Label | Artifact | Supported result |
|---|---|---|
| SIMULATED | [Corpus manifest](../bench/results/m3/dataset/manifest.json) | 180 unique generated sources; 120/60 template split; labels are not independently human-authored |
| MEASURED | [Study report](../bench/results/m3/report.json), [raw tool outputs](../bench/results/m3/baseline-raw.json) | Parser extracted 24/180 (13.3%); 156 abstentions; zero observed false accepts on these synthetic cases |
| BLOCKED | [Readiness](../bench/results/m3/readiness.json) | Both local health probes failed with URLError; zero model calls and zero payments; no 3B fit proof or M3 paid-run authorization |
| MOCK | [Controlled proof](../bench/results/m3/controlled-proof.json) | Two controlled purchases including reference cost; lost-response reservation retained and a second payment refused |
| MEASURED | [Python tests](../bench/results/m3/python-tests.txt), [Node tests](../bench/results/m3/node-tests.txt) | 177 Python and 29 Node tests pass; financial tests use controlled adapters |
| MEASURED | [Redacted secret scan](../bench/results/m3/secret-scan.json) | Zero history findings/sensitive committed paths; five working-tree findings, all in the user's locally edited `.env.example`, which is excluded from this milestone commit |

Twelve of the 24 extracted cases still have PO/payment exceptions and require review. Thus the report's `refusals_or_review` is 168, whereas parser abstentions are 156. Extraction coverage is not permission to pay. CPU, electricity, maintenance and human review are unpriced; internal check fees are SIMULATED. Paid latency, when available, is provider-reported inference latency, not end-to-end settlement time. No model accuracy or cost-saving number is inferred from the tool baseline.

Saved MOCK reference-run audit head: `5a18b16f876e8ed300b2dcad6764cec53dbf901cd28c62dc5390522640d232c9` (14 events). Reproduction changes hashes because IDs/timestamps differ. No runtime Python dependency or Node dependency changed.

**MEASURED hosted CI:** all four Ubuntu/Windows × Python 3.11/3.12 jobs passed on implementation commit `7b4c61687a92683cbf1f7ac64317086403257aea`, including Python tests, pinned Node installation/tests and the full-history heuristic secret scan. The clean checkout excludes the local credential edit. [CI run](https://github.com/kaushikkr-dev092005/touchstone/actions/runs/41609109102) · [saved metadata](../bench/results/m3/ci.json). This is controlled implementation evidence, not a live model/payment result.

## Claims now allowed and not allowed

Allowed: reproducible synthetic corpus, conservative tool baseline, source-citation/integer checks, unchanged statistical gate, blocked-model showcase, and controlled paid-reference/uncertainty accounting.

Not allowed: eligible useful inference, representative OCR/vendor accuracy, independent human labels, a verified partner-credit balance, a hosted API purchase, measured paid latency/savings, live M2 crash recovery, or a new Airwallex write. The corpus uses readable amounts and explicit ITEM boundaries; OCR noise is limited to decorative text. A stronger parser might solve more cases. This baseline does not prove an LLM is necessary. Historical local-model profiles use a different task/checker and cannot qualify this domain.

## Needed from the user

Start the local model for each tier using the [M3 runbook](M3_RUNBOOK.md), then collect calibration and held-out profiles with hardware evidence. Supply hosted credentials through the seller environment and confirm partner-credit funding privately. A new written M3 aggregate USDZ cap and call count are needed before any paid profiling; the existing M2 one-call allowance is not reused. Funding requires its own approval. Keep secrets in ignored local configuration; `.env.example` is a tracked template and its local credential edit is neither loaded by the standard configuration loader nor included in this commit.
## 10 November follow-up: source-span selection, still ineligible

The model now selects IDs from public source substrings; code reconstructs exact
Unicode offsets. This removes invented offsets without supplying expected answers
or assigning semantic roles in the catalog. Unknown selections and abstentions
fail closed. Historical profiles are retained unchanged.

A fresh 180-call local 1.5B study measured 18/120 strict-correct calibration
outputs and 1/60 on the fixed holdout. There were 57/29 verifier-accepted outputs
and 41/28 incorrect acceptances respectively. Exact textual support and arithmetic
do not establish correct field interpretation. The unchanged 95% qualification
screen rejects the model; no invoice payment is authorized from these outputs.

The raw profile is `bench/results/m3/profiles/balanced-source-spans-20261110.json`.
The current dashboard report includes that study and rejects stale historical
profiles. The experiment uses known synthetic layouts, not representative finance
operations or a pristine prospective evaluation. Provider/model identity, raw
selections, hardware samples and source hashes are retained. No hosted call or
external financial transaction was sent; local electricity/CPU costs are unpriced.

Windows checkpoints now use unique temporary files and bounded sharing-violation
retries. Retrying a checkpoint does not repeat the model or payment call.
