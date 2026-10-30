# Live integration evidence — 30 October 2026

## Metal testnet: executed

The dedicated EVM wallet was created locally; its private key is in ignored `data/metal/funding-wallet.json`. The user funded its public address using the Metal console faucet. Read-only RPC verification observed chain **63825**, with 100 testnet USDZ before the probe. Authenticated RPC URLs and API keys are excluded from this report.

The probe deposited **0.10 testnet USDZ** into its own persisted clearing wallet, purchased **one 0.01 testnet USDZ inference call**, and retained the actual SDK invoice, signed receipt and output. `bench/results/metal-paid-proof.json` contains the redacted evidence. These are test assets, not a fiat conversion or a transfer from an Airwallex balance.

| Evidence | Observed result |
|---|---|
| Approval transaction | `0x8824f8a68523a692805c64f1fec38eb1efbe1de2b96ebc9aff9b78cc637f5fda` |
| Deposit transaction | `0xe0bcbffaa1a746c93c2efebeb741bbfea552ba77b513dbee9e43411cfb8eae08` |
| Actual paid calls | 1 |
| Provider | Local Qwen2.5 1.5B Q4_K_M on NVIDIA Vulkan |
| Model output | `{"total_cents": 1250}` |
| Source-correct answer | `{"total_cents": 2000}` |
| Online verifier | Rejected the result |
| Cached buyer retry | Identical original result; no second payment |
| Provider receipt replay | Original signed proof returned identical stored delivery; no payment creation |
| Receipt assurance | Preconfirmed; no per-call blockchain transaction hash invented |
| Unused float | 0.09 testnet USDZ returned in non-deferred claim transaction `0x5e6f4e180c98f5843db3d98c7cc149c19e9f79c0c12b24235901ae3de30b398d`; withdrawal was queued in transaction `0xf5a00b55cdb84d5ffaf9d5a04b8c73aba7238ee858270641c8b05d4af8d73a98` |

The SDK confirmed the withdrawal claim after epoch `93301` finalized. `returned_float_confirmed` is true. Run `python tools/prove_metal.py --withdraw-only` to recheck withdrawal state; it retains the queue and claim transaction history and does not replay the paid inference request.

The initial attempt hit a clearing epoch refusal. Recovery examined the durable SDK state, which stores pending before sending and clears it only for a verified receipt or authoritative refusal. An unpaid reservation could retry only the same URL, seller, deployment and price. Unknown held invoices retain the original SDK invoice and block replacement purchases. This behavior is covered by separate local tests.

The test is an explicit protocol probe. These generated arithmetic inputs can be solved locally; the purchase is not a claim that inference was economically necessary. The failed answer and its charge remain in the evidence. Neither measured model has autonomous procurement authorization.

## Airwallex sandbox: authenticated; direct create blocked; hosted fallback untested

The supplied scoped key and Client ID authenticate successfully. After the user updated its account-level permissions, balance and Global Account reads both passed. No token, API key, raw account details, card body or client secret is retained in public evidence.

PaymentIntent creation returns **HTTP 400 `configuration_error`** with the message:

> Invalid request against merchant configuration. Please contact your account manager.

No customer authorization or capture has been completed. See `bench/results/airwallex-hold-proof.json` and `airwallex-readiness.json`. Unresolved create scopes remain in the private operation journal; they have not been treated as successful authorizations or available liquidity.

The direct PaymentIntent route remains blocked by merchant configuration. A browser-assisted alternative is now implemented with the beta Checkout Sessions API at version `2026-05-29`; it creates an uncaptured card session, returns a hosted URL to the operator, and verifies authorization from read-back state. That path is not yet exercised and requires the sandbox payment account ID, Checkout Sessions read/write scope, and an activated payment method. The [Checkout Sessions guide](https://www.airwallex.com/docs/payments/integration-options/web-checkout/checkout-session/quickstart) explains its account/API prerequisites, while [sandbox settings](https://www.airwallex.com/docs/developer-tools/sandbox-environment/sandbox-settings) notes Native API checkout/PCI enablement is not provisioned by default.

The integrated `banked-proof-001` create operation is still journaled as `UNKNOWN` after HTTP 400 `duplicate_request`. A read-only lookup by its merchant order ID found no matching PaymentIntent at the time checked. Preserve this scope and do not count it as an authorization; the create outcome needs Airwallex reconciliation.

## Integrated job implementation

`python -m touchstone banked-job --scope banked-proof-001 --integration-probe --recover` resumes one durable sandbox/testnet job. Its immutable mandate includes source, provider URL, price cap, allocation, hold and purpose. The job obtains an actual authorization before allocating a funded clearing wallet, then reserves a quote, pays, verifies, captures accounted spend and tracks withdrawal claims. The full path passes controlled adapter tests; the actual banked job is currently blocked at PaymentIntent creation.

Live probe checking fees are zero. Customer capture rounds provider spend down to whole cents and records the sub-cent difference as merchant expense. Gas and any native-token costs are not charged to the customer. Fiat and token accounts remain separate; no automated bridge or FX conversion is implemented. Funded jobs sharing the EVM account are serialized to avoid nonce and allocation races.

The three-job dashboard scenario remains a simulator. Its separate real-evidence panel and banked-job journal disclose the state of these integrations.
