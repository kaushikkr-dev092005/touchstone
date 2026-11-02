# Integration contracts and verified sources

Updated 1 November 2026. Credentials are local, one funded SDK inference purchase is verified, and Airwallex authentication/read access passes. Direct PaymentIntent creation is blocked by `configuration_error`; hosted checkout remains untested. The engine Metal route has returned a live quote from the loopback GPU seller without paying; no integrated live inference output was produced. The seller's outage mode returned 503 before quote/payment; paid engine and quality-drop/kill-restart runs remain unexercised. FX operations remain untested. See [actual proof](LIVE_PROOF.md) and [commands](ACCOUNT_SETUP.md).

## Airwallex transport and authorization

`treasury.py` pins `https://api.sandbox.airwallex.com`, refuses redirects, authenticates with Client ID/API key and optionally `x-login-as`, then reuses its token. It reports read permissions separately from authentication, so a scoped-key read denial is not misreported as an invalid API key. Tokens, raw bank account data and card fields are not printed. `checkout.py` uses Checkout Sessions API version `2026-05-29` for a hosted, user-present card flow; it disables auto-capture, persists only safe session/intent fields, and resumes by read-only scope lookup if create response is lost. It requires `AIRWALLEX_ACCOUNT_ID` and Checkout Sessions read/write scope.

`holds.py` implements create/confirm/retrieve/capture/cancel and persists immutable terms and operation UUIDs. Unknown outcomes are retained. Create recovery first reads the merchant order, then may replay the identical body and original UUID under Airwallex's documented idempotency only when the ID has not been consumed. HTTP 4xx `configuration_error` on create is a definitive `REJECTED_NO_OBJECT`; `duplicate_request` is `REQUEST_ID_CONSUMED` without proving whether an object exists. Neither state permits a replay. Capture/cancel unknown outcomes remain read-reconciled. `airwallex-retire` requires recorded rejection or operator-attested support evidence, fresh complete empty read-back and a new scope; it preserves a local tombstone, not a remote cancellation. See [M1 runbook](M1_RUNBOOK.md).

The fixed public test-card workflow uses USD whole cents and holds capped at USD 10. It excludes raw card fields, CVC and client secrets from persisted response data. Merchant configuration currently rejects creation before authorization. Native API checkout/PCI enablement is not provisioned by default and may require Airwallex support. The exact configuration issue is not established by the generic API error.

`banked-job` obtains authorization before allocating a clearing wallet and purchasing. It then captures actual accounted spend, records merchant-absorbed fractional cents and tracks returned float. Its full path is covered by controlled adapter tests. The HPP authorization can continue into that workflow without creating a duplicate PaymentIntent. An actual external hold/capture has not yet completed. Hold increases, refunds and token bridging are not implemented.

### Treasury FX

`airwallex-fx` exposes current wallet balances, quote creation, guarded conversion creation, request-ID recovery and a read-only spend report. Read-only operations need account context plus **Core Resources > Balances > Read** and **Transactional FX > Conversion > Read**. Quote/conversion writes need **Transactional FX > Conversion > Write**. The conversion journal stores the request ID, quote ID, immutable terms and opening balances before posting. If the response is uncertain, it looks up that same request ID and refuses a second write. The report compares a settled conversion with both corresponding wallet-history entries and displays current balances. No live quote or conversion has been attempted because `AIRWALLEX_ACCOUNT_ID` is unset and write scopes are unverified.

Sources: [Airwallex API key scopes](https://www.airwallex.com/docs/developer-tools/api/api-key-scopes), [conversion API](https://www.airwallex.com/docs/api/transactional_fx/conversion), [quotes API](https://www.airwallex.com/docs/api/transactional_fx/quotes), [balances API](https://www.airwallex.com/docs/api/core_resources/balances/current).

M1 adds an environment-only `airwallex-doctor --probe-reads` and job-linked `treasury-job` lifecycle. Settled conversions must match quote terms and both wallet entries before append-only Airwallex currency entries are recorded. An explicit demo rate creates a separate **SIMULATED** USDZ accounting entry; it cannot fund or increase real Metal float. `banked-job --treasury-request-id` requires matching reconciled treasury evidence for that scope and still independently checks actual testnet wallet funding. The dashboard shows all stages with evidence labels. The saved M1 exercise is **MOCK**; no real FX quote/conversion ran. Airwallex hold/checkout/banked commands require `--execute`, and FX conversion also requires `--sell-currency` and `--max-sell-amount`. Written chat approval is a separate human gate.

### Airwallex CLI, MCP and AgentOS boundary

The current Airwallex guide separates sandbox development connectors from production AgentOS. The Airwallex CLI can use sandbox or production, but the beta CLI officially supports macOS/Linux; this Windows checkout has no CLI or Airwallex MCP tools connected. The AgentOS MCP endpoint and AgentOS workflow skills are production-account connectors, not a safe substitute for sandbox testing. Do not connect them to production without the account owner's explicit OAuth approval and an approved production use case.

For this sandbox project, use the Airwallex Developer MCP/Docs MCP for sandbox development and documentation. The current hackathon guide says FX conversions have no MCP tool, so the actual conversion must go through the sandbox REST API (the `airwallex-fx` adapter) and a human-approved request ID. The current terminal environment does not provide a connected MCP session, and the sponsor has not confirmed whether the CLI/Developer MCP path satisfies its “Airwallex tooling” criterion. Ask the sponsor in Slack before claiming that criterion. The account ID and conversion write scope are also not set, so no write has been attempted.

Sources: [Airwallex CLI](https://www.airwallex.com/docs/developer-tools/cli), [AgentOS and connector environments](https://www.airwallex.com/docs/developer-tools/ai/agentos), [sandbox Developer MCP setup](https://airwallex.com/en-us/blog/devx-ai-guide), [hackathon guide](https://airwallexdev.com/guide).

Sources: [authentication](https://www.airwallex.com/docs/api/authentication/api_access_token), [scoped keys](https://www.airwallex.com/docs/developer-tools/api/manage-api-keys), [Payment Intents](https://www.airwallex.com/docs/api/payments/payment_intents), [Checkout Sessions](https://www.airwallex.com/docs/api/checkout/checkout_sessions), [API versioning](https://www.airwallex.com/docs/api/versioning), [sandbox settings](https://www.airwallex.com/docs/developer-tools/sandbox-environment/sandbox-settings).

## Metal SDK bridge and seller

`touchstone.metal.MetalRail` invokes `bridge.mjs` over stdin/stdout. Portable Node 22.23.4, Metal SDK 0.3.3 and viem 2.57.13 are pinned and locked. `CompositeRail` presents a common quote/pay/lookup/recover/reconcile contract to the engine and dispatches by the persisted quote provider; real errors never silently fall back to mocks. The dedicated `metal-probe` policy routes only to Metal.

The bridge discovers the supported clearing deployment and verifies RPC chain ID 63825. The SDK owns cryptography, invoices, receipts and payment state. A SQLite implementation of its supported store interface provides Windows durability and exclusive per-wallet ownership. Each job retains a separate clearing key and purchase history. Funding jobs sharing the EVM account also use a shared owner lock.

| Operation | Implemented behavior |
|---|---|
| Wallet | Persisted signer/store; never print private key; refuse simultaneous owners |
| Funding | Exact capped deposit; broadcast and spendability are separate; duplicate deposit blocked |
| Quote | Bind resource, seller, chain, asset, deployment, amount and expiry; apply live queue-depth pricing and report service-time sample count beside its estimate |
| Purchase | Persist reservation before SDK payment; enforce cap and total wallet budget |
| Recovery | Replay the held SDK invoice or retrieve the original paid delivery |
| Definitive refusal | `UNPAID_CONFIRMED` permits only identical reservation terms to retry |
| Withdrawal | Report empty/waiting/queued/claimed; count actual distinct non-deferred claims |

SDK pending state is durably stored before send and cleared only after verified receipt or authoritative refusal. Recovery uses that protocol state, not an empty remote lookup, to distinguish an unpaid retry from an uncertain payment. Held invoices retain their original URL and price. The exact fallback is disabled and its ephemeral EVM account is unfunded.

The included loopback seller issues real x402 requirements, validates task-digest resource binding, verifies SDK signatures against chain/service state, and caches delivery by payment ID. Queue depth is measured from pending deliveries; each queued task adds 20% to the current quote, capped at the configured USD 0.05 seller maximum. The exact offer is durably recorded and matched on paid delivery. Quotes report the completed-delivery sample count so the default pre-first-delivery latency estimate is not mistaken for measured timing. A plain receipt replay cannot create a replacement payment. The provider receives no funding or Airwallex keys, and its model worker receives no RPC credential. It runs one task at a time and refuses quotes when the local model is unavailable.

Explicit local chaos controls are `TOUCHSTONE_PROVIDER_CHAOS=outage` (503 before an offer, so no call is paid) and `quality-drop` (a paid, deliberately corrupted delivery). The latter keeps aggregate invoice totals balanced while corrupting line arithmetic. The engine also supports `--kill-at after_rail`, which terminates the Python process after the rail returns a paid receipt, plus `--recover` against the same durable scope. The outage mode has been exercised once through a live quote-only request; paid quality-drop and kill/restart remain unrun. A single historical Metal payment is not the requested 30–50-step integrated run.

The Node tests cover wallets, price/unit caps, immutable retries, pending invoice replay, unpaid refusal handling, durable delivery and source binding, queue-aware pricing and injected quality loss. A separate actual proof records a 0.10 USDZ deposit, one 0.01 USDZ GPU inference purchase, identical buyer/provider replays, and a non-deferred return of the remaining 0.09 USDZ. The purchased output failed source verification; the charge remains recorded. Receipt assurance remains preconfirmed.

Sources: [Metal clearing](https://docs.metalntwx.com/agents/clearing), [x402](https://github.com/coinbase/x402), pinned SDK source/types under installed `@metalntwx/metal-pay`.

## Model and evaluation boundary

`tools/setup_local.py` installs hash-verified official llama.cpp Vulkan and publisher-hosted Qwen GGUFs with license metadata. `tools/profile_local.py` owns an isolated server, records paired seeds, actual timings and GPU telemetry, then shuts it down. `tools/run_local.py` runs the installed model for the paid provider.

Two measured tiers achieved 22.2% and 48.9% strict correctness on 90 calls each. Raw profiles include available layer-offload logs and VRAM evidence. Paired replay uses assumed prices and rejects a blanket cheap-first savings claim. Bounded tools solve 1,000 generated tasks without model calls. The deduplicated offline eligibility screen authorizes no model for autonomous procurement. Protocol probes require their explicit purpose flag and do not bypass this screen while claiming useful autonomous model selection.

The main dashboard's three-job scenario remains simulated. Its separate actual-evidence panel and banked-job journal report the real integration state. A complete banking demonstration still needs merchant configuration resolved, actual hold/capture, finality of the paid inference receipt and a qualified model on representative finance-operations sources.
