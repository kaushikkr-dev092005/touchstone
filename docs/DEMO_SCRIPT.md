# Demo script, target 4 minutes 45 seconds

The financial stress scenario is a **local simulator**. Keep its mode badges visible. A separate funded Metal GPU purchase and original paid delivery replay have now run; show their real-evidence panel with its rejected answer and preconfirmed receipt. Airwallex authentication/reads pass, but merchant configuration blocks customer authorization/capture.

| Time | Show | Explain |
|---|---|---|
| 0:00–0:25 | Dashboard and mode badges | “An agent buying intelligence needs a spending mandate and evidence of what it got. This local prototype simulates the external services.” |
| 0:25–1:00 | Three holds and $1.50 operator float | “Customers authorized $2.50, but authorization is not liquidity. We cannot allocate money we do not have.” |
| 1:00–1:45 | Start demo, route reasons, quote board and ledger | Show price/latency changes and a rejected call. Every failed paid attempt remains in cost. |
| 1:45–2:20 | Quality degradation and prompt expansion in decision stream | Show a reroute or escalation; explain that higher quality costs more and the hold still wins. |
| 2:20–2:50 | Policy pause and float allocation | Show which constraint blocks the next purchase. No silent authorization increase. |
| 2:50–3:20 | Close jobs, capture actual simulated spend, release rest | Explain customer capture and provider payments as different accounting entries. |
| 3:20–3:55 | Real testnet evidence panel | Show the USD 0.01 inference purchase, signed preconfirmed receipt and identical cached/provider receipt replay. The answer was wrong and rejected; its charge remains recorded. State that this was a protocol probe. |
| 3:55–4:30 | Planning preview and measured model evidence | Select a calculation, then a foreign-currency invoice. Show local resolution versus review with zero purchases. Explain that 1,000 generated tasks need no model, both measured models fail eligibility, and live paid inference still needs proof. |
| 4:30–4:45 | Banked job and Airwallex status | Authentication and account reads pass; creation is blocked by merchant configuration. The integrated workflow exists and passes fixture tests; actual customer hold/capture remains open. The 0.09 testnet USDZ return is confirmed, while the paid receipt remains preconfirmed. |

Commands for rehearsal:

```powershell
python -m touchstone benchmark
python -m touchstone procurement-evidence
python -m unittest discover -s tests -p test_controls.py -v
python -m touchstone serve --data-dir data/rehearsal
```

A live version should use tens of requests with one wallet per job. Clearing payments and withdrawals can take longer than the video window. Record finality separately and never claim a queued withdrawal was returned immediately.

Do not promise “only pays for quality”, production banking readiness or zero semantic errors. The claim supported by the prototype is bounded purchases, explicit verification limits, charged-failure accounting and recovery evidence.
