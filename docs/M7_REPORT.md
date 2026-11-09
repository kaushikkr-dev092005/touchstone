# M7 — local packaging verification, 6 November 2026

## Current follow-up, 10 November 2026

The latest exact source snapshot and all stage results are recorded in
`bench/results/completion-20261110/release-current.json`; earlier reports below
remain historical. Its working-tree manifest includes explicitly named public
added files, excludes private runtime data and binds every source file by hash.

The dashboard now has an authenticated, read-only issuing recheck and a sandbox
settings link. Current-account Cards, Cardholders and Config reads pass after the
operator enabled their Read scopes. Mismatched historical account evidence cannot
claim current access. No card was created; issuing writes and Visa remain unverified.

One separately approved local test spent exactly 0.01 USDZ and was rejected
(1,400 vs 2,000 cents). The receipt, actual cost, output, audit and post-test wallet
read are preserved in the release evidence; no retry, top-up, transfer or hosted
call occurred. This protocol test does not qualify a model. The model was stopped
afterward; final validation uses controlled adapters without GPU inference.

The model launcher refuses startup at 65 C and stops its owned child at 75 C,
reported thermal throttling or lost temperature telemetry. Unit tests exercise
the cutoffs and child-process shutdown with controlled readings, without heating
hardware. A captioned local recording exists; no upload or submission occurred.

## Completion follow-up, 9 November 2026

The 9 November release attempt passed Python/Node and the frontend build, then
failed browser validation because saved planning evidence was stale. The runner
now regenerates bounded-tool evidence in the extracted copy before browser QA.
This does not refresh historical model profiles or qualify an inference provider.

The dashboard now respects `--data-dir` for banked and real-policy history. Its
transaction explorer separates quoted/reserved amounts from confirmed charges;
void attempts are labelled as uncharged. CSV exports include both amounts and
neutralize formula-leading text. Browser QA covers filters, pagination, keyboard
drawer access and exported totals across two simulated runs.

An explicit `--working-tree` packaging/validation mode verifies tracked edits
without creating a commit. Its manifest binds the base revision and every file
hash, labels changed paths, and excludes untracked files and private data.
The committed-tree default remains available. See the
[validation runbook](VALIDATION_RUNBOOK.md) for the reproduction command.

The fresh run is recorded at
`bench/results/completion-20261109/release.json`. Consult its `passed`, `stages`,
`source_mode`, base `commit` and `archive_sha256` fields for the precise result;
the older artifacts below remain historical. This local work performs no live
financial transaction, hosted inference, publication or submission.

## Changes

README leads with the pitch and three saved proofs. The demo script and submission
draft now distinguish completed sandbox FX/capture and one-call Metal recovery
from the blocked larger studies. The evidence index includes all four extensions
and the M5 billing comparison. `tools/run_mock.py` starts a credential-isolated
offline demo on Windows, macOS and Linux with Python 3.11+ only.

`tools/bundle.py` packages an explicit committed Git tree, scans its contents and
configured secret values, rejects private/generated paths, and records file hashes.
Concurrent user frontend/configuration edits are preserved and excluded. The one
public `current-wallet-preflight.json` is a readiness report, not a key store; it
receives the full content scan. Private wallet files remain excluded.

## Current source artifact (rebuilt 6 November 2026, supersedes the one below)

- Commit: `cb5bce811b5fe4f2ad7f99e92ff7fd450800f11a` (includes the dashboard/landing redesigns and the live-mode,
  fault-receipt, FX-execution, calibration and banking-adapter work).
- Local archive: `dist/touchstone-source.zip`; 372 files, 18,258,711 bytes.
- SHA-256: `c50c7195cd7fab1bda2595a09d7a9f2f9286769edab9e90dca8d3f02b5f2f13d`.
- [Rebuild evidence](../bench/results/package/head-rebuild.json); manifest in `dist/bundle-manifest.json`.
- Secret-shape and configured-environment scans passed; no private runtime data or working-tree edits included.
- Every extracted file matched its Git blob at that commit (0 mismatches).
- In the extracted copy: **274 Python tests** and **53 Node tests**, zero failures.

**Caveats:** `node_modules` was copied from the working tree rather than installed with `npm ci`; `.tools` was
symlinked; browser QA ran against the working tree before the commit, not the extracted copy. This is weaker than the
earlier pinned-install run. Nothing was uploaded, published or submitted, and no financial transaction or hosted
inference call was sent. The environment notes and exclusions below still apply, except that the new features were
exercised only with controlled adapters.

## Previous source artifact (superseded; kept for the record)

- Commit: `b82b977b9bbab399c08c20e1cc424ffd862a8711`.
- Local archive: `dist/touchstone-source.zip`; 323 files, 18,095,749 bytes.
- SHA-256: `e34d4886a7b0804ac596be34673cff2b7f7ab911cbbebd19afeb7bab6ec922ea`.
- Manifest: `dist/bundle-manifest.json`, including individual source hashes.
- [Clean-checkout evidence](../bench/results/package/clean-checkout.json).

The report commit is separate from the source revision under test. The archive
remains tied to the exact revision above; it is not rebuilt silently from a dirty
working tree. Source bytes were checked against the manifest after extraction.

## Measured verification

- Pinned `npm ci --ignore-scripts` succeeded in the extracted directory.
- **247 Python tests**, **47 Node tests**, zero failures.
- Desktop and 390px browser checks passed, with no page errors or overflow.
- Both billing policies, reconciliation, kill/resume and session/Host/Origin checks
  passed. Missing FX credentials yield BLOCKED, not simulated success.
- The actual one-command mock launcher passed at 1440×900 and 390×844 with reduced
  motion enabled/disabled and zero external requests. An isolated mock-server
  restart triggered SSE reconnect and restored the stream.
  [Mock smoke result](../bench/results/package/mock-smoke.json).
- No private configuration/model/wallet data was copied into the clean directory.
  No financial transaction or hosted inference call was sent by validation.
- No new Python runtime or Node dependency was added by these extensions.

The optional concurrent React landing page was type-checked and built locally
after correcting misleading payment copy, without restyling it. Its source and
static-serving changes remain the user's uncommitted work and are outside this
source archive. The default dashboard, model and local seller are running; their
health is not evidence of payment, qualification or final settlement.

## Allowed claims, remaining gates

Allowed: reproducible mock demo, clean-source tests, saved measured sandbox/testnet
proofs and explicitly bounded extension implementations. No critical failure was
observed in this validation scope. Windows was executed locally; Ubuntu/macOS
support is provided by portable code/CI configuration, not a new local OS run.

Excluded: current remote CI success, production readiness, new paid tests, eligible
invoice models, a live M4 comparison, refunds, fiat-token funding, issuing access,
Visa approval, calibrated GPU pricing or independent final settlement.

Human/external gates: hosted credentials/credits and model qualification; new caps
before further live operations; issuing access and genuine Visa trust if pursued;
throughput/pricing calibration; accepted registration, portal schema/deadline,
sponsor tooling eligibility, video recording, submission and receipt confirmation.
Feature freeze remains scheduled for 11 November. Nothing was pushed, uploaded,
recorded or submitted by this packaging step.
