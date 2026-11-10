# Issuing, merchant and Visa completion

**Current outcome:** the approved plan created one READY synthetic delegate and
one ACTIVE non-personalized sandbox virtual card. Its USD 0.01 per-transaction and
all-time limits, USD-only currency, single-use policy, cash-withdrawal block and
expiry were verified through read-only reconciliation. Exactly the original two
creation operations were observed. No merchant payment, transfer, PAN/CVC retrieval
or model call occurred. [Verified proof](../bench/results/completion-20261110/issuing-proof.json).

The server truncated the approved expiry to milliseconds, slightly earlier than
requested. The verifier accepts only the exact expiry or that earlier millisecond
truncation, never an extension. The approved writing code was not re-executed; the
correction reconciled the original card with GET calls. Both creation approvals are
consumed. The authorization window ends at `2026-11-10T19:10:10.454Z`; this is not a
card cancellation or a merchant payment.

Merchant Agentic Commerce config now reports **active**. Approved plan
`2ce5ecc382199fff` made the service public, sent exactly one onboarding POST and
one catalog upsert: 100 added, zero updated or failed. Guest PKCE completed through
the real Airwallex MCP gateway; missing and tampered tokens were rejected, a signed
guest token was accepted and eight tools were listed. A read-only catalog lookup
also succeeded. No checkout/payment tool or model was invoked.
[Configuration proof](../bench/results/completion-20261110/merchant-onboarding.json),
[OAuth and catalog proof](../bench/results/completion-20261110/merchant-oauth.json),
[service deployment](MERCHANT_SERVICE.md).
Visa application is submitted and approval is pending, as reported by the operator.
No Visa approval is claimed.

## Earlier read-only diagnosis

Read-only account check, 10 November 2026: authentication and Issuing Cards,
Cardholders and Config reads pass. The account returned no cards and no
cardholders, with `has_more=false` on both lists. The merchant configuration
endpoint returned HTTP 404 `MERCHANT_CONFIG_NOT_FOUND`. This is a missing merchant
configuration, not the earlier issuing HTTP 401. Card creation and Visa approval
have not been demonstrated.

The operator subsequently confirmed enabling Cards and Cardholders Write and
reported that the Visa application is submitted with approval pending. These are
user reports. Issuing writes were subsequently verified above; Visa approval still
needs independent evidence.
[Completed capped issuing proof](ISSUING_PROOF_PLAN.md).

[Measured account check](../bench/results/completion-20261110/external-access.json).
Repeat without spending or starting the GPU:

```text
python tools/check_external_access.py
```

Only authentication and GET requests reach Airwallex. The tool returns aggregate
counts and permission/error codes; it omits raw cardholder and merchant config data.
Its Visa status records the absence of verified onboarding evidence, not a query
of Visa's private registry.

## Card creation

The adapter now uses Airwallex's documented `card_id` and `card_status` fields,
with API version `2024-03-31`. Read-back binds the card to the original request ID,
account, cardholder, personalized commercial program, currency, single-use limit,
cash-withdrawal block and expiry. Recovery retrieves individual card details because
the list response omits the required control and attribution fields. An uncertain
create cannot send another create request.
[API contract](https://www.airwallex.com/docs/api/issuing/cards/create),
[list limitations](https://www.airwallex.com/docs/issuing/get-started/create-cards).

The account owner reports **Issuing / Cards / Write** and **Cardholders / Write**
enabled on the selected scoped sandbox key. The separately approved plan then created
one READY delegate and one controlled card. Personalized cards require an individual
cardholder. The explicit `--non-personalized` path also supports a READY delegate. Keep Config
at Read; creating a card does not require Config / Write.
[Sandbox](https://sandbox.airwallex.com/),
[scope reference](https://www.airwallex.com/docs/developer-tools/api/api-key-scopes),
[cardholder types](https://www.airwallex.com/docs/issuing/get-started/create-cardholders).

The saved proof verifies this account's non-personalized commercial sandbox program
for the approved card. It does not authorize another card. Individual cardholder approval may need an
Airwallex action. Use the account's secure setup flow for identity and consent
details; no identity or consent is inferred from a repository username.
[Issuing checklist](https://www.airwallex.com/docs/issuing/test-and-go-live/integration-checklist).

Before a write, prepare a fresh immutable scope with the approved cardholder,
requesting user's legal name, currency, whole-cent cap, expiry within an hour and
confirmed creation fees. The consumed checkout/Metal approvals do not authorize
this new issuing scope. Card issuance alone does not prove a merchant charge or
settlement. No card creation or merchant charge has been sent during this check.

## Merchant enablement — completed sandbox configuration

The approved configuration now uses public HTTPS checkout and OAuth endpoints,
a separate checkout HMAC secret and an image-host allowlist. Its original POST and
100-product upload are consumed. The local journal forbids repeating either write
after an uncertain result and refuses account/key changes. `python tools/onboard_merchant.py status`
only reads the account and journal. Guest OAuth verifies issuer/audience, PKCE,
consent, JWT signing and gateway acceptance; no real shopper identity is asserted.
This setup is separate from the existing hosted customer checkout proof and does
not establish paid merchant fulfillment or independent settlement.
[Builder guide](https://airwallexdev.com/guide),
[merchant contract](https://airwallexdev.com/agentic-commerce/).

Earlier prepared support request, superseded by the successful onboarding above:

> Subject: Touchstone sandbox Agentic Commerce merchant enablement
>
> We are building Touchstone for the Airwallex hackathon:
> https://github.com/kaushikkr-dev092005/touchstone.
> Sandbox issuing creation and control read-back are verified. Agentic Commerce
> config returns MERCHANT_CONFIG_NOT_FOUND at the last read. We have implemented
> signed checkout quotes, synthetic products and guest OAuth/PKCE endpoints.
> Please confirm merchant-side enablement and the supported onboarding process.
> We will identify the sandbox account through your secure support flow.
>
> Our existing customer checkout proof is sandbox-only. This request does not
> authorize purchases, additional funding or a production account change.

This is an unsent draft. There is no support ticket or activation confirmation.

## Visa agent trust

The local RFC 9421 Ed25519 proof verifies an intent and refuses replay using a
controlled key. It does not establish a Visa-approved agent identity. Visa's TAP
documentation describes recognizing approved agents; creating a local key or
running the public sample cannot confer that approval.
[TAP documentation](https://developer.visa.com/docs/trusted-agent-protocol),
[local evidence](../bench/results/features/tap-probe.json).

The operator must obtain Visa's agent-onboarding instructions and approval through
the official developer/partner channel, then configure the issued registration and
trust material locally. Keep credentials and private keys out of chat and Git.
Use the actual supplied endpoint, key identifiers and supported profile; no registry
record, approval ID or application status is fabricated. Visa Intelligent Commerce
credential retrieval has additional onboarding requirements if that scope is later
chosen. TAP recognition alone does not prove VIC credential access or payment.
[VIC prerequisites](https://developer.visa.com/docs/visa-intelligent-commerce/docs-getting-started).

Prepared request for the operator's Visa/hackathon partner channel:

> Subject: Touchstone Trusted Agent Protocol sandbox onboarding
>
> We have a local signed-intent and replay-refusal implementation for Touchstone:
> https://github.com/kaushikkr-dev092005/touchstone.
> Please provide the agent registration/approval process, sandbox trust-key
> onboarding instructions, supported TAP profile and merchant verification test.
> We do not yet claim Visa approval, VIC access or a real Visa merchant payment.

This is an unsent draft. The operator reports a submitted application awaiting
approval; this project has not submitted another application or verified approval.
Further hosted inference remains stopped: conservative exposure is $2.919117
against the user's $3 total ceiling. Account setup must not trigger model calls.
