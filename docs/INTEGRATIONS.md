# Integration contracts and verified sources

Updated 30 October 2026. Credentials are local, one funded SDK inference purchase is verified, and Airwallex authentication/read access passes. Merchant PaymentIntent creation is blocked by `configuration_error`. See [actual proof](LIVE_PROOF.md) and [commands](ACCOUNT_SETUP.md).

## Airwallex transport and authorization

`treasury.py` pins `https://api.sandbox.airwallex.com`, refuses redirects, authenticates with Client ID/API key and optionally `x-login-as`, then reuses its token. It reports read permissions separately from authentication, so a scoped-key read denial is not misreported as an invalid API key. Tokens, raw bank account data and card fields are not printed.

`holds.py` implements create/confirm/retrieve/capture/cancel and persists immutable terms and operation UUIDs. Unknown outcomes are retained. Create recovery first reads the merchant order, then may replay the identical body and original UUID under Airwallex's documented idempotency. It never silently generates another create UUID. Capture/cancel unknown outcomes remain read-reconciled.

The fixed public test-card workflow uses USD whole cents and holds capped at USD 10. It excludes raw card fields, CVC and client secrets from persisted response data. Merchant configuration currently rejects creation before authorization. Native API checkout/PCI enablement is not provisioned by default and may require Airwallex support. The exact configuration issue is not established by the generic API error.

`banked-job` obtains authorization before allocating a clearing wallet and purchasing. It then captures actual accounted spend, records merchant-absorbed fractional cents and tracks returned float. Its full path is covered by controlled adapter tests. An actual external hold/capture has not yet completed. Hold increases, refunds, FX execution and token bridging are not implemented.

Sources: [authentication](https://www.airwallex.com/docs/api/authentication/api_access_token), [scoped keys](https://www.airwallex.com/docs/developer-tools/api/manage-api-keys), [Payment Intents](https://www.airwallex.com/docs/api/payments/payment_intents), [idempotency](https://www.airwallex.com/docs/payments/get-started/using-payments-intent-api), [sandbox settings](https://www.airwallex.com/docs/developer-tools/sandbox-environment/sandbox-settings).

## Metal SDK bridge and seller

`touchstone.metal.MetalRail` invokes `bridge.mjs` over stdin/stdout. Portable Node 22.23.4, Metal SDK 0.3.3 and viem 2.57.13 are pinned and locked. The original multi-job simulator retains `MockRail`; real errors never silently fall back to mocks.

The bridge discovers the supported clearing deployment and verifies RPC chain ID 63825. The SDK owns cryptography, invoices, receipts and payment state. A SQLite implementation of its supported store interface provides Windows durability and exclusive per-wallet ownership. Each job retains a separate clearing key and purchase history. Funding jobs sharing the EVM account also use a shared owner lock.

| Operation | Implemented behavior |
|---|---|
| Wallet | Persisted signer/store; never print private key; refuse simultaneous owners |
| Funding | Exact capped deposit; broadcast and spendability are separate; duplicate deposit blocked |
| Quote | Bind resource, seller, chain, asset, deployment, amount and expiry |
| Purchase | Persist reservation before SDK payment; enforce cap and total wallet budget |
| Recovery | Replay the held SDK invoice or retrieve the original paid delivery |
| Definitive refusal | `UNPAID_CONFIRMED` permits only identical reservation terms to retry |
| Withdrawal | Report empty/waiting/queued/claimed; count actual distinct non-deferred claims |

SDK pending state is durably stored before send and cleared only after verified receipt or authoritative refusal. Recovery uses that protocol state, not an empty remote lookup, to distinguish an unpaid retry from an uncertain payment. Held invoices retain their original URL and price. The exact fallback is disabled and its ephemeral EVM account is unfunded.

The included loopback seller issues real x402 requirements, validates task-digest resource binding, verifies SDK signatures against chain/service state, and caches delivery by payment ID. A plain receipt replay cannot create a replacement payment. The provider receives no funding or Airwallex keys, and its model worker receives no RPC credential. It has one execution slot and refuses quotes when the local model is unavailable.

Seventeen Node tests cover wallets, price/unit caps, immutable retries, pending invoice replay, unpaid refusal handling, durable delivery and source binding. A separate actual proof records a 0.10 USDZ deposit, one 0.01 USDZ GPU inference purchase, identical buyer/provider replays, and a non-deferred return of the remaining 0.09 USDZ. The purchased output failed source verification; the charge remains recorded. Receipt assurance remains preconfirmed.

Sources: [Metal clearing](https://docs.metalntwx.com/agents/clearing), [x402](https://github.com/coinbase/x402), pinned SDK source/types under installed `@metalntwx/metal-pay`.

## Model and evaluation boundary

`tools/setup_local.py` installs hash-verified official llama.cpp Vulkan and publisher-hosted Qwen GGUFs with license metadata. `tools/profile_local.py` owns an isolated server, records paired seeds, actual timings and GPU telemetry, then shuts it down. `tools/run_local.py` runs the installed model for the paid provider.

Two measured tiers achieved 22.2% and 48.9% strict correctness on 90 calls each. Raw profiles include available layer-offload logs and VRAM evidence. Paired replay uses assumed prices and rejects a blanket cheap-first savings claim. Bounded tools solve 1,000 generated tasks without model calls. The deduplicated offline eligibility screen authorizes no model for autonomous procurement. Protocol probes require their explicit purpose flag and do not bypass this screen while claiming useful autonomous model selection.

The main dashboard's three-job scenario remains simulated. Its separate actual-evidence panel and banked-job journal report the real integration state. A complete banking demonstration still needs merchant configuration resolved, actual hold/capture, finality of the paid inference receipt and a qualified model on representative finance-operations sources.
