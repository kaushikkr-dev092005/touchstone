# Sandbox merchant service

The [public sandbox service](https://touchstone-sandbox-merchant.sublimeoak1.chatgpt.site)
has active Airwallex merchant configuration and 100 uploaded synthetic products.
[Onboarding proof](../bench/results/completion-20261110/merchant-onboarding.json)
records exactly one onboarding POST and one catalog upsert, with zero failed rows.
[Real gateway checks](../bench/results/completion-20261110/merchant-oauth.json)
complete guest PKCE and MCP discovery, reject missing/tampered tokens, accept the
signed guest token and perform a read-only product lookup. No checkout/payment
mutation or inference runs. The earlier
[private-deployment checks](../bench/results/completion-20261110/merchant-service.json)
retain their original private-access scope. Public access was explicitly approved
after those checks.

The hosting edge intermittently returned a sign-in page for the generic `/health`
diagnostic while required OAuth/catalog endpoints and a fresh anonymous browser
worked. `/api/merchant-health` provides the application-specific diagnostic; check
the latest hosted evidence before treating availability as verified. `oauth_ready`
means a signing key is loaded; the separate gateway proof establishes actual OAuth.

`apps/merchant/worker.mjs` is a dependency-free Worker implementing the
[Airwallex developer-lab merchant contract](https://airwallexdev.com/agentic-commerce/).
It exposes 100 synthetic products, signed checkout quotes, OAuth discovery,
public RSA signing keys, explicit guest consent, S256 PKCE and single-use codes.
These are sandbox practice documents. The service does not invoke a model,
submit a payment, collect card data or mark quotes paid. Actual paid fulfillment
and payment-webhook reconciliation are not enabled.

Run locally with the project's configured Node executable:

```text
node apps/merchant/local.mjs
python -m unittest tests.test_merchant_service -v
```

First startup creates `data/merchant-service/config.json` and `state.sqlite`.
Both are private and ignored by Git. Configuration contains the checkout HMAC
secret and RSA private signing key; never paste or publish either. Local HTTP is
limited to loopback. The hosted origin must use HTTPS. Set `OAUTH_RESOURCE` only
to the exact sandbox ACP MCP URL returned by Airwallex merchant onboarding.
Until then authorization and token issuance refuse requests. Remote OAuth
redirects require an explicit `OAUTH_REDIRECT_URIS` allowlist; ephemeral loopback
callbacks are supported. No saved-card shopper identity is asserted.

Requests have a 32 KiB body limit. Persistent registration and quote storage are
capped at 1,000 records each; live consents at 500 and codes at 1,000, with expired
authorization records removed. Capacity exhaustion refuses new writes rather
than dropping previous quotes. HMAC requests must be within five minutes of
server time, and exact replay returns the same quote. No server-side credentials
for Airwallex, Metal or Claude belong in this service.

The existing Sites project is recorded in `.openai/hosting.json`, with only a
`DB` binding. `python tools/build_merchant.py --commit <full-sha>` packages the
Worker and hosting metadata directly from that Git commit. The same source must
be pushed to the site's configured repository before saving and deploying its
archive. Runtime secrets are set through Sites environment configuration.
The site starts private; Airwallex's anonymous callbacks require public access
before merchant onboarding can be tested. A saved URL alone does not establish
merchant enablement, paid checkout or Visa approval.
