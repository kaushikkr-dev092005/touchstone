# Demo script, target 4 minutes 45 seconds

Lead with the **real paid GPU failure**, then label the three-job policy run as a simulator. The opening evidence card shows one $0.01 USDZ Metal call: the local GPU returned 1,250 cents for a 2,000-cent total, the verifier rejected it, and buyer/provider replays did not pay again. The $0.01 is an unbilled operator probe outlay; no customer hold or capture exists. The remaining demo is a financial-control regression simulator, not an all-real-provider comparison.

| Time | Show | Explain |
|---|---|---|
| 0:00–0:45 | First card: real paid GPU evidence and probe P&L | “The model answered 1,250 cents where the source totals 2,000. It was paid, rejected and not retried for a second charge. Provider outlay was $0.01; no customer hold or capture was made.” Show the preconfirmed receipt status. |
| 0:45–1:15 | Planning evidence | “For bounded tasks, buy no model: deterministic tools solve these cases. Defer unfamiliar sources to review. When a paid model is justified, check the answer.” This is a synthetic workload result, not general business accuracy. |
| 1:15–1:40 | Mode badges and simulated stress test | Explicitly introduce the following flow as simulation. Three simulated holds total $2.50 against $1.50 operator float. |
| 1:40–2:30 | Policy table, quotes, chaos and ledger | Explain that the three-policy table is simulator-only; show price/latency/quality changes and that rejected simulated calls remain charged. Do not call these real-provider cost measurements. |
| 2:30–3:10 | Policy pause and mandate approval | Show a policy pause. A human can approve a new **simulated** mandate version from the existing run float, then click Resume. This does not increment an Airwallex hold or add real funds. |
| 3:10–3:35 | Close and reconcile | Simulated capture/release remains separate from the real $0.01 testnet provider outlay; do not imply revenue was collected for the probe. |
| 3:35–4:10 | Noisy-check chart | One-row noisy spot-check false-accepts 79% on injected offsetting errors; exact source arithmetic rejects all 20. Synthetic fault injection, not population calibration. |
| 4:10–4:45 | Airwallex state and remaining gates | Authentication and balance/account reads pass. `AIRWALLEX_ACCOUNT_ID` is unset; FX and hosted checkout have not been tested. The planned next live finance action is a small sandbox FX conversion plus wallet-history reconciliation after account context and write scope are configured. No new live Metal engine run is claimed. |

Commands for rehearsal:

```powershell
python -m touchstone benchmark
python -m touchstone procurement-evidence
python -m unittest discover -s tests -p test_controls.py -v
python -m touchstone serve --data-dir data/rehearsal
```

A live three-policy comparison still requires multiple qualified real model endpoints, a configured provider URL, funded testnet wallets and an operator-approved aggregate cap. Clearing payments and withdrawals can take longer than the video window. Record finality separately and never claim a queued withdrawal was returned immediately.

Feature freeze is scheduled for 11 November, recording for 12 November, and submission for 13 November. These are planned milestones, not actions completed by this code change. The integrated engine, live-provider chaos and kill/restart path still need a configured provider, testnet funds and an operator-authorized budget before they can be demonstrated on the real rail.

Do not promise “only pays for quality”, production banking readiness or zero semantic errors. The supported claim is narrower: tools avoid some unnecessary inference; one real paid model result was wrong and rejected; the simulator exercises budget, recovery and approval controls.
