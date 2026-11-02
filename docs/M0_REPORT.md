# M0 — truth and hygiene, 2 November 2026

Status: local checks **MEASURED / PASS**; hosted CI **BLOCKED / pending corrected commit run**. No money-moving action was executed. The scope of this work ends at M0.

## What changed

- Reconciled README status labels: simulated mandate approval exists; a real Airwallex hold increase does not. Unrun work is marked BLOCKED with its cause. Fiat and testnet token accounts stay separate.
- Retained the public-repository submission status and verified GitHub reports PUBLIC. ROADMAP separates Done from Not done and records the current M0–M7 order and human gates.
- Kept Bash equivalents beside PowerShell examples; documented isolated verification in VALIDATION.md.
- Repaired two CI evidence tests with temporary MOCK profile fixtures. Saved model outputs and hashes remain unchanged; stale historical measurements still cannot authorize purchases. Added changed-code provenance rejection coverage.
- Isolated verification from private local configuration using `TOUCHSTONE_IGNORE_LOCAL_CONFIG=1`. The Node test/install launcher does not load local credentials. Added a test proving the isolation setting does not inspect private paths.
- Updated the redacted history scanner to include lockfiles, report exclusions and shallow history, and refuse to read private data/wallet/config contents. Sensitive committed paths fail the scan without exposing values. Added controlled tests for those boundaries.
- Retained the Ubuntu/Windows × Python 3.11/3.12 CI matrix, locked Node dependencies and independent Node/scan steps after a Python failure. CI now explicitly ignores local config. No dependencies changed.

## Saved evidence and results

| Label | Check | Result | Evidence |
|---|---|---|---|
| MEASURED | Local Python 3.12.10 on Windows | 133 passed; no failures | [Python log](../bench/results/m0/python-tests.txt) |
| MEASURED | Local Node 22.23.4 | 21 passed; no failures | [Node log](../bench/results/m0/node-tests.txt) |
| MEASURED | History and working-tree heuristic scan before evidence packaging | 349 text blobs/files; no findings or sensitive committed paths; non-shallow history; zero reported exclusions | [Redacted scan](../bench/results/m0/secret-scan.json) |
| MEASURED | Previous hosted CI diagnosis | Two evidence tests failed on stale profile hashes; Node and scan passed | [Previous CI run](https://github.com/kaushikkr-dev092005/touchstone/actions/runs/41481693908) |
| BLOCKED | Hosted CI for the corrected commit | Pending | Run URL will be recorded after completion |

The scan covers text reachable from all locally available Git refs and non-ignored working files, with a 2,000,000-byte limit and documented heuristic patterns. Private `data/`, wallet/config contents, ignored files and dependency directories are excluded by policy; sensitive paths in history are checked separately. It is not proof that arbitrary secrets cannot exist. The saved count predates this report and its logs; subsequent CI scans include them. Raw local test output is evidence of code execution against MOCK adapters and SIMULATED workloads, not a new live financial proof.

## Claims now allowed

- MEASURED: local offline suites pass, repository visibility is PUBLIC, and the redacted heuristic scan found no matches within its stated scope.
- MOCK: adapter recovery and financial-control behavior covered by tests.
- SIMULATED: versioned human mandate approval and the three-job short-float scenario.
- Historical MEASURED claims remain bounded by LIVE_PROOF.md: one paid-and-rejected Metal call with receipt replay and Airwallex authentication/reads.

## Claims not allowed

No new Airwallex write, real hold increase, live paid engine/restart run, qualified inference model, live policy comparison, fiat-to-token bridge, refreshed GPU profile, or hackathon submission. Hosted CI is not green until the corrected run passes. Legacy financial commands that lack an execute-style guard remain unavailable under the current rules; M1/M2 must close those command gaps before execution.

## Human gates — pending, no approval inferred

1. Confirm accepted registration, personal deadline and submission schema in the signed-in portal, including the video duration limit.
2. Set `AIRWALLEX_ACCOUNT_ID` privately and save the required sandbox scopes. The chat screenshot shows recommended Conversion Write and Balances Read selections; it is not saved-key or API authorization evidence. No current account configuration was read in M0.
3. Ask Airwallex support about the PaymentIntent `configuration_error`, hosted checkout enablement, and whether Developer MCP/CLI satisfies the tooling requirement. M1 will prepare the support request; no message has been sent.
4. Fund the Metal wallet via the faucet, start the local provider and llama.cpp, and supply hosted credentials through environment variables when those milestones are reached.
5. Approve each money-moving workflow in chat with its currency, amount and aggregate cap. An execute-style flag is also required; no spend approval exists in this task.
6. Record the video, submit early and confirm the submission receipt manually.

Freeze: 11 November. Working submission deadline: 13 November 2026, 18:29 UTC (23:59 IST), subject to the human portal confirmation above.
