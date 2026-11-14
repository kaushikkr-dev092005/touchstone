# Operational judge demonstration

Use the [deployment guide](LIVE_DEPLOYMENT.md) to initialize the local operator
yourself and start port 8089. No keys, model download, bank credentials or spend
are needed. The existing simulator/evidence site on 8088 remains a separate view.

## A — Actual backend task

1. Open `/control-room` on the operator origin and sign in.
2. Keep arithmetic and `tools-only`. Source: 1250 + 900 cents, minus 150 cents.
3. Select **Create backend job**. It appears as QUEUED in the persistent ledger.
4. Select **Start zero-charge processing**. The actual local tool returns 2000;
   the source verifier passes. The backend records COMPLETED and real audit events.
5. Inspect output, verifier, distinct zero USD/USDZ/API charges and event IDs.
6. Reload; restart the backend; sign in if needed. The same job remains completed.

This is actual source processing and persistence, not a simulated inference call.
No receipt is fabricated because no payment occurred.

## B — Provider readiness without buying

Choose `real-touchstone`, a supported external-only task, and proposed nonzero
integer micro-USDZ limits. Configure approved provider origins offline first.
**Get actual provider quotes** uses the SDK's genuine x402 challenge checks.
Stopped providers report BLOCKED; no configured origin reports an explicit reason.
A received quote still reports qualification and approval requirements. It cannot
be dispatched by this service. No budget field allocates funds or grants spending.

The current saved qualification is stale and paid sellers are off; do not narrate
this scenario as a successful paid run. The current router is fixed local-first
escalation, not a learned adaptive policy.

## C — Cryptographic approval, controlled purchase

```text
python tools/demo_signed_mandates.py --output tmp/signed-demo.json
python tools/check_signed_mandates.py
```

Both use actual EIP-712/viem verification and separate ephemeral test keys, with
MOCK payment rails. Unsigned blocks, exact terms authorize one MOCK dispatch,
changed terms block, and the original record remains unchanged. For an actual
human-controlled browser wallet use the private dashboard and follow
[Signed Mandates](SIGNED_MANDATES.md). Test-generated keys are not human approval.

## D — Real sandbox/testnet transaction

Not included in this demonstration. Follow the private financial runbooks only
after fresh explicit transaction and fee caps, qualified provider, balances,
actual quote and independent human signature are verified. Existing historical
approvals are consumed. The remote operator service has no financial write route.

## E — Persistence, failure and recovery

```text
python -m unittest discover -s tests -p test_operator_workspace.py
python -m unittest discover -s tests -p test_procurement_approval.py
python tools/check_operator_workspace.py
```

These check actual local auth/jobs/events/restart, concurrent idempotency, and
controlled financial crash/replay invariants. The existing measured Metal
process-death recovery proof stays under `bench/results/m2/`; it is not a new
transaction made by this demo.

Open the original dashboard's Evidence/Transactions views for historical capture,
fault acknowledgement, qualification and the completed policy comparison. Keep
their measured/simulated/review labels visible. A signed seller acknowledgement
does not imply a refund, and extraction success never authorizes invoice payment.
