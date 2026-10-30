"""One provider inference call over stdin/stdout; sources are data only."""
import json
import sys

from .local_tools import solve
from .providers import local_inference
from .workload import Task


def main():
    try:
        raw = json.loads(sys.stdin.read(20000))
        task = Task(**raw["task"])
        if raw["mode"] == "tool":
            output, latency = solve(task), None
            if output is None:
                raise ValueError("Unsupported tool input")
        elif raw["mode"] == "model":
            output, latency = local_inference(task)
        else:
            raise ValueError("Invalid worker mode")
        print(json.dumps({"output": output, "latency_ms": latency, "provider_type": raw["mode"], "mode": "LOCAL_EXECUTION"}, allow_nan=False))
        return 0
    except Exception:
        print(json.dumps({"error": "PROVIDER_EXECUTION_FAILED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
