"""Turn an FX-aware comparison into one approved, funded, single-use fiat-provider purchase.

The comparison in fx_router never dispatches. This module is the only bridge and it adds, in order:
a written approval bound to scope, provider and a maximum effective cost; a fresh re-comparison at
execution time that must still pick the same provider from MEASURED offers and unexpired quotes;
an independent funded-balance read for the card currency; a durable single-use journal entry before
any dispatch; and the card rail's own re-verification and merchant adapter. No conversion is created.
"""
from decimal import Decimal, ROUND_FLOOR
import math
import re
import time

from .fx_router import compare
from .holds import OperationJournal, OutcomeUnknown
from .ledger import PolicyError


def verify_funding(client, currency, needed_micro):
    """Read-only: the account must hold at least `needed_micro` (micro-units of `currency`) available."""
    rows = client.current_balances()
    for row in rows:
        if row.get('currency') == currency:
            try:
                available = int((Decimal(str(row['available_amount'])) * 1_000_000).to_integral_value(ROUND_FLOOR))
            except (KeyError, ArithmeticError, ValueError):
                raise PolicyError('Balance row is unreadable; no purchase dispatched') from None
            if available < needed_micro:
                raise PolicyError(f'Insufficient funded {currency} balance for this purchase; no purchase dispatched')
            return {'currency': currency, 'available_micro': available, 'required_micro': needed_micro}
    raise PolicyError(f'No {currency} wallet is funded for this purchase; no purchase dispatched')


def check_approval(approval, *, scope, provider, cost_micro, now):
    required = {'scope', 'provider', 'approver', 'max_effective_cost_micro', 'expires_at'}
    if not isinstance(approval, dict) or not required <= set(approval):
        raise PolicyError('A written approval with scope, provider, approver, maximum cost and expiry is required')
    if approval['scope'] != scope or approval['provider'] != provider:
        raise PolicyError('Approval does not cover this scope and provider')
    if not isinstance(approval['approver'], str) or not approval['approver'].strip():
        raise PolicyError('Approval needs a named approver')
    if type(approval['max_effective_cost_micro']) is not int or cost_micro > approval['max_effective_cost_micro']:
        raise PolicyError('Effective cost exceeds the approved maximum')
    if (type(approval['expires_at']) not in (int, float) or not math.isfinite(approval['expires_at'])
            or approval['expires_at'] <= now):
        raise PolicyError('Approval expired')


def execute_preferred(offers, rates, *, scope, approval, card_rail, card_scope, adapters, funding_client, journal: OperationJournal,
                      execute=False, now=None, **compare_options):
    """Dispatch the single cheapest eligible provider. Raises (never silently falls back) on any gate."""
    if not execute:
        raise ValueError('Fiat procurement requires --execute and separate written approval')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', scope):
        raise ValueError('Invalid procurement scope')
    now = time.time() if now is None else now
    comparison = compare(offers, rates, now=now, allow_simulated=False, **compare_options)
    chosen = next((row for row in comparison['offers'] if row['provider'] == comparison['preferred_provider']), None)
    if chosen is None or not chosen['eligible'] or chosen['cost_label'] == 'SIMULATED':
        raise PolicyError('No eligible MEASURED fiat provider; nothing dispatched')
    check_approval(approval, scope=scope, provider=chosen['provider'], cost_micro=chosen['effective_cost_micro'], now=now)
    adapter = adapters.get(chosen['provider'])
    if adapter is None:
        raise PolicyError('No verified merchant adapter is configured for the selected provider')
    funding = verify_funding(funding_client, chosen['currency'], chosen['price_micro'])
    terms = {'provider': chosen['provider'], 'price_micro': chosen['price_micro'], 'currency': chosen['currency'],
             'effective_cost_micro': chosen['effective_cost_micro'], 'quote_id': chosen['quote_id'],
             'approver': approval['approver'], 'card_scope': card_scope}
    request_id, prior = journal.begin(scope, 'fx_procurement', '/local/fx-procurement', terms)
    if prior:
        return {**prior, 'idempotent_replay': True}
    try:
        payment = card_rail.pay(card_scope, chosen['price_micro'], adapter=adapter, job_id=scope, execute=True,
                                expected_currency=chosen['currency'])
    except (PolicyError, ValueError):
        journal.abandon(scope, 'fx_procurement')  # refused before any merchant call; a corrected retry is allowed
        raise
    except Exception:
        journal.uncertain(scope, 'fx_procurement')
        raise OutcomeUnknown('Fiat procurement outcome is unresolved; reconcile the card scope and never retry automatically') from None
    result = {'label': payment['label'], 'scope': scope, 'request_id': request_id, 'terms': terms, 'funding_checked': funding,
              'comparison': {'preferred_provider': comparison['preferred_provider'], 'decision': 'DISPATCHED_AFTER_APPROVAL',
                             'offers': comparison['offers']},
              'payment': payment, 'conversions_created': 0, 'fiat_token_bridge': False}
    journal.observe_raw(scope, 'fx_procurement', result)
    return result
