# Sandbox issuing proof awaiting approval

Plan `047d1243edb1eefc9098de7cb43358dceb9a5cfc0bbe973cb52760db6c2d8760`
is prepared for the configured sandbox account. It is not an executed proof.
[Exact terms and source hashes](../bench/results/completion-20261110/issuing-plan.json).

It permits one synthetic DELEGATE cardholder with reserved `example.com` email and
one non-personalized commercial virtual card. The synthetic requester name is
Alex Example; no real person's date of birth, identification document or consent
assertion is submitted. The card has a USD 0.01 per-transaction and all-time limit,
USD-only spending, a single-use control and blocked cash withdrawals. Its fixed
expiry is set once, thirty minutes after approval execution begins. Expiry limits
authorizations; it does not delete the card.

Merchant charges, funding transfers, production calls, card-number/CVC retrieval,
hosted inference and GPU startup are outside this approval. New cash permitted: $0.
The existing $3 total Claude ceiling remains unchanged. No automatic retry or
additional scope is permitted. The controller binds the account and financial
source hashes before any write. A changed source or expired original card window
stops execution instead of extending the approval.

Prepare/read status without creating anything:

```text
python tools/run_issuing_proof.py prepare
python tools/run_issuing_proof.py status
```

`prepare` overwrites the prepared public plan using current source hashes; do not
run it to replace an already approved plan. `status` only reads remote objects and
reconciles the local journal. Neither sends a business write. Exact approval is
required for `execute`; it is not part of the ordinary dashboard or demo launcher.

The durable journal is `data/issuing.sqlite` and is excluded from Git and releases.
Unknown creation outcomes require GET reconciliation and never resend creation.
Cardholder uniqueness and the original card request ID prevent adopting an
unrelated card. Pending delegate approval stops card creation. A successful report
will verify actual server controls and still report zero merchant payments and
Visa approval false.

The owner reports enabling Cards and Cardholders Write. Visa application is
submitted with approval pending, as reported by the operator. These reports are
separate from API write evidence or Visa approval. The merchant config read
returned HTTP 404 `MERCHANT_CONFIG_NOT_FOUND`; this issuing plan does not onboard a
merchant or claim Visa trust. [Current setup and support drafts](EXTERNAL_ACCESS.md).
