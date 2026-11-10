# Issuing, merchant and Visa completion

Read-only account check, 10 November 2026: authentication and Issuing Cards,
Cardholders and Config reads pass. The account returned no cards and no
cardholders, with `has_more=false` on both lists. The merchant configuration
endpoint returned HTTP 404 `MERCHANT_CONFIG_NOT_FOUND`. This is a missing merchant
configuration, not the earlier issuing HTTP 401. Card creation and Visa approval
have not been demonstrated.

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

The account owner must enable **Issuing / Cards / Write** on the selected scoped
sandbox key. Because this account has no cardholder, either provision an approved
individual test cardholder through the account's supported flow or enable
**Cardholders / Write** for a separately reviewed creation. The existing adapter
creates personalized cards, so a delegate cardholder is insufficient. Keep Config
at Read; creating a card does not require Config / Write.
[Sandbox](https://sandbox.airwallex.com/),
[scope reference](https://www.airwallex.com/docs/developer-tools/api/api-key-scopes),
[cardholder types](https://www.airwallex.com/docs/issuing/get-started/create-cardholders).

Airwallex must confirm the account's card program, card creation limit and any
required issuing enablement. Individual sandbox cardholder approval may need an
Airwallex action. Use the account's secure setup flow for identity and consent
details; no identity or consent is inferred from a repository username.
[Issuing checklist](https://www.airwallex.com/docs/issuing/test-and-go-live/integration-checklist).

Before a write, prepare a fresh immutable scope with the approved cardholder,
requesting user's legal name, currency, whole-cent cap, expiry within an hour and
confirmed creation fees. The consumed checkout/Metal approvals do not authorize
this new issuing scope. Card issuance alone does not prove a merchant charge or
settlement. No card creation or merchant charge has been sent during this check.

## Merchant enablement

The current account has no Agentic Commerce merchant config. Airwallex's builder
guide routes merchant enablement through `devhelp@airwallex.com`. The documented
onboarding contract also needs public HTTPS checkout and OAuth endpoints, a checkout
HMAC secret and an image-host allowlist. A working hosted customer checkout does
not establish this separate merchant integration. No onboarding POST was sent.
[Builder guide](https://airwallexdev.com/guide),
[merchant contract](https://airwallexdev.com/agentic-commerce/).

Prepared request for the account owner to send through their existing Airwallex
support channel:

> Subject: Touchstone sandbox issuing and merchant enablement
>
> We are building Touchstone for the Airwallex hackathon:
> https://github.com/kaushikkr-dev092005/touchstone.
> Issuing card, cardholder and configuration reads pass. The account currently has
> no cardholder or card; Agentic Commerce config returns MERCHANT_CONFIG_NOT_FOUND.
> Please confirm the allowed commercial virtual-card program, card creation limit,
> test cardholder approval requirements and any sandbox creation fees. Please also
> provide merchant-side Agentic Commerce enablement and onboarding instructions.
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

This is an unsent draft. No Visa registration has been submitted by this project.
Further hosted inference remains stopped: conservative exposure is $2.919117
against the user's $3 total ceiling. Account setup must not trigger model calls.
