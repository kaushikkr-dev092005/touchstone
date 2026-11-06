# M7 — local packaging verification, 6 November 2026

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

## Exact source artifact verified

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
