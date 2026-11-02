# Airwallex support request — draft, not sent

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

Separately, we are preparing one capped sandbox FX conversion plus read-back of both wallet-history entries. No FX quote or conversion has been executed. We will verify account context and scope access before requesting the operator's written spend approval.

Evidence: `docs/LIVE_PROOF.md`, `bench/results/airwallex-hold-proof.json`, and `docs/M1_REPORT.md` in the public repository. This draft contains no credentials, tokens, wallet material or raw account identifiers.

Thank you.
