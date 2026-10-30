"""Read-only RPC diagnostics. Never include authenticated URLs in errors."""
import json
import os
import urllib.request

from .treasury import NoRedirect


def inspect_rpc():
    from .config import load_local
    load_local()
    url = os.environ.get("METAL_RPC_URL")
    if not url:
        raise ValueError("Configure METAL_RPC_URL locally first")
    requests = [{"jsonrpc": "2.0", "id": i, "method": method, "params": []}
                for i, method in enumerate(("eth_chainId", "eth_blockNumber", "web3_clientVersion"), 1)]
    try:
        request = urllib.request.Request(url, json.dumps(requests).encode(), {"Content-Type": "application/json"})
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            replies = json.loads(response.read(200000))
        results = {r["id"]: r.get("result") for r in replies}
        chain = int(results[1], 16)
        if chain != 63825:
            raise ValueError("Wrong chain")
        return {"mode": "READ_ONLY", "connected": True, "chain_id": chain,
                "block_number": int(results[2], 16), "client_version": str(results[3])[:100],
                "endpoint_disclosed": False, "transactions_sent": 0}
    except Exception:
        raise RuntimeError("RPC check failed or returned a different chain; endpoint details hidden") from None
