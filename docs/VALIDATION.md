# Validation record

Updated 2 November 2026. Environment: Windows, Python 3.12.10, portable Node 22.23.4, NVIDIA RTX 3050 Laptop GPU with 4096 MiB VRAM, driver 610.62. Any measured GPU profiles are stored separately from simulator results.

## Automated financial controls

`python -m unittest discover -s tests -v`

127 Python tests were collected on 2 November 2026 (before the M0 test additions); 124 passed, 2 failed because the saved local profiles are bound to older verifier/provider hashes (the stale-evidence guard is working; regeneration needs the local model), and one test that compared wall-clock quote expiry was flaky and has been fixed. The suite covers accounting, concurrency, process-death recovery, source evidence, planning, invoice checks, wallet FX journaling/reconciliation, Metal engine routing, hosted checkout/banked-job cases, versioned simulated mandate approval, and no-payment quote/unavailable-provider handling. No remote paid operations are part of the suite.

Sandbox workflow tests exercise lost create and capture responses, repeated execution without a second write, immutable scope/amounts, pending review refusal, monetary precision, and exclusion of card fields/client secrets from persisted response data. A read-only smoke check can verify Checkout Sessions read access but never verifies write access. The remote API is replaced with controlled fixtures in these tests; no actual hosted checkout or sandbox authorization is claimed.

`python tools/metal.py test`: 21 Node tests pass (2 November). They cover SDK store ownership, quote units/caps and sample-count metadata, exact pending-invoice replay, authoritative unpaid refusals, refusal to change seller/URL, uncertain payment retention, original paid delivery replay, durable provider output, task-digest binding, queue-aware quote persistence/pricing, quality-drop injection and funding-key preservation.

`python tools/metal.py inspect` succeeded against the public testnet facilitator and sent zero payments. Evidence is saved in `bench/results/metal-discovery.json`. SDK 0.3.3 and viem 2.57.13 are locked; npm reported zero known vulnerabilities on installation. A local preparation wallet was initialized under ignored data/metal/; no private key was printed or funded.

`python -m touchstone engine-metal --quote-only` was exercised against the loopback Qwen2.5 0.5B Vulkan seller and Metal testnet deployment. It returned a $0.01 quote at queue depth zero and sent zero payments. The provider reported zero completed-delivery latency samples, so the displayed 1,000 ms remains a fallback estimate. It did not create a ledger run or execute inference; see `bench/results/metal-provider-quote.json`.

The recovery test starts a subprocess, commits one receipt to the independent mock rail, then terminates via the engine's `kill_at='after_rail'` path (exit 86) before recording local payment. The parent reopens the stores, recovers the original receipt, repeats recovery without another effect and finishes the run. Additional tests cover interruption after reservation and after local payment commit. These simulated process-kill tests are distinct from a real Metal kill/restart, which has not been run.

## Benchmark

`python -m touchstone benchmark`

The saved `bench/results/simulated.json` and RESULTS.md record three policies over five paired seeds with 200 tasks per seed. Results are entirely simulated and include verification charges. The raw file includes each run, policy-control gates, and a separate seeded invoice fault-injection study. Dashboard copy labels the comparison as simulated; the first evidence card instead leads with the single recorded live paid call and its rejected answer.

All five gates passed: no budget breaches, no price-cap breaches, no duplicate mock payment keys, matching mock rail receipts, and complete workloads under every policy.

| Policy | Median total cost USD | Median true success |
|---|---:|---:|
| Always premium | 10.200 | 99.5% |
| Always cheapest | 2.200 | 80.5% |
| Touchstone, source-rules-v3 | 6.162 | 100.0% |

The original membership-only Touchstone result (86.0%, $5.833) remains under baseline-v1/. Current results no longer report the tautological calibration MAE. A noisy checker, injected with two offsetting one-cent errors across 20 ten-line invoices and 100 repeat seeds per case, false-accepts 79.0%, 62.0%, 46.5%, and 20.9% when sampling 1, 2, 3, and 5 rows. The exact source-citation arithmetic checker false-accepts 0/20 on that injected set. These are synthetic fault-injection rates, not population estimates. The 100% policy result is measured on supported synthetic templates, not arbitrary semantic text or real model calls, and does not establish real-world quality parity or GPU cost savings.

## Browser validation

Desktop and phone-width end-to-end checks are recorded by `tools/check_dashboard.py` using an isolated local test server. The script checks page errors, start/halt/resume/partial closure, Host/session-token refusal, layout overflow and mode labels, and saves screenshots under ignored `tmp/browser/`.

Passed at 1440 px desktop and 390 px phone width: no browser script errors, no page-level horizontal overflow, start/halt/resume/partial-capture flow successful, Host/Origin/session-token controls refused invalid requests. Provider payments plus checking charges matched simulated customer captures, with no unresolved attempts or authorization overrun. The UI displays verifier version, integration readiness and measured local-model summaries.

## Measured local inference

Official llama.cpp b12000 Vulkan and publisher-hosted Qwen2.5 Q4_K_M model files were downloaded with SHA-256 verification. Both model repositories declare Apache-2.0; publisher revisions and model hashes are retained in the raw profiles. The profiler explicitly selects `Vulkan1: NVIDIA GeForce RTX 3050 Laptop GPU` and disables multi-device splitting. NVIDIA VRAM allocation was observed during each run; exact offloaded layer counts were not exposed by the logs and are not invented.

Each model was evaluated on 30 tasks for each of seeds 41, 42 and 43, with one excluded warm-up, temperature 0 and schema-constrained JSON output. GPU memory remained well below the 80% allocation ceiling.

| Model tier | Calls | Strict true correctness | Median latency ms | p95 ms | Peak observed NVIDIA VRAM MiB |
|---|---:|---:|---:|---:|---:|
| Qwen2.5 0.5B Q4_K_M | 90 | 22.2% | 230.0 | 620 | 454 |
| Qwen2.5 1.5B Q4_K_M | 90 | 48.9% | 183.0 | 410 | 1074 |

The initial unconstrained-output run is retained under `unconstrained-baseline/`. It is diagnostic only: formatting differed and device selection was automatic, so it is not used in the paired comparison.

`tools/replay_profiles.py` applies identical online checks to both measured output sets. It never uses private truth to choose a provider. At assumed per-call prices of USD 0.01 and 0.02 plus USD 0.001 checking charges, cheap-first escalation costs USD 2.460 for 45 correct outcomes, versus USD 1.890 for 44 with balanced-only. This experiment rejects a blanket claim that escalation saves money. Latencies are sums of recorded calls, not a newly measured concurrent paid service. These tasks admit deterministic solutions, so no production business-value claim follows.

## Local planning and provider evidence

`python -m touchstone procurement-evidence` and `python -m touchstone plan` both completed with zero payments. Bounded tools produced the independently generated expected answer on 1,000/1,000 tasks across seeds 101–105. The authored boundary suite met 24/24 expectations: six local resolutions and eighteen explicit review decisions. Review is not completion; these results do not establish performance on arbitrary banking documents.

All six provider/task combinations fail the offline screen. Calibration uses seeds 41–42; evaluation uses 43 and cannot affect calibration counts. This split is retrospective because the original profiles were previously inspected. Classification has only three unique sources and no unseen source in evaluation. Raw profiles remain unchanged. Reports bind code, cases and profile hashes and are marked stale if those inputs change.

See `bench/results/PROCUREMENT_RESULTS.md`, `procurement-evidence.json` and `docs/PROCUREMENT_POLICY.md`. The interactive dashboard shows six eligibility rows and switches between a local calculation and a foreign-currency review case; browser QA checks both outcomes.

## Real integrations executed

The user funded the locally generated testnet wallet through the console. Chain 63825 was verified, 0.10 testnet USDZ deposited and one 0.01 USDZ inference call purchased through the SDK. The provider verified a real signed receipt. Both buyer-cache replay and direct provider receipt replay returned identical original delivery without another payment. The real model output was 1250 cents rather than the correct 2000, and the verifier rejected it. The charge remains recorded. Receipt assurance is preconfirmed. The remaining 0.09 testnet USDZ was returned in a non-deferred claim after withdrawal epoch 93301 finalized. Queue and claim transactions are recorded in `metal-paid-proof.json`; the payment receipt itself remains preconfirmed. See LIVE_PROOF.md.

Airwallex smoke rerun on 1 November confirms authentication, balance reads and Global Account reads; `account_context_configured=false` because `AIRWALLEX_ACCOUNT_ID` is unset. Checkout Sessions and FX conversion reads could not be tested; no writes were performed. PaymentIntent creation still returns HTTP 400 `configuration_error` from merchant configuration. No customer authorization/capture or treasury FX conversion has completed. The failure is retained in `airwallex-hold-proof.json`; unknown operation scopes are preserved privately.

## Not executed

Actual hosted Checkout Session or sandbox hold/capture; a Treasury FX quote/conversion; 30–50 paid engine steps; paid quality-drop chaos and a real Metal kill/restart; three concurrent external customer holds; finality for the paid inference receipt; representative finance-document evaluation and qualified autonomous model procurement; production security assessment; hackathon submission. A zero-payment provider-outage preflight is recorded separately. The repository is public. The real x402 round trip above uses test assets and is separate from the multi-job simulator.
