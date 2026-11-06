# Procurement extensions — 6 November 2026

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

## 2. CardRail and controlled signed intent

`python tools/card_rail.py --help` exposes a sandbox-only issuing doctor, guarded
create and read-only reconciliation. Controls bind a single-use virtual card to
an existing cardholder, currency, whole-cent transaction/all-time cap, one-hour
expiry and blocked cash withdrawal. A durable request ID precedes dispatch;
uncertain creation never automatically retries. No PAN/CVC endpoint is used.
Issuing a card is not a merchant payment: `pay` refuses without a separately
verified merchant adapter. The existing Metal path remains independent.

**BLOCKED:** the saved real issuing read returned HTTP 401. No card was created.
An operator must enable issuing access and separately approve a stated cap.
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

## 4. Measured GPU capacity

`GET /api/telemetry` and SSE expose timestamped NVIDIA driver observations: GPU
identity, temperature, utilization, VRAM, power, clocks and actual thermal-slowdown
flags. Samples cache for five seconds; failed samples become BLOCKED. These are
local measurements, not remote hardware attestations.
[Saved sample](../bench/results/features/telemetry.json).

The seller quotes a compact telemetry reference, rejects new local-model quotes
when actual thermal throttling is observed and uses observed service latency/
queue depth only when samples exist. Already-paid delivery/recovery remains
available. Temperature alone never changes price. Tokens/second is UNMEASURED
because the current model endpoint exposes no throughput metrics.

**BLOCKED calibration:** no fitted capacity coefficients or measured thermal
throughput experiment exist. Capacity price markups are disabled; new seller
quotes use the fixed base price. No invented temperature progression or economic
pricing claim is presented.

## Commands that move no money

PowerShell, macOS and Linux use the same commands:

```text
python tools/run_mock.py
python tools/features.py --controlled-fx --tap-probe --controlled-fault-proof --sample-gpu
python tools/card_rail.py doctor
python tools/fault_proof.py verify --input bench/results/faults/metal-fault.json
```

Doctor needs locally configured sandbox credentials. `--refresh-fx` is an optional
network quote-only observation, not a conversion. Never reuse consumed approvals
for any new purchase, deposit, withdrawal, card or FX transaction.

## Verification and remaining gates

**MEASURED:** 247 Python tests and 47 Node tests pass locally. Browser checks pass
at desktop/390px widths, including SSE, session/Host/Origin controls, missing-key
FX refusal, both simulated billing policies, kill/resume and reconciliation.
See [validation](VALIDATION.md) and the [evidence index](EVIDENCE_INDEX.md).

M3 useful paid inference, M4 live comparison, calibrated capacity pricing, enabled
issuing, Visa credentials/trust, final settlement, manual portal/video/submission
and new spending approvals remain gates. The implementation does not turn those
missing observations into completion claims.
