# Airwallex support request — draft, not sent

**Latest outcome:** the approved sandbox Agentic Commerce onboarding succeeded.
Configuration is active; 100 synthetic products were added, with zero row failures.
Guest OAuth/PKCE and real MCP gateway discovery pass. No merchant payment or model
call was made. Merchant enablement requests below are superseded; this draft was
never sent. Visa approval remains pending with Visa, according to the operator.

**10 November current status:** hosted customer checkout/capture and capped sandbox
issuing creation now pass. The original two issuing creation approvals are consumed.
Agentic Commerce merchant config still returned `MERCHANT_CONFIG_NOT_FOUND` at the
last read. A separate synthetic merchant checkout/OAuth service is implemented and
deployed on private Sites hosting; public callback access is required before
onboarding. Please confirm merchant-side enablement if the documented onboarding
endpoint remains unavailable after those endpoints are public. Visa application is
submitted and approval pending, as reported by the operator. No new support message
or Visa application has been sent. The dated draft below retains historical facts.

**5 November update (draft remains unsent):** current scoped-key reads, one sandbox
FX conversion, and a separately approved hosted card authorization/capture pass.
The historical native PaymentIntent error below remains relevant only to native
checkout entitlement; hosted checkout is no longer blocked. Never include credentials
or hosted session URLs in a support message.

To: devhelp@airwallex.com

Subject: Agentic Banking Hackathon Kit 12 — sandbox PaymentIntent configuration and tooling eligibility

Hello Airwallex developer support,

I am building Touchstone for Kit 12, Inference Sourcing Agent. The public repository is https://github.com/kaushikkr-dev092005/touchstone. Our working submission deadline is 13 November 2026 at 18:29 UTC.

Historical sandbox evidence shows authentication, balance reads and Global Account reads succeeded. `POST /api/v1/pa/payment_intents/create` returned HTTP 400 with code `configuration_error` and this redacted message:

> Invalid request against merchant configuration. Please contact your account manager.

No authorization or capture completed. A later retry of an older request ID returned `duplicate_request`; an order lookup found no matching PaymentIntent at that time. We have retained the unresolved operation locally and will not resend a consumed request ID or treat an empty list alone as proof that no object exists.

Could you confirm:

1. Which sandbox merchant capability/configuration is needed for PaymentIntent create and uncaptured authorization? Is native API checkout/PCI enablement required for this account, and can it be enabled for the hackathon?
2. Whether hosted Checkout Sessions can be enabled as an alternative, including the required scopes and supported API version. We implemented uncaptured hosted checkout against version `2026-05-29`, but have not executed it.
3. Whether a `configuration_error` consumes the create request ID without creating an object, and how to obtain authoritative confirmation for the older `duplicate_request` operation. We can supply the account/order/request identifiers through your private support channel; please provide a case reference and explicit outcome before we retire that scope.
4. Whether sandbox Developer MCP or the Airwallex CLI qualifies as “Airwallex tooling” for the hackathon. Our financial adapter currently uses sandbox REST; we are not connected to production AgentOS.

Update, 5 November: a separate, explicitly approved sandbox FX conversion has now
settled (1.00 USD to 0.89 EUR), with both wallet-history sides reconciled. Scoped
authentication and Checkout Session reads now pass after the operator updated
permissions. We have not executed a current-account card authorization/capture.
The native PaymentIntent error described above is historical; please confirm the
current account's supported checkout capabilities through a private channel.

Evidence: `docs/LIVE_PROOF.md`, `bench/results/airwallex-hold-proof.json`, and `docs/M1_REPORT.md` in the public repository. This draft contains no credentials, tokens, wallet material or raw account identifiers.

Thank you.
## Current additional access request, 10 November 2026

Resolved, 10 November: the operator enabled Issuing / Cards, Cardholders and
Config / Read for the selected account. A fresh login now passes those three
read probes and the balance read. The earlier HTTP 401 was an issuing-permission
denial while account authentication/balance access worked. No card was created
and no card transaction was sent.

Please identify the minimum issuing write scopes, cardholder setup, account context and permissions
needed for capped virtual-card creation and transaction simulation. Return no
PAN, CVC, API keys or other sensitive card details in the support response.

Visa agent identity/trust and an independently verified merchant settlement flow
are separate onboarding requirements. Please identify the supported sandbox
process and credentials for those integrations; a local HTTP signature does not
establish Visa approval or payment settlement.

This is an unsent draft. No request has been sent to support by this agent.
