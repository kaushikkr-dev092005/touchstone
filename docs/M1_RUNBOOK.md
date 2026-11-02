# M1 operator runbook

Status: **BLOCKED for live execution**. The environment-only doctor found no Airwallex variables in the agent's process on 2 November. The user reports configuring them in a terminal; configuration in a different process is not inherited automatically. Set `AIRWALLEX_CLIENT_ID`, `AIRWALLEX_API_KEY` and `AIRWALLEX_ACCOUNT_ID` privately in the terminal running these commands. The new Airwallex commands read that environment and do not load ignored local configuration or wallet files.

Money movement requires **both** a written chat approval naming the currencies and aggregate cap, and `--execute`. These commands are prepared instructions, not evidence that they ran. No quote or conversion has been executed. Existing PaymentIntent acquiring remains externally blocked; the [support draft](AIRWALLEX_SUPPORT_REQUEST.md) is ready for the user to send.

## Read-only doctor

PowerShell:

```powershell
python -m touchstone airwallex-doctor --probe-reads --output bench/results/m1/airwallex-doctor.json
```

Bash:

```bash
python -m touchstone airwallex-doctor --probe-reads --output bench/results/m1/airwallex-doctor.json
```

This prints flags and results only. It checks account context, then reads balances, balance history and conversion lists. Conversion Write remains `UNVERIFIED`: successful reads cannot prove write permission. Required scope names follow [Airwallex's scope table](https://www.airwallex.com/docs/developer-tools/api/api-key-scopes); Conversion Write includes conversion reads, and Balances Read covers wallet balance/history.

## Proposed FX proof — approval required

Proposed written authorization: **one sandbox conversion selling at most USD 1.00 for EUR, aggregate sell cap USD 1.00; no Metal activity, customer holds/capture or card issuing.** Airwallex documents a USD 1 equivalent minimum per conversion ([API contract](https://www.airwallex.com/docs/api/transactional_fx/conversion)). This proposal is not approved yet. The EUR buy amount is determined by the actual quote.

After that approval and a passing doctor, create the non-settling quote and prepare the local job. This example uses a fresh scope/request ID; once dispatched, retain them for reconciliation. Never create a replacement ID to retry an uncertain conversion.

PowerShell:

```powershell
python -m touchstone airwallex-fx quote --sell-currency USD --buy-currency EUR --sell-amount 1.00 --output data/m1-fx-quote.json
python -m touchstone treasury-job prepare --scope m1-fx-20261102-001 --request-id m1-fx-20261102-001 --quote data/m1-fx-quote.json --customer-budget-currency USD --customer-budget-amount 1.00 --demo-usdz-per-unit 1
python -m touchstone treasury-job run --scope m1-fx-20261102-001
```

Bash:

```bash
python -m touchstone airwallex-fx quote --sell-currency USD --buy-currency EUR --sell-amount 1.00 --output data/m1-fx-quote.json
python -m touchstone treasury-job prepare --scope m1-fx-20261102-001 --request-id m1-fx-20261102-001 --quote data/m1-fx-quote.json --customer-budget-currency USD --customer-budget-amount 1.00 --demo-usdz-per-unit 1
python -m touchstone treasury-job run --scope m1-fx-20261102-001
```

The final command above is a local preview. Inspect the quote, immutable budget, currencies and expiry. `--demo-usdz-per-unit 1` means one **SIMULATED** USDZ accounting unit per EUR received; it is not a market rate, exchange service, token bridge or wallet funding. The customer budget is a SIMULATED mandate, not an Airwallex authorization.

The following command moves sandbox money. Run only after the written approval, within the quote's validity:

PowerShell:

```powershell
python -m touchstone treasury-job run --scope m1-fx-20261102-001 --sell-currency USD --max-sell-amount 1.00 --execute --output bench/results/m1/airwallex-fx-job.json
python -m touchstone airwallex-fx report --request-id m1-fx-20261102-001
python -m touchstone treasury-job reconcile --scope m1-fx-20261102-001 --output bench/results/m1/airwallex-fx-job.json
```

Bash:

```bash
python -m touchstone treasury-job run --scope m1-fx-20261102-001 --sell-currency USD --max-sell-amount 1.00 --execute --output bench/results/m1/airwallex-fx-job.json
python -m touchstone airwallex-fx report --request-id m1-fx-20261102-001
python -m touchstone treasury-job reconcile --scope m1-fx-20261102-001 --output bench/results/m1/airwallex-fx-job.json
```

Use `reconcile` after uncertainty; it only reads the financial service. `SCHEDULED`, missing history, mismatched amounts, wrong request ID and unknown outcomes do not credit float. Only a settled conversion matching both signed wallet entries and local quote terms creates append-only ledger entries. They record an Airwallex sell debit, an Airwallex treasury credit in its actual currency, and a separate SIMULATED USDZ entry. The ledger audit-chain head is included in every job report.

The dashboard's Treasury funding table renders these states before a provider purchase exists. A later `banked-job` using this scope must include `--treasury-request-id m1-fx-20261102-001` and have separate approvals for its hold and Metal funding/purchase/withdrawal. The workflow still checks the real Metal wallet; demo float cannot satisfy that check. This runbook authorizes none of those later actions.

## Retire a stuck PaymentIntent scope

New direct create failures with HTTP 4xx `configuration_error` become `REJECTED_NO_OBJECT`; the request ID is consumed. `duplicate_request` becomes `REQUEST_ID_CONSUMED` and does not prove no object exists. Timeouts and 5xx remain unknown. Consumed IDs are never replayed. Historical journals are not automatically reclassified or erased.

Retirement is a local tombstone, not a remote cancellation. Supply a redacted JSON file with exactly these fields:

```json
{
  "scope": "old-scope",
  "request_id": "the-original-request-uuid",
  "kind": "AIRWALLEX_SUPPORT",
  "reference": "support-case-reference",
  "no_object_created": true
}
```

Use only actual support confirmation. `RECORDED_CONFIGURATION_ERROR` is an alternative only when the same request has a locally recorded 4xx configuration rejection. An empty lookup alone is insufficient. The command also requires an empty, complete fresh order lookup and refuses scopes with other financial operations or an already-used replacement. It preserves the original operation ID and rejects future writes against the retired scope.

PowerShell:

```powershell
python -m touchstone airwallex-retire --scope old-scope --replacement-scope fresh-scope --journal data/banked/airwallex.sqlite --evidence path/to/retirement-evidence.json
python -m touchstone airwallex-retire --scope old-scope --replacement-scope fresh-scope --journal data/banked/airwallex.sqlite --evidence path/to/retirement-evidence.json --execute
```

Bash:

```bash
python -m touchstone airwallex-retire --scope old-scope --replacement-scope fresh-scope --journal data/banked/airwallex.sqlite --evidence path/to/retirement-evidence.json
python -m touchstone airwallex-retire --scope old-scope --replacement-scope fresh-scope --journal data/banked/airwallex.sqlite --evidence path/to/retirement-evidence.json --execute
```

These placeholders must be replaced locally from actual evidence. This agent has not read the private journal or retired any live scope. Confirm support's outcome before filling in `no_object_created`.

## Optional acquiring/card branch

Hosted checkout and direct hold workflows now require `--execute` for any path that can create/confirm/capture/cancel; hold recovery can perform writes and therefore also requires it. Hosted `--status` is read-only. Execution remains blocked until acquiring enablement and a written hold/capture cap are confirmed. Card issuing is not known enabled, so the conditional virtual-card stretch was not started.

## Reproduce controlled evidence

PowerShell:

```powershell
$env:TOUCHSTONE_IGNORE_LOCAL_CONFIG = '1'
python -m unittest discover -s tests -v
python tools/metal.py test
python tools/prove_m1.py
```

Bash:

```bash
export TOUCHSTONE_IGNORE_LOCAL_CONFIG=1
python -m unittest discover -s tests -v
python tools/metal.py test
python tools/prove_m1.py
```

`prove_m1.py` uses temporary stores, controlled adapters and a network refusal. Its output is **MOCK**, including the rejected/retired operation; it never reads account configuration or wallets.
