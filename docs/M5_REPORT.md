# M5 — financial story

## Changed

The run stores an immutable failed-call billing policy. In the SIMULATED
three-job scenario, `CUSTOMER_PAYS` bills failed attempts while
`MERCHANT_ABSORBS` excludes their provider and internal check costs from customer
capture. Provider expenses remain recorded in both cases. Hold/float reservations
remain conservative and unchanged; uncertain payments still block closure.
The dashboard exposes customer capture, provider spend, internal check charges,
absorbed failures and modeled margin before unpriced operating expenses.

## Evidence and tests

[Reproducible story](../bench/results/m5/financial-story.json), generated with:

```text
python tools/prove_m5.py
```

Both runs use **SIMULATED** holds of 2.50 USD and initial float of 1.50 USD.
Customer capture is 1.454 USD for customer-pays and 1.244 USD for merchant-absorbs;
the provider expenses are preserved. No external transaction occurs.
Two Python regressions cover policy immutability, idempotent settlement and
uncertain-payment refusal. Browser checks exercise both policies through SSE.

Audit heads, also saved in the JSON:

- Customer pays: `98a2822cf8769a81ba59b2642cd2bea7a657858b8f219ccf0e15fba519cb`.
- Merchant absorbs: `6c0a0008a19e31c044bcc1f72bc6f4e64ad1ad1d99340990532e356b5b9eebbb`.

## Claims allowed and excluded

Allowed: a coherent, auditable simulated billing comparison alongside separate
real Airwallex FX and Metal purchase records. Cash accounts are distinct; credit
acknowledgements are not refunds. The real M1 hosted capture is independent of
this simulation. Its issuer release timing remains unmeasured.

Excluded: an all-live three-customer settlement loop, actual hold increases,
automatic credit/refund settlement, a fiat-token bridge or zero operating costs.
Merchant absorption is not enabled for the TESTNET customer contract.

## Human gates

No permission is needed to replay this simulation. Further live operations require
fresh written caps. Native acquiring, issuing and Visa credentials remain separate
account entitlements; current simulation does not establish any of them.
