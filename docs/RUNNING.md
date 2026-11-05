# Running the local project — 5 November 2026

## Start

With the already-installed models and Node adapter, run from the repository root.
The same command works in PowerShell and Bash:

```text
python tools/run_project.py
```

This starts the dashboard on 8088, the balanced llama.cpp model on 8080 with an
8192-token context, and the existing local-GPU seller on 8092. It preserves healthy
existing services, refuses occupied ports belonging to a different service, and
does not generate a wallet, deposit, purchase, withdraw, convert money or call a
hosted inference API. Seller health is configuration evidence, not payment proof.
The dashboard's three-job demo remains **SIMULATED**.

On Windows, the launcher reads configured user environment variables, then uses
the normal local configuration loader. It never loads `.env.example`. Bank secrets
and the funding key are removed from seller/model environments; the local model
also receives no RPC credential. A hosted seller starts only when its credentials
and existing seller wallet are present. Hosted entitlement and credits are not
established by a health response.

Status only, with no service starts:

```text
python tools/run_project.py --status --no-browser
```

An already-running service retains its original environment. Restart that service
after a credential change; the launcher does not terminate a working process.
No Python runtime dependencies or Node dependency changes were added.

## Verified repairs

- **MEASURED:** the existing scoped Airwallex key authenticates and reads balances,
  Global Accounts and FX conversions. Smoke queries now use supported page sizes
  and reuse one login token. Account validators accept internal underscores and
  hyphens, while rejecting header injection.
- **MEASURED:** exactly one authorized sandbox conversion sold **1.00 USD** for
  **0.89 EUR**, settled, and matched the real sell/buy wallet-history entries.
  The observed USD cash debit was exactly **1.00**. No conversion was retried.
  The earlier one-conversion authorization is consumed.
  [Financial evidence](../bench/results/m1/live-fx-single-conversion.json).
- **MEASURED:** the same FX record is linked to a treasury job. Airwallex ledger
  entries are measured; the separate `METAL_DEMO_FLOAT` entry is **SIMULATED**
  accounting and cannot fund a real wallet. [Job proof](../bench/results/m1/live-treasury-job.json).
  Audit head: `1855dc7889c605a2a406bb6cfa2df5a54ec544f7317869178ddbf86cae873e6c`.
- The sandbox request-ID history lookup returned 404 after settlement. The adapter
  now explicitly records that limitation, scans bounded GET-only history pages,
  and accepts only exact conversion-source matches. Authentication failures do not
  trigger that scan; incomplete pagination refuses reconciliation.
- **MEASURED:** one hosted 1.00 USD authorization and 0.01 USD final capture completed.
  The unused 0.99 was not captured; issuer release timing is unmeasured.
  [Card proof](../bench/results/m1/current-hosted-card-proof.json).
- **MEASURED:** one approved 0.02 USDZ deposit and one 0.01 USDZ engine purchase,
  followed by hard process death and recovery twice without a new payment.
  Actual native funding fees: 451,768 wei, below the 10^15 wei cap.
  The answer failed verification; the receipt is preconfirmed, not final settlement.
  [Final proof and audit](../bench/results/m2/live-single-call-final.json).
- **MEASURED on SIMULATED sources:** both installed models measured on 180 sources
  each; both failed the unchanged qualification gate. No useful-inference claim.
  [M3 report](M3_REPORT.md).
- Stale historical model profiles no longer disable the independent deterministic
  planning panel. Current tool measurements are regenerated; stale profiles remain
  explicitly **BLOCKED** and cannot qualify a purchase. Historical raw outputs are
  preserved. Saved Airwallex observations are bound to the selected account, and
  an unbound historical merchant error is not asserted against a different account.

## Remaining external gates

| Gate | Current evidence | Required operator action |
|---|---|---|
| Native acquiring / production | **MEASURED:** the separate hosted sandbox authorization/capture is complete. Native API enablement and production are unverified. | Support must confirm native entitlement only if needed; the successful hosted path can be used independently. |
| Further Metal operations | **MEASURED:** single-call/recovery gates passed. The deposit and purchase approvals are consumed; 0.01 USDZ remains in the job wallet. | Obtain fresh written caps before any new purchase, deposit or withdrawal. No new operation is needed for this proof. |
| Hosted premium tier | **BLOCKED:** no hosted API credential is configured. | Supply credentials privately in the seller environment and identify the intended model/credit source. Hosted API usage needs its own authorization. |
| M3/M4 paid studies | **BLOCKED:** the single-purchase allowance does not cover these experiments. | Qualify a model using actual measurements; approve the study's aggregate cap/call count and upstream usage. No eligibility threshold is reduced. |

Repair RPC credentials locally without exposing the URL:

```text
python tools/configure_metal_rpc.py
```

The masked form checks the fixed testnet host and chain before saving. It never
generates a wallet or sends a transaction. Airwallex uses the equivalent existing
`python tools/configure_airwallex.py` masked setup window.

Account access references: [API key scopes](https://www.airwallex.com/docs/developer-tools/api/api-key-scopes),
[sandbox checkout settings](https://www.airwallex.com/docs/developer-tools/sandbox-environment/sandbox-settings).
The [support request](AIRWALLEX_SUPPORT_REQUEST.md) is a draft, not a sent email.

The optional native-fee guard applies to the approved deposit through `tools/fund_metal_probe.py`; it does not claim to retrofit a fee cap onto every legacy deposit command. That fixed-scope script records a consumed approval and must not be rerun as a fresh authorization.
