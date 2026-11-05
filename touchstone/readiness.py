"""Local readiness checks expose presence only, never credential values."""
import json
import os
from pathlib import Path
import platform
import hashlib

ROOT = Path(__file__).resolve().parent.parent


def _object(path):
    """A readiness artifact is advisory: anything but a readable JSON object counts as absent."""
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def inspect():
    from .config import load_local
    load_local()
    profiles = []
    for tier in ("economy", "balanced"):
        path = ROOT / "bench/results" / f"local-{tier}.json"
        raw = _object(path)
        if raw:
            profiles.append({"tier": tier, **{k: raw.get(k) for k in ("mode", "gpu_offload_confirmed", "true_success_rate", "latency_p50_ms", "latency_p95_ms")}})
    node = ROOT / ".tools/node/manifest.json"
    package = ROOT / "integrations/metal/package-lock.json"
    rpc, funding, airwallex, hold, proof = {}, {}, {}, {}, {}
    rpc = _object(ROOT / 'data/rpc-readiness.json')
    if rpc.get('endpoint_fingerprint') != hashlib.sha256(os.environ.get('METAL_RPC_URL', '').encode()).hexdigest():
        rpc = {}
    hold = _object(ROOT / 'bench/results/airwallex-hold-proof.json')
    airwallex = _object(ROOT / 'data/airwallex-readiness.json')
    account_context = bool(os.environ.get('AIRWALLEX_ACCOUNT_ID'))
    account_fingerprint = hashlib.sha256(os.environ.get('AIRWALLEX_ACCOUNT_ID', '').encode()).hexdigest()
    observation_matches_account = account_context and airwallex.get('account_fingerprint') == account_fingerprint
    if not observation_matches_account:
        airwallex = {}
    historical_hold_error = hold.get('failure', {}).get('code') == 'configuration_error'
    hold_matches_account = account_context and hold.get('account_fingerprint') == account_fingerprint
    hold_workflow = ('BLOCKED_MERCHANT_CONFIGURATION' if historical_hold_error and hold_matches_account else
                     'HISTORICAL_MERCHANT_CONFIGURATION_ERROR' if historical_hold_error else 'IMPLEMENTED_UNVERIFIED')
    fx = _object(ROOT/'bench/results/m1/live-fx-single-conversion.json')
    fx_matches_account = (account_context and fx.get('account_fingerprint') == account_fingerprint
                          and fx.get('label') == 'MEASURED' and fx.get('reconciliation') == 'MATCHED_WALLET_HISTORY'
                          and fx.get('conversion', {}).get('status') == 'SETTLED')
    fx_proof = ({'label': 'MEASURED', 'status': 'RECONCILED',
                 **{k: fx['conversion'].get(k) for k in ('conversion_id', 'sell_currency', 'sell_amount', 'buy_currency', 'buy_amount')},
                 'metal_funded': False} if fx_matches_account else {'label': 'BLOCKED', 'status': 'UNVERIFIED'})
    card = _object(ROOT/'bench/results/m1/current-hosted-card-proof.json')
    card_result = card.get('result') if isinstance(card.get('result'), dict) else {}
    card_complete = bool(account_context and card.get('account_fingerprint') == account_fingerprint
                         and card.get('label') == 'MEASURED' and card_result.get('complete') is True
                         and card_result.get('operator_capture_recorded') is True
                         and card_result.get('payment_status') in {'SUCCEEDED', 'CANCELLED'})
    if card_complete:
        hold_workflow = 'MEASURED_HOSTED_CAPTURE_COMPLETE'
    checkout_read = bool(airwallex.get('checkout_sessions_read'))
    hosted_checkout_workflow = ('BLOCKED_ACCOUNT_CONTEXT' if not account_context else
                                'BLOCKED_CHECKOUT_SESSIONS_READ' if not checkout_read else
                                'MEASURED_CAPTURE_COMPLETE' if card_complete else 'WRITE_UNVERIFIED')
    try:
        raw = json.loads((ROOT / 'bench/results/metal-paid-proof.json').read_text(encoding='utf-8'))
        result = raw.get('result', {})
        if raw.get('mode') == 'REAL_TESTNET_PROTOCOL_PROBE' and result.get('state') == 'DELIVERED':
            task = raw.get('terms', {}).get('task', {})
            source = task.get('source', {})
            amounts = source.get('amounts_cents')
            discount = source.get('discount_cents')
            expected_output = ({"total_cents": sum(amounts) - discount}
                               if task.get('kind') == 'arithmetic' and isinstance(amounts, list)
                               and amounts and all(type(amount) is int for amount in amounts)
                               and type(discount) is int else None)
            proof = {"phase": result['state'], "paid_calls": raw.get('paid_calls_recorded'),
                     "price_micro_usd": int(result['receipt']['invoice']['amount'])//10**12,
                     "receipt_id": result['receipt']['invoice']['id'], "receipt_status": result['receipt']['status'],
                     "verification_passed": raw.get('verdict', {}).get('passed'),
                     "actual_output": result.get('output', {}).get('body', {}).get('output'),
                     "expected_output": expected_output,
                     "cached_retry_identical": raw.get('cached_retry_identical'),
                     "provider_receipt_replay_identical": raw.get('provider_receipt_replay_identical'),
                     "withdrawal_status": raw.get('withdrawal', {}).get('status'),
                     "returned_float_confirmed": raw.get('withdrawal', {}).get('returned_float_confirmed', False),
                     "airwallex": raw.get('airwallex'), "model": "Qwen2.5-1.5B Q4_K_M"}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        funding = json.loads((ROOT / 'data/metal-funding-readiness.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    return {"python": platform.python_version(),
            "airwallex": {"credentials_configured": all(bool(os.environ.get(k)) for k in ("AIRWALLEX_CLIENT_ID", "AIRWALLEX_API_KEY")),
                          "authenticated": airwallex.get('authenticated', False),
                          "balance_read": airwallex.get('balance_read', False),
                          "global_accounts_read": airwallex.get('global_accounts_read', False),
                          "account_context_configured": account_context,
                          "observation_matches_account": observation_matches_account,
                          "hold_workflow": hold_workflow,
                          "hold_error": hold.get('failure') if hold_matches_account else None,
                          "historical_hold_configuration_error": historical_hold_error,
                          "fx_proof": fx_proof,
                          "hosted_checkout": {"workflow": hosted_checkout_workflow,
                                               "read_access_verified": checkout_read,
                                               "write_access_verified": card_complete,
                                               "authorization_active": False if card_complete else None,
                                               "captured_micro_usd": card_result.get('captured_micro_usd') if card_complete else None},
                          "dashboard_mode": "SIMULATED"},
            "metal": {"rpc_configured": bool(os.environ.get("METAL_RPC_URL")),
                      "funding_key_configured": bool(os.environ.get("AGENT_PRIVATE_KEY")),
                      "provider_configured": bool(os.environ.get("METAL_PROVIDER_URL")),
                      "sdk_locked": package.exists(),
                      "node_version": json.loads(node.read_text())["version"] if node.exists() else None,
                      "rpc_chain_verified": rpc.get('chain_id') == 63825,
                      "rpc_observed_at": rpc.get('observed_at'),
                      "funding_address": funding.get('address'),
                      "funding_observed": bool(funding),
                      "funding_has_tokens": int(funding.get('usdz_balance_base_units', '0')) > 0,
                      "funding_has_gas": int(funding.get('native_balance_base_units', '0')) > 0,
                      "paid_call_verified": bool(proof), "paid_proof": proof, "dashboard_mode": "SIMULATED"},
            "inference": {"profiles": profiles,
                          "hosted_anthropic": {"credentials_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
                                               "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
                                               "api_access_verified": False,
                                               "dashboard_mode": "SIMULATED"},
                          "dashboard_mode": "SIMULATED"},
            "secrets_disclosed": False}
