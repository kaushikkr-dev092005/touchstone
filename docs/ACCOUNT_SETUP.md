# Account setup and integrated test runbook

Updated 1 November 2026. The user has created both accounts, configured local credentials and funded a dedicated testnet wallet. RPC, Airwallex authentication/account reads, and one actual paid Metal inference call are verified. `AIRWALLEX_ACCOUNT_ID` is currently unset, so account-scoped Checkout Sessions and Treasury FX have not been tested. Airwallex merchant configuration currently blocks PaymentIntent creation. See [live evidence](LIVE_PROOF.md).

## Local configuration

The CLI reads ignored `data/local-config.json` and optional `data/metal/funding-wallet.json`. Environment variables take precedence. `.env.example` documents names but is not auto-loaded. Restart long-running processes after changing credential values. Never put credentials in tracked files.

```powershell
python -m touchstone doctor
python -m touchstone rpc-smoke
python -m touchstone metal-funding
python -m touchstone airwallex-smoke
```

macOS / Linux / Git Bash equivalent:

```bash
python -m touchstone doctor
python -m touchstone rpc-smoke
python -m touchstone metal-funding
python -m touchstone airwallex-smoke
```

These checks do not send a financial transaction. Doctor reports configuration presence and saved observations, not secret values. RPC must identify chain 63825. `metal-funding` reads gas and USDZ balances of the dedicated public address.

## Airwallex permissions and merchant setup

For a new checkout, create a sandbox account at https://www.sandbox.airwallex.com/signup. In Developer > API keys, configure account-level **Payment Acceptance: Write** and **Global Accounts: Read** or **Balances: Read**. Hosted checkout also needs Checkout Sessions read/write access and an activated sandbox payment method. Set `AIRWALLEX_ACCOUNT_ID` to the payment account shown in Settings > Account details; it is required for Checkout Sessions and is also sent as `x-login-as` during authentication.

The current account passes login, balance and Global Account reads, but direct PaymentIntent creation returns HTTP 400 `configuration_error` before card confirmation. The exact missing setting is not established. `airwallex-checkout` now provides a browser-assisted Hosted Payment Page path using the Checkout Sessions API (beta, API version `2026-05-29`) with `auto_capture: false`; it still requires Payment Acceptance activation, Checkout Sessions read/write access, and the payment account ID. If those are not available in the portal, ask Airwallex Support to confirm Payments activation and supported checkout mode. No hosted session has been created yet.

For the hosted flow, use a fresh scope (do not reuse `banked-proof-001`, whose direct create outcome remains unresolved). The start command creates an unpaid Checkout Session and prints its hosted URL; complete payment only with a sandbox test card in the Airwallex page, then retrieve the session status:

```powershell
python -m touchstone airwallex-checkout --scope hpp-smoke-001 --hold-usd 1.00
python -m touchstone airwallex-checkout --scope hpp-smoke-001 --hold-usd 1.00 --status
```

macOS / Linux / Git Bash equivalent:

```bash
python -m touchstone airwallex-checkout --scope hpp-smoke-001 --hold-usd 1.00
python -m touchstone airwallex-checkout --scope hpp-smoke-001 --hold-usd 1.00 --status
```

The second command must report `authorization_ready: true` and an intent in `REQUIRES_CAPTURE` before a job may dispatch. To test a standalone partial capture and remainder cancellation, pass the same scope to the existing command:

```powershell
python -m touchstone airwallex-hold --scope hpp-smoke-001 --hold-usd 1.00 --capture-usd 0.50
python -m touchstone airwallex-hold --scope hpp-smoke-001 --hold-usd 1.00 --capture-usd 0.50 --recover
```

macOS / Linux / Git Bash equivalent:

```bash
python -m touchstone airwallex-hold --scope hpp-smoke-001 --hold-usd 1.00 --capture-usd 0.50
python -m touchstone airwallex-hold --scope hpp-smoke-001 --hold-usd 1.00 --capture-usd 0.50 --recover
```

For the integrated banked flow, pass `--journal data/banked/airwallex.sqlite` to both `airwallex-checkout` commands, then use the same scope with `banked-job --integration-probe`; this deliberately proceeds to a testnet provider purchase and should only be run when that separate expense is intended. The fixed sandbox workflow is limited to USD 10 holds and whole cents. It persists UUIDs before writes, captures once and cancels remaining capture-ready authorization. Customer-action states are completed only by the customer on Airwallex's hosted page. Unused authorization does not prove issuer balance availability.

Recovery reads existing intents. For unresolved create only, it may replay the identical body using the original UUID under documented Airwallex idempotency. It never silently invents another create UUID. Unknown capture/cancel outcomes remain read-reconciled. A cached `duplicate_request` from a rejected create is not authorization; preserve that scope for inspection.

## Treasury wallet and FX

Set `AIRWALLEX_ACCOUNT_ID` from the sandbox payment account and verify read access with `python -m touchstone airwallex-smoke`. The key needs **Core Resources > Balances > Read** for wallet balances/history and **Transactional FX > Conversion > Read** for conversion/quote reads. **Transactional FX > Conversion > Write** covers both `POST /api/v1/fx/quotes/create` and `POST /api/v1/fx/conversions/create`; do not infer write permission from a successful read. Check current [API key scopes](https://www.airwallex.com/docs/developer-tools/api/api-key-scopes), [conversion API](https://www.airwallex.com/docs/api/transactional_fx/conversion), [quote API](https://www.airwallex.com/docs/api/transactional_fx/quotes), and [balances API](https://www.airwallex.com/docs/api/core_resources/balances/current) before enabling writes.

```powershell
python -m touchstone airwallex-fx balances
python -m touchstone airwallex-fx quote --sell-currency USD --buy-currency EUR --sell-amount 10.00
python -m touchstone airwallex-fx convert --request-id fx-demo-unique-001
python -m touchstone airwallex-fx convert --request-id fx-demo-unique-001 --execute
python -m touchstone airwallex-fx report --request-id fx-demo-unique-001
```

macOS / Linux / Git Bash equivalent:

```bash
python -m touchstone airwallex-fx balances
python -m touchstone airwallex-fx quote --sell-currency USD --buy-currency EUR --sell-amount 10.00
python -m touchstone airwallex-fx convert --request-id fx-demo-unique-001
python -m touchstone airwallex-fx convert --request-id fx-demo-unique-001 --execute
python -m touchstone airwallex-fx report --request-id fx-demo-unique-001
```

Quote is a non-settling preview saved locally. Conversion is a separate sandbox wallet write and requires a unique request ID (Airwallex rejects duplicates; use the same ID for read-based recovery, never mint a replacement to retry uncertainty). The local journal binds that ID to exact quote terms before posting. A report shows wallet balances and reconciles a settled conversion with its sell/buy balance-history entries. Keep this isolated from Metal funding; no fiat/token bridge is implemented. No Airwallex quote or conversion has been created yet.

## Metal wallet and runtime

For a fresh checkout, prepare portable Node and dependencies:

```powershell
python tools/setup_node.py
python tools/metal.py install
python tools/metal.py test
python tools/metal.py inspect
python tools/metal.py wallet
```

macOS / Linux / Git Bash equivalent:

```bash
python tools/setup_node.py
python tools/metal.py install
python tools/metal.py test
python tools/metal.py inspect
python tools/metal.py wallet
```

`wallet` generates or reads a dedicated local funding key and prints only its public address. It never overwrites an existing wallet. Use the console faucet at https://console-testnet.metalntwx.com to fund that address with test USDZ. Configure the full RPC URL, not a token with an added `0x`. Use only a dedicated testnet wallet.

The SDK uses a distinct persisted clearing wallet per job under ignored `data/metal/`. It verifies network, asset, deployment, seller and caps. Exact-payment fallback is disabled. Unknown payments retain their original invoice and URL; do not erase wallet state or create replacement purchases.

## Local paid provider

The installed runtime and model can be started in one terminal, then the seller in another:

```powershell
python tools/run_local.py --tier balanced
# Another terminal:
python tools/metal.py provider
```

macOS / Linux / Git Bash equivalent:

```bash
python tools/run_local.py --tier balanced
# Another terminal:
python tools/metal.py provider
```

The model uses NVIDIA Vulkan on loopback port 8080. The x402 seller binds loopback port 8092, binds the public task digest to its resource URL, and verifies real signed receipts against chain and service state. A delivery journal returns the original stored result when that paid proof is replayed. The provider receives no Airwallex credentials or EVM funding key; the model worker receives no RPC credential. In hosted mode, only that worker receives `ANTHROPIC_API_KEY`.

`TOUCHSTONE_PROVIDER_MODE=tool` explicitly selects a bounded tool instead of a model for protocol testing. The saved actual proof used `model`. The seller refuses local-model quotes while the model health endpoint is unavailable.

### Hosted Claude and real-only comparison policies

The hosted tier uses Anthropic's Messages API with a constrained JSON schema and reports API-provided token usage. Set the API key only in the hosted seller's terminal; do not add it to the testnet buyer's environment, commits or chat. The default model is `claude-sonnet-5`. The seller readiness response checks only key/model configuration, not API entitlement or spend limit. The USDZ ledger measures Metal payments and checking charges, not the separate Anthropic API bill.

Run the local seller as `local-gpu` on port 8092 and hosted seller as `hosted-premium` on port 8093. The provider URLs must be passed to `engine-metal` in that order. A hosted call that becomes uncertain after dispatch is not repeated on restart; it can leave a paid receipt with missing output rather than risk duplicate API billing.

The real policies accept no simulator quotes: `real-cheapest` selects only the local GPU, `real-premium` selects only hosted Claude, and `real-touchstone` starts local then escalates to hosted only after a paid verifier rejection. First run `engine-metal --quote-only` with both origins; it performs no model inference and no payment. Then run each policy with the same seed/task set and a distinct scope, using explicit total budgets. The dashboard's live policy table is populated only by saved paid runs; it reports testnet USDZ plus verification costs, verifier-accepted outputs, failed provider spend and receipt reconciliation. Customer capture remains zero and Airwallex stays `NOT_RECONCILED`.

### Engine Metal route, chaos and restart

The unified engine requires RPC credentials, the local provider URL, a funded dedicated Metal wallet, a total budget and per-step cap. The testnet route uses only the Metal tier and never falls back to MockRail. Do not treat the probe as model eligibility evidence. A 30-step run with the 5-cent per-step ceiling needs up to USD 1.53 including the internal verification charges; a 50-step ceiling is USD 2.55.

Before authorizing a paid run, fetch a live quote for one generated public task. This checks the loopback model health, provider offer, Metal deployment and quote cap without creating a ledger run or sending payment or model inference:

```powershell
python -m touchstone engine-metal --scope quote-check --steps 1 --budget-usd 0.05 --price-cap-usd 0.05 --provider-url http://127.0.0.1:8092 --quote-only
```

macOS / Linux / Git Bash equivalent:

```bash
python -m touchstone engine-metal --scope quote-check --steps 1 --budget-usd 0.05 --price-cap-usd 0.05 --provider-url http://127.0.0.1:8092 --quote-only
```

The report says `LIVE_QUOTE_ONLY` and `payments_sent: 0`. It also reports `latency_samples`: zero means the displayed 1,000 ms is an explicit cold-start fallback, not an observed service-time measurement. Do not use customer data in quote probes.

```powershell
python -m touchstone engine-metal --scope engine-30-001 --steps 30 --budget-usd 1.53 --price-cap-usd 0.05 --execute
```

macOS / Linux / Git Bash equivalent:

```bash
python -m touchstone engine-metal --scope engine-30-001 --steps 30 --budget-usd 1.53 --price-cap-usd 0.05 --execute
```

To test provider outage before any quote, set `$env:TOUCHSTONE_PROVIDER_CHAOS = 'outage'` before starting `python tools/metal.py provider`; it returns 503 and no payment is initiated. To test a paid quality degradation, use `quality-drop`; the provider deliberately corrupts one result, which is charged and then rejected. Only use that mode with an explicit small test budget.

The process-kill demonstration spends a real request at `after_rail`, exits with code 86, recovers the same persisted scope without `--execute`, and then explicitly resumes the remaining steps:

```powershell
python -m touchstone engine-metal --scope engine-kill-001 --steps 30 --budget-usd 1.53 --price-cap-usd 0.05 --execute --kill-at after_rail
python -m touchstone engine-metal --scope engine-kill-001 --steps 30 --budget-usd 1.53 --price-cap-usd 0.05 --recover
python -m touchstone engine-metal --scope engine-kill-001 --steps 30 --budget-usd 1.53 --price-cap-usd 0.05 --execute
```

macOS / Linux / Git Bash equivalent:

```bash
python -m touchstone engine-metal --scope engine-kill-001 --steps 30 --budget-usd 1.53 --price-cap-usd 0.05 --execute --kill-at after_rail
python -m touchstone engine-metal --scope engine-kill-001 --steps 30 --budget-usd 1.53 --price-cap-usd 0.05 --recover
python -m touchstone engine-metal --scope engine-kill-001 --steps 30 --budget-usd 1.53 --price-cap-usd 0.05 --execute
```

The stable scope binds tasks, budget, cap and provider URL(s). Preserve those exact values across restarts. These are operator runbook instructions only; the real provider, chaos, 30-step run and kill/restart have not yet been executed in this checkout.

## Resume the existing funded proof

```powershell
python tools/prove_metal.py --withdraw-only
```

macOS / Linux / Git Bash equivalent:

```bash
python tools/prove_metal.py --withdraw-only
```

This resumes the existing withdrawal for `funded-proof-001` without replaying inference. The original proof preserves one reservation, a 0.10 USDZ deposit and a 0.01 USDZ purchase cap. Both cached retry and direct provider receipt replay were verified without another payment. The purchased model answer failed verification; its expense remains recorded. A non-deferred claim has now returned 0.09 testnet USDZ to the funding wallet.

A paid missing output remains blocked until the original provider accepts receipt replay. A definitive SDK refusal can establish `UNPAID_CONFIRMED`; only the same reservation, URL, seller and price may retry. SDK pending state is durable before sending, and is cleared only after definitive outcomes in the pinned version.

Withdrawals expose `empty`, `waiting`, queued and non-deferred claims separately. `empty` can mean funds are not finalized; it is not returned float. The proof records the queue and successful claim transactions separately. Repeated deposits are blocked until the original deposit is reconciled; no automatic top-up is implemented.

## Integrated banked job

After merchant configuration is enabled, a new test job can run:

```powershell
python -m touchstone banked-job --scope banked-proof-002 --integration-probe
python -m touchstone banked-job --scope banked-proof-002 --integration-probe --recover
python -m touchstone banked-status
```

macOS / Linux / Git Bash equivalent:

```bash
python -m touchstone banked-job --scope banked-proof-002 --integration-probe
python -m touchstone banked-job --scope banked-proof-002 --integration-probe --recover
python -m touchstone banked-status
```

The immutable mandate binds source, origin, hold, allocation and call cap. Authorization precedes funding/payment; exact receipt terms are checked before capture. Live checking fees are zero. The merchant absorbs sub-cent rounding and gas. Customer closure and returned-float completion are distinct. Fiat and token accounts remain separate; no automated bridge is implied. Treasury FX is a separate optional workflow, not connected to this job.

`banked-halt` stops new dispatches and `banked-resume` preserves limits. Funded jobs sharing the EVM key are serialized through a shared owner lock. The original three-job dashboard remains a financial simulator; actual banked jobs and paid evidence appear in separate panels.

References: [scoped keys](https://www.airwallex.com/docs/developer-tools/api/manage-api-keys), [key scopes](https://www.airwallex.com/docs/developer-tools/api/api-key-scopes), [sandbox settings](https://www.airwallex.com/docs/developer-tools/sandbox-environment/sandbox-settings), [PaymentIntent idempotency](https://www.airwallex.com/docs/payments/get-started/using-payments-intent-api), [Metal clearing](https://docs.metalntwx.com/agents/clearing).
