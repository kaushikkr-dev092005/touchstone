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

To verify current tracked edits before committing, add `--working-tree`:

```text
python tools/validate_release.py --working-tree --browser --frontend --output bench/results/completion-20261109/release.json
```

This mode records `TRACKED_WORKING_TREE`, the base commit, changed paths and exact
file hashes. It excludes untracked files and creates no commit. The default remains
an exact committed tree. The browser stage first regenerates bounded-tool evidence
inside the extracted copy; stale historical model profiles remain ineligible.
The transaction explorer checks confirmed charges, search, outcome/run filters,
sorting, pagination, keyboard access to the receipt drawer and CSV totals.

New public files can be included explicitly with repeated `--include relative/path`
arguments in working-tree mode. Every added file receives the same path, secret and
hash checks. Unlisted untracked files remain excluded.

## Current proposed paid-test limits, 10 November

The operator proposed 1.00 USDZ aggregate and 0.01 USDZ per inference call, with
$0 hosted spending, no hosted credit usage until its availability and permitted
use are verified, and no top-ups/transfers. **These limits are not final approval.**
All zero-cost checks and estimated test costs must be reported before requesting
the final approval for any paid operation.

```text
python tools/validation_status.py --rpc --paid-preflight-wallet m2-live-single-20261105-j1 --output bench/results/completion-20261110/paid-preflight.json
python tools/capped_probe.py --wallet m2-live-single-20261105-j1
```

Both commands above send no payment. The second prints the exact, scope-bound
approval phrase and reports FINAL_APPROVAL_REQUIRED. Its execution path requires
both `--execute` and the exact approved phrase; the operator's separate final
approval must exist before using them. It permits one local arithmetic protocol
probe from existing clearing funds, uses a durable ledger, logs actual cost,
receipt ID and verification, and never deposits, transfers, uses hosted credits
or automatically repeats an uncertain call. Receipt IDs are not on-chain
transaction hashes; preconfirmation is not final settlement.

Repeated completed scopes return their stored report. Unresolved reservations
remain locked for separate recovery. An aggregate owner and conservative exposure
check enforce the proposed 1.00 USDZ ceiling across this probe runner's scopes.

The 10 November read-only observation found 0.01 USDZ in the selected clearing
wallet, sufficient for one quoted 0.01 USDZ call. The separate funding account is
not authorized to transfer. A 30–50-call comparison cannot run from that wallet
under the no-transfer restriction. Hosted credits remain unverified and unused.

The frontend type-check starts from `src/main.tsx` and its imported modules. Legacy
scenes that the application does not import are preserved in the source archive;
their missing experimental assets cannot break the shipped application build.

## Private hosted setup

```text
python tools/configure_hosted.py
```

Enter the key in the masked desktop field, an accessible Claude model ID and an
optional workspace ID. Confirm the partner-credit declaration locally. Verification
uses only `GET /v1/models/{model_id}`; it does not request inference. Configuration
is saved atomically under the ignored local settings path. The optional startup
checkbox lets the operator start the local model and sellers without purchasing.
An account-wide key needs the appropriate workspace; a workspace-scoped key may
omit it. The Messages adapter forwards the optional workspace header.

Contract references: [model metadata](https://platform.claude.com/docs/en/api/http/beta/models/retrieve),
[authentication and workspace selection](https://platform.claude.com/docs/en/manage-claude/authentication).
Verified metadata is not model qualification, credit-balance verification or spend approval.

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
