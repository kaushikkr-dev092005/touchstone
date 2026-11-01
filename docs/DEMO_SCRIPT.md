# Demo script, target 4 minutes 45 seconds

The financial stress scenario is a **local simulator**. Keep its mode badges visible. A separate funded Metal GPU purchase and original paid delivery replay have run; show their real-evidence panel with its rejected answer and preconfirmed receipt. Airwallex authentication/balance/account reads pass, but merchant configuration blocks customer authorization/capture. The account ID is still unset, so Checkout Sessions and FX have not been probed.

| Time | Show | Explain |
|---|---|---|
| 0:00–0:25 | Dashboard and mode badges | “An agent buying intelligence needs a spending mandate and evidence of what it got. This local prototype simulates the external services.” |
| 0:25–1:00 | Three holds and $1.50 operator float | “Customers authorized $2.50, but authorization is not liquidity. We cannot allocate money we do not have.” |
| 1:00–1:45 | Start demo, route reasons, quote board and ledger | Show price/latency changes and a rejected call. Every failed paid attempt remains in cost. |
| 1:45–2:20 | Quality degradation and prompt expansion in decision stream | Show a reroute or escalation; explain that higher quality costs more and the hold still wins. |
| 2:20–2:50 | Policy pause and float allocation | Show which constraint blocks the next purchase. No silent authorization increase. |
| 2:50–3:20 | Close jobs, capture actual simulated spend, release rest | Explain customer capture and provider payments as different accounting entries. |
| 3:20–3:55 | Real testnet evidence panel | Show the USD 0.01 inference purchase, signed preconfirmed receipt and identical cached/provider receipt replay. The answer was wrong and rejected; its charge remains recorded. State that this was a protocol probe. |
| 3:55–4:30 | Planning, measured models and invoice-check chart | Show local resolution versus review, then the fault-injection table: the one-row noisy checker false-accepts 79% on offsetting errors; exact source arithmetic rejects all 20 injected cases. Explain this is synthetic, not a population estimate. |
| 4:30–4:45 | Banked job and Airwallex status | Authentication and account reads pass; merchant configuration blocks PaymentIntent creation. Account context is missing, so Checkout Sessions/FX are untested. No actual customer hold/capture or new Metal engine run is claimed. The 0.09 testnet USDZ return is confirmed; the old paid receipt remains preconfirmed. |

Commands for rehearsal:

```powershell
python -m touchstone benchmark
python -m touchstone procurement-evidence
python -m unittest discover -s tests -p test_controls.py -v
python -m touchstone serve --data-dir data/rehearsal
```

A live version should use tens of requests with one wallet per job. Clearing payments and withdrawals can take longer than the video window. Record finality separately and never claim a queued withdrawal was returned immediately.

Feature freeze is scheduled for 11 November, recording for 12 November, and submission for 13 November. These are planned milestones, not actions completed by this code change. The integrated engine, live-provider chaos and kill/restart path still need a configured provider, testnet funds and an operator-authorized budget before they can be demonstrated on the real rail.

Do not promise “only pays for quality”, production banking readiness or zero semantic errors. The claim supported by the prototype is bounded purchases, explicit verification limits, charged-failure accounting and recovery evidence.
