# Release validation and live gates

## Reproduce validation without spending

From the repository root, PowerShell, macOS and Linux use the same command:

```text
python tools/validate_release.py --browser --frontend --output bench/results/validation/release.json
```

The runner bundles an exact committed revision, verifies every extracted file against
the source manifest, installs the Metal npm lockfile with scripts disabled, and runs
the Python/Node suites and M1–M5 controlled proofs. It never copies `data/`, keys,
`node_modules` or `.tools` into the extracted source. Node must already be installed;
the existing portable Node installation is supported through PATH.

`--browser` needs the existing Playwright/Chromium development installation. It checks
the simulated demo, both billing policies, Host/Origin/session controls, kill/resume,
reconciliation, reduced motion, desktop/mobile layouts, offline assets and SSE restart.
A prior-process session token must fail after restart; a refreshed page gets a new one.

`--frontend` needs Bun and installs `apps/web/bun.lock` with `--frozen-lockfile` before
type checking and building the optional `/site/` page. It adds that page to the
browser checks. Package downloads are external network requests; no inference,
card, FX or token transaction is executed. Logs and screenshots stay under `tmp/`.
The report records their hashes and the exact source commit.

## Read-only provider and qualification checks

```text
python tools/validation_status.py --rpc --output bench/results/validation/readiness.json
```

This reads local health endpoints, configuration-presence booleans, saved profiles
and (with `--rpc`) chain metadata. It prints no credential values and buys nothing.
Health and a partner-credit declaration cannot prove working hosted credentials or
available credits. Missing health, a wrong identity/chain or stale qualification
remains BLOCKED. Historical outputs can be rescored without becoming new model calls.

The operator starts llama.cpp/providers and enters credentials privately. All live
money actions still require fresh written chat approval with explicit caps and the
relevant execute flag. CLI flags, a service-health result and an old approval are
not new authorization.

## Gates this validation cannot close

| Gate | Required evidence |
| --- | --- |
| Useful inference | Full current calibration/holdout profiles passing the unchanged eligibility screen; no truth in model requests |
| Concurrent Metal jobs | Separately approved funding and paid run with distinct job wallets, linked reservations/receipts and reconciliation |
| M4 live comparison | Current immutable plan, matching seller schedule, funded dedicated scope, approval covering aggregate/call/upstream limits, 30–50 actual purchases and measured fault injection |
| Optional card/FX execution | Enabled issuing and an independently verified funded merchant, then a separately approved sandbox operation |
| Genuine Visa trust | External credentials/onboarding and verified interoperability; local signatures are insufficient |
| Submission | Operator portal checks, video, submission and receipt confirmation |

M2's historical single-call payment/recovery and M1's settled FX/capture remain
separate saved proofs. Controlled fixtures cannot pass their larger live gates.
No fiat-to-token bridge or settled refund is claimed.
