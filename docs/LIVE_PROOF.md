# Live integration evidence — 30 October 2026

M1 update, 2 November: **no new live financial evidence**. The environment-only doctor could not see the required Airwallex variables in the agent process and made no API requests. The user reports local setup in another terminal. A new treasury job lifecycle and scope-retirement path passed controlled-adapter tests; their saved proof is **MOCK**. No private historical scope was read or retired. See [M1 report](M1_REPORT.md) and [support draft](AIRWALLEX_SUPPORT_REQUEST.md).

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

Live probe checking fees are zero. Customer capture rounds provider spend down to whole cents and records the sub-cent difference as merchant expense. Gas and any native-token costs are not charged to the customer. Fiat and token accounts remain separate; no automated bridge is implemented. A separate Airwallex Treasury FX workflow has since been added, but it has not been configured or exercised and is not connected to Metal funding. Funded jobs sharing the EVM account are serialized to avoid nonce and allocation races.

The three-job dashboard scenario remains a simulator. Its separate real-evidence panel and banked-job journal disclose the state of these integrations.

## 2 November code update (not live evidence)

The provider worker now supports hosted Claude through the Messages API with schema-constrained JSON and records the usage counts returned by that API. The buyer bridge strips Anthropic and Airwallex credentials from its child environment. Hosted delivery is at-most-once after the server durably marks a request running: a crash/timeout will not trigger a second potentially billable model call, but may leave a paid receipt with no recoverable answer.

`engine-metal` now has three live-only policies for the local GPU tier and hosted premium tier. The local-only, hosted-only and local-first/escalate policies require both quote identities to pass a no-payment preflight, and their engine offers exclude every simulator quote. Each run measures Metal testnet spend plus verification charges per verifier-accepted output, stores reported hosted token counts, and writes a local evidence file for the dashboard's separate live-trial panel. This is an implemented path only: no Anthropic API request, matched three-policy paid run, or dashboard live-policy result has been recorded. Hosted API dollar cost is separate and excluded from the USDZ metric; customer capture is zero.

No Airwallex write was attempted. `AIRWALLEX_ACCOUNT_ID` remains unset; Conversion Write scope, a specific approved currency pair/amount, the conversion and reconciliation against both wallet-history entries are outstanding. No AgentOS/CLI/MCP/skills or sponsor Slack connector is available in this workspace.

## 1 November readiness update

The Qwen2.5 0.5B Q4_K_M economy model runtime was started on the local Vulkan path; the loopback x402 seller reported model health ready on testnet chain 63825. `engine-metal --quote-only` obtained a $0.01 quote for a generated invoice task. Queue depth was zero and no payment was sent. The reported 1,000 ms latency is the provider's cold-start fallback with zero completed-delivery samples, not measured inference latency. This preflight did not produce a model output or paid engine step. Redacted evidence is saved in `bench/results/metal-provider-quote.json`.

The seller's real outage chaos mode was also exercised on that quote-only route. It returned HTTP 503 before offer, and the engine reported "no purchase was dispatched"; no payment was sent. This verifies the no-quote outage boundary only. A paid quality-drop scenario and process-kill/restart still require an explicitly funded wallet and approved budget. Evidence is saved in `bench/results/metal-provider-outage.json`.

The read-only `python -m touchstone airwallex-smoke` run authenticated and read balances and Global Accounts. It reported `account_context_configured: false` because `AIRWALLEX_ACCOUNT_ID` is unset; Checkout Sessions read access and FX conversion read access were therefore not tested. The smoke performed no writes. No Checkout Session, FX quote or conversion was created.

The code now has a unified engine-facing Metal rail, explicit `engine-metal` command, queue-sensitive quotes with explicit latency sample counts, fail-closed recovery, opt-in provider outage/quality-drop modes and an abrupt process-kill recovery boundary. The live quote-only path and an outage returning 503 before quote have been exercised without payment. No 30–50 paid-step run, paid quality-drop run or real Metal kill/restart has taken place: the provider URL is not persistently configured, and the prior testnet wallet balance was withdrawn. The Airwallex customer-hold side remains `NOT_RECONCILED` in the engine because no customer authorization/capture completed. FX wallet-history reconciliation is a separate read-only report, not a customer-payment reconciliation.

The invoice fault-injection study is synthetic: across 20 ten-line inputs and 100 seeded checks per input, the noisy checker false-accepted 79.0% of offsetting errors when sampling one line (20.9% when sampling five). The exact source-arithmetic checker false-accepted none of the 20 injected cases. These rates are test measurements, not real invoice prevalence estimates.
