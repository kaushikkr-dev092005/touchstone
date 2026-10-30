# Account setup and integrated test runbook

Updated 30 October 2026. The user has created both accounts, configured local credentials and funded a dedicated testnet wallet. RPC, Airwallex authentication/account reads, and one actual paid Metal inference call are verified. Airwallex merchant configuration currently blocks PaymentIntent creation. See [live evidence](LIVE_PROOF.md).

## Local configuration

The CLI reads ignored `data/local-config.json` and optional `data/metal/funding-wallet.json`. Environment variables take precedence. `.env.example` documents names but is not auto-loaded. Restart long-running processes after changing credential values. Never put credentials in tracked files.

```powershell
python -m touchstone doctor
python -m touchstone rpc-smoke
python -m touchstone metal-funding
python -m touchstone airwallex-smoke
```

These checks do not send a financial transaction. Doctor reports configuration presence and saved observations, not secret values. RPC must identify chain 63825. `metal-funding` reads gas and USDZ balances of the dedicated public address.

## Airwallex permissions and merchant setup

For a new checkout, create a sandbox account at https://www.sandbox.airwallex.com/signup. In Developer > API keys, configure account-level **Payment Acceptance: Write** and **Global Accounts: Read** or **Balances: Read**. Organization webhook access alone is insufficient. Select one sandbox account, or set `AIRWALLEX_ACCOUNT_ID` for the selected account if the key spans several. Its value is sent as `x-login-as` during authentication.

The current account now passes login, balances and Global Account reads. Create returns HTTP 400 `configuration_error`: Invalid request against merchant configuration. The error does not identify the exact missing setting, and it occurs before card confirmation. Current sandbox documentation says Hosted Payment Page is the default checkout, while Native API checkout and PCI DSS enablement require Airwallex Support. Ask Support to confirm Payments activation, merchant configuration and the allowed checkout mode before retrying. If Native API is unavailable, the workflow needs a customer-facing hosted-checkout path; that path has not been implemented.

After merchant setup is resolved, use a fresh, clearly named test scope and retain all failed scopes:

```powershell
python -m touchstone airwallex-hold --scope touchstone-smoke-002 --hold-usd 1.00 --capture-usd 0.50
python -m touchstone airwallex-hold --scope touchstone-smoke-002 --hold-usd 1.00 --capture-usd 0.50 --recover
```

The fixed public sandbox card workflow is limited to USD 10 holds and whole cents. It persists UUIDs before dispatch, captures once and cancels remaining capture-ready authorization. Review/customer-action states are incomplete. Unused authorization does not prove issuer balance availability.

Recovery reads existing intents. For unresolved create only, it may replay the identical body using the original UUID under documented Airwallex idempotency. It never silently invents another create UUID. Unknown capture/cancel outcomes remain read-reconciled. A cached `duplicate_request` from a rejected create is not authorization; preserve that scope for inspection.

## Metal wallet and runtime

For a fresh checkout, prepare portable Node and dependencies:

```powershell
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

The model uses NVIDIA Vulkan on loopback port 8080. The x402 seller binds loopback port 8092, binds the public task digest to its resource URL, and verifies real signed receipts against chain and service state. A delivery journal returns the original stored result when that paid proof is replayed. The provider receives no Airwallex credentials or EVM funding key; the model worker receives no RPC credential.

`TOUCHSTONE_PROVIDER_MODE=tool` explicitly selects a bounded tool instead of a model for protocol testing. The saved actual proof used `model`. The seller refuses model quotes while the model health endpoint is unavailable.

## Resume the existing funded proof

```powershell
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

The immutable mandate binds source, origin, hold, allocation and call cap. Authorization precedes funding/payment; exact receipt terms are checked before capture. Live checking fees are zero. The merchant absorbs sub-cent rounding and gas. Customer closure and returned-float completion are distinct. Fiat and token accounts remain separate; no bridge or FX conversion is implied.

`banked-halt` stops new dispatches and `banked-resume` preserves limits. Funded jobs sharing the EVM key are serialized through a shared owner lock. The original three-job dashboard remains a financial simulator; actual banked jobs and paid evidence appear in separate panels.

References: [scoped keys](https://www.airwallex.com/docs/developer-tools/api/manage-api-keys), [key scopes](https://www.airwallex.com/docs/developer-tools/api/api-key-scopes), [sandbox settings](https://www.airwallex.com/docs/developer-tools/sandbox-environment/sandbox-settings), [PaymentIntent idempotency](https://www.airwallex.com/docs/payments/get-started/using-payments-intent-api), [Metal clearing](https://docs.metalntwx.com/agents/clearing).
