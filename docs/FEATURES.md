# Procurement extensions — 6 November 2026

Status key: **IMPLEMENTED** code and tests exist and ran against controlled adapters only;
**MEASURED** a real local observation exists; **BLOCKED** an external credential, grant or spend
approval is required. The follow-up verified sandbox issuing reads, one approved
synthetic delegate and a single-use USD 0.01 sandbox card, with no merchant payment.
Visa approval is pending; merchant Agentic Commerce config and fiat merchant
settlement remain unverified. [Current evidence](EXTERNAL_ACCESS.md).

Implementation is local Python stdlib plus the existing pinned Metal SDK and viem.
No runtime dependency was added. Tests use controlled adapters; none purchases a
service, issues a card, settles a credit or converts funds.

## 1. Signed inferential-fault receipts

`python tools/fault_proof.py --help` describes creation and offline verification.
The bounded contract currently covers integer USD invoice/arithmetic faults, not
general semantic correctness. The artifact retains the original task, output,
payment invoice, receipt signatures, verifier provenance and reproducible numeric
counterexample. Domain-separated Merkle hashing binds those sections. A buyer
signature attests the fault statement; the provider must independently validate
the original contract, delivery and arithmetic before applying its policy.

**MEASURED:** the historical paid result claimed 1,250 cents while its source
recomputes to 2,000. The saved artifact was signed with the existing buyer wallet
without creating a wallet or sending a transaction. A read-only chain-63825
operator-context/journal check verified the original payment signatures.
[Fault artifact](../bench/results/faults/metal-fault.json).

Commitment root:
`2ee0189fdb3df446bb90ecd48ffb04d1d136c2a12e6138aee67a5479f88d52ac`.

**Limits:** the historical provider output was unsigned. It cannot become
cryptographically attributable retroactively. Its receipt is preconfirmed; final
settlement is not independently proven. No refund or actual credit was issued.
Offline checks without an independently trusted operator key explicitly report
that key as unanchored.

Future seller deliveries carry a separate signature binding output, task,
resource and payment. `/faults/review` checks that signed delivery against its
durable cache, reproduces the fault and persists nonce/invoice replay protection.
The default live review policy grants no credit. Controlled acceptance and
rejection paths produce signed acknowledgements, preserve the original charge
and never net an acknowledgement against settled cash.
[MOCK identity / MEASURED signature example](../bench/results/features/controlled-credit-acknowledgement.json).

### Automatic fault receipts (IMPLEMENTED)

`Engine(ledger, rail, fault_pipeline=FaultPipeline(...))` hands every deterministic verification
failure to `touchstone/fault_pipeline.py`. Per payment key, durably and idempotently, it rebuilds the
saved-purchase record from the rail's own lookup, creates and re-validates the proof, signs it with
the job's existing wallet (never a new one), submits it to the original provider's `/faults/review`
origin (HTTPS or loopback only, no redirects), verifies the provider's acknowledgement signature
offline with the provider's own verifier, and retains it in the `fault_receipts` table. An outage
leaves `SUBMIT_PENDING` for `retry_pending()`; a forged or mismatched acknowledgement is `ACK_INVALID`
and ignored; an unsupported task or missing signed delivery is `NOT_ELIGIBLE`. Any pipeline error is
swallowed after logging so procurement never stops. Acknowledgements are never refunds and are never
netted against the settled charge. `engine-metal` and the authorized live dashboard enable it by
default. **Not yet observed:** a live provider acknowledging a real fault; the default live review
policy still grants no credit.

## 2. CardRail and controlled signed intent

`python tools/card_rail.py --help` exposes a sandbox-only issuing doctor, guarded
create and read-only reconciliation. Controls bind a single-use virtual card to
an existing cardholder, currency, whole-cent transaction/all-time cap, one-hour
expiry and blocked cash withdrawal. A durable request ID precedes dispatch;
uncertain creation never automatically retries. No PAN/CVC endpoint is used.
Issuing a card is not a merchant payment: `pay` refuses without a separately
verified merchant adapter. The existing Metal path remains independent.

**MEASURED, 10 November:** fresh login and Cards, Cardholders, Config and balance
reads pass after the operator enabled the three issuing read scopes. The earlier
401 is resolved. No card was created. Card creation needs its own write access,
existing cardholder and separately approved cap. `doctor --diagnose` and the
dashboard's authenticated recheck distinguish account authentication from issuing
permission denial, save only sanitized diagnostics and bind evidence to the account.
[Readiness](../bench/results/features/card-readiness.json).
The contract follows [Airwallex create card documentation](https://www.airwallex.com/docs/api/issuing/cards/create);
live write/read-back compatibility remains unverified.

**MOCK identity / MEASURED cryptography:** a controlled loopback merchant accepted
one RFC 9421 Ed25519 signed intent (HTTP 200), then rejected its replay (403).
The implemented agent-recognition profile binds authority, path, method, body
digest, expiry and nonce to a pinned local public key. It does not implement Visa
onboarding, Visa key trust/discovery, consumer/payment containers or a payment.
Do not claim Visa-approved identity, full TAP interoperability or award eligibility.
[Probe](../bench/results/features/tap-probe.json),
[Visa TAP specification](https://developer.visa.com/docs/trusted-agent-protocol/trusted-agent-protocol-specifications).

### Merchant payment, key directory and hold increases (IMPLEMENTED, controlled adapters only)

`CardRail.pay(scope, amount, adapter=..., execute=True)` re-reads the issued card, re-verifies it is
active, single-use, unexpired, in the purchase currency and large enough for the exact amount, writes a
durable request, calls a `MerchantAdapter`, and refuses to retry after any uncertainty.
`touchstone/merchant.py::SignedIntentMerchant` posts an RFC 9421 Ed25519 intent (signed by
`integrations/metal/tap-sign-cli.mjs` with an *existing* key file) to an HTTPS or loopback merchant and
accepts only an acknowledgement that echoes the intent with signature, intent and replay checks true.
No PAN/CVC is ever requested or sent. A merchant acknowledgement is **not** settlement:
`settlement_verified` and `merchant_payment_completed` stay false until an adapter supplies independent
settlement evidence.

`keysFromJwks` lets the merchant verifier trust an Ed25519 JWKS key directory (time-limited,
`trust_source=KEY_DIRECTORY`). It never sets `visa_approved_agent`: that needs Visa onboarding and key
trust this repository does not have. **BLOCKED:** genuine Visa integration and any issuing write.

`SandboxHoldWorkflow.increase` raises a mandate's *real* authorization by authorizing one
supplemental sandbox PaymentIntent through the existing journaled create/confirm path (Airwallex
incremental authorization is not assumed). It dry-runs the ledger change first, verifies the parent is
still uncaptured, and raises the local mandate only after the supplement is observed ready; an uncertain
outcome leaves the mandate unchanged and never recreates the intent. Capture/cancel each intent in its
own scope. CLI: `python -m touchstone airwallex-hold-increase ... --execute`. **Not yet observed:** a
real sandbox supplemental authorization; the unused remainder is not a wallet credit.

## 3. FX-aware procurement

`Router.select_fx` compares converted provider cost, explicitly bounded FX/rail
and check fees, and bounded expected retry cost. Exact rational arithmetic rounds
costs upward. Fresh rates, known pair orientation, disclosed FX fees, current
quality qualification, latency, budget and funded fiat account gates all apply.
USDZ is a separate token account and is never treated as fiat USD.

**MEASURED reference quote / SIMULATED offers:** the dashboard can explicitly
refresh a non-settling Airwallex FX quote. An expired saved quote is labelled
expired. Provider prices and funding assumptions in this preview are illustrative;
neither actual local model is qualified and no fiat merchant is configured.
No preferred live provider or dispatch is claimed.
[Saved reference](../bench/results/features/fx-quote.json).

**SIMULATED:** a controlled comparison changes preference from the EUR offer to
the USD offer as FX changes, with quality held fixed and explicit fees included.
[Comparison](../bench/results/features/controlled-fx.json).
Retry independence is a stated modeling assumption, not a measured guarantee.
This is procurement comparison, not arbitrage or a fiat-to-token bridge.

Rebalancing is a separate threshold/minimum-size plan, requiring the existing
guarded FX command and fresh written approval. No conversion occurs per call.
The previous one-conversion approval was consumed by the settled M1 proof.
[Airwallex FX quote contract](https://www.airwallex.com/docs/api/transactional_fx/quotes/create).

### Funded fiat execution (IMPLEMENTED, controlled adapters only)

`touchstone/fx_execution.py::execute_preferred` is the only bridge from comparison to dispatch. It
requires `--execute`; re-runs the comparison at execution time with MEASURED offers only; requires a
written approval bound to scope, provider, named approver, maximum effective cost and expiry; reads the
fiat wallet balance for the card currency; writes a single-use journal row; then calls `CardRail.pay`.
A card in a different currency is refused (no conversion happens). A pre-dispatch refusal releases the
journal row so a corrected retry is possible; an uncertain merchant outcome never retries. **BLOCKED:**
a real funded fiat merchant; this repository has none configured.

## 4. Measured GPU capacity

`GET /api/telemetry` and SSE expose timestamped NVIDIA driver observations: GPU
identity, temperature, utilization, VRAM, power, clocks and actual thermal-slowdown
flags. Samples cache for five seconds; failed samples become BLOCKED. These are
local measurements, not remote hardware attestations.
[Saved sample](../bench/results/features/telemetry.json).

The seller quotes a compact telemetry reference, rejects new local-model quotes when actual
thermal throttling is observed and uses observed service latency/queue depth only when samples exist.
Already-paid delivery/recovery remains available. Temperature never changes price.

**MEASURED throughput and calibration:** `python tools/measure_throughput.py` drives the pinned local
model over 30 sequential calls, pairing each with a hardware sample, and writes raw samples and a
digest-bound calibration under `bench/results/features/`. Result on the RTX 3050 laptop GPU with
Qwen2.5-1.5B Q4_K_M: **124.8 tokens/s median** (90% interval 124.2–125.6, range 116.5–127.6 over 59–70 °C).
Pricing rule: `multiplier = clamp(baseline_tps / median(recent live decode tps), 1, 1.25)`, applied only
when the calibration verifies (digest, model hash, seven-day expiry), at least five live decode samples
exist and the result stays under the 0.05 USD ceiling. Seller deliveries record the server-reported
decode rate. Missing, expired, altered or wrong-model calibration reverts to the fixed base price.
[Samples](../bench/results/features/throughput-samples.json),
[calibration](../bench/results/features/capacity-calibration.json).

**Limits:** one model, one machine, sequential single-slot load; the 1.25 cap is a policy bound, not a
fitted economic optimum, and no buyer has paid a calibrated price. Concurrent-load behavior is
unmeasured. Recalibrate after any model, driver or hardware change.

## Commands that move no money

PowerShell, macOS and Linux use the same commands:

```text
python tools/run_mock.py
python tools/features.py --controlled-fx --tap-probe --controlled-fault-proof --sample-gpu
python tools/measure_throughput.py --runs 30   # local model only; no payment
python tools/card_rail.py doctor
python tools/fault_proof.py verify --input bench/results/faults/metal-fault.json
```

Doctor needs locally configured sandbox credentials. `--refresh-fx` is an optional
network quote-only observation, not a conversion. Never reuse consumed approvals
for any new purchase, deposit, withdrawal, card or FX transaction.

## Verification and remaining gates

**MEASURED:** the full Python and Node suites pass locally (see [validation](VALIDATION.md) for the current counts). Browser checks pass
at desktop/390px widths, including SSE, session/Host/Origin controls, missing-key
FX refusal, both simulated billing policies, kill/resume and reconciliation.
See [validation](VALIDATION.md) and the [evidence index](EVIDENCE_INDEX.md).

M3 useful synthetic review drafting and one integrated customer sandbox proof are now measured.
M4 remains incomplete after clearing refusals and the credit-cap stop. Sandbox issuing creation
and controls are verified. Visa credentials/trust, merchant enablement, independent final settlement and signed-in portal
submission remain gates. A captioned local recording is available in the release package. The implementation does not turn those
missing observations into completion claims.
