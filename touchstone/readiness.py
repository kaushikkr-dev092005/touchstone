"""Local readiness checks expose presence only, never credential values."""
import json
import os
from pathlib import Path
import platform
import hashlib

ROOT = Path(__file__).resolve().parent.parent


def inspect():
    from .config import load_local
    load_local()
    profiles = []
    for tier in ("economy", "balanced"):
        path = ROOT / "bench/results" / f"local-{tier}.json"
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            profiles.append({"tier": tier, **{k: raw.get(k) for k in ("mode", "gpu_offload_confirmed", "true_success_rate", "latency_p50_ms", "latency_p95_ms")}})
    node = ROOT / ".tools/node/manifest.json"
    package = ROOT / "integrations/metal/package-lock.json"
    rpc, funding, airwallex, hold, proof = {}, {}, {}, {}, {}
    try:
        rpc = json.loads((ROOT / 'data/rpc-readiness.json').read_text(encoding='utf-8'))
        if rpc.get('endpoint_fingerprint') != hashlib.sha256(os.environ.get('METAL_RPC_URL', '').encode()).hexdigest():
            rpc = {}
    except (OSError, ValueError):
        pass
    try:
        hold = json.loads((ROOT / 'bench/results/airwallex-hold-proof.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    try:
        airwallex = json.loads((ROOT / 'data/airwallex-readiness.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        pass
    try:
        raw = json.loads((ROOT / 'bench/results/metal-paid-proof.json').read_text(encoding='utf-8'))
        result = raw.get('result', {})
        if raw.get('mode') == 'REAL_TESTNET_PROTOCOL_PROBE' and result.get('state') == 'DELIVERED':
            proof = {"phase": result['state'], "paid_calls": raw.get('paid_calls_recorded'),
                     "price_micro_usd": int(result['receipt']['invoice']['amount'])//10**12,
                     "receipt_id": result['receipt']['invoice']['id'], "receipt_status": result['receipt']['status'],
                     "verification_passed": raw.get('verdict', {}).get('passed'),
                     "actual_output": result.get('output', {}).get('body', {}).get('output'),
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
                          "account_context_configured": bool(os.environ.get('AIRWALLEX_ACCOUNT_ID')),
                          "hold_workflow": "BLOCKED_MERCHANT_CONFIGURATION" if hold.get('failure', {}).get('code') == 'configuration_error' else "IMPLEMENTED_UNVERIFIED",
                          "hold_error": hold.get('failure'), "dashboard_mode": "SIMULATED"},
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
            "inference": {"profiles": profiles, "dashboard_mode": "SIMULATED"},
            "secrets_disclosed": False}
