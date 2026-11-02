"""Start an isolated GPU server, measure repeated tasks, record telemetry, then stop it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import socket
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.procurement_evidence import digest
from touchstone.providers import local_inference
from touchstone.verifier import check, VERIFIER_VERSION
from touchstone.workload import generate


def telemetry():
    result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,temperature.gpu,power.draw,clocks.sm,driver_version", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
    values = result.stdout.strip().splitlines()[0].split(", ")
    return dict(zip(["name", "total_vram_mib", "used_vram_mib", "temperature_c", "power_w", "clock_mhz", "driver"], values))


def run(tier, steps, repetitions, port):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError("Profiling port is already in use; choose another port to avoid measuring the wrong server") from None
    manifest = json.loads((ROOT / ".tools/models" / f"{tier}-manifest.json").read_text())
    devices = subprocess.run([manifest["executable"], "--list-devices"], capture_output=True, text=True, timeout=20)
    device_text = devices.stdout + devices.stderr
    selected = re.search(r"(Vulkan\d+):\s*NVIDIA[^\r\n]*", device_text)
    if not selected:
        raise RuntimeError("The llama.cpp runtime did not expose an NVIDIA Vulkan device")
    device = selected[1]
    output = ROOT / "bench/results" / f"local-{tier}.json"
    logs = ROOT / "tmp/inference"
    logs.mkdir(parents=True, exist_ok=True)
    logpath = logs / f"{tier}.log"
    command = [manifest["executable"], "-m", manifest["model_path"], "--host", "127.0.0.1", "--port", str(port),
               "--ctx-size", "2048", "--parallel", "1", "--n-gpu-layers", "99", "--device", device,
               "--split-mode", "none", "--log-verbosity", "4", "--jinja"]
    previous = {k: os.environ.get(k) for k in ("LOCAL_INFERENCE_URL", "LOCAL_MODEL")}
    before = telemetry()
    with logpath.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, cwd=ROOT)
        try:
            for _ in range(180):
                if process.poll() is not None:
                    raise RuntimeError("Model server exited; inspect " + str(logpath))
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(.5)
            else:
                raise RuntimeError("Model server startup timed out")
            os.environ["LOCAL_INFERENCE_URL"] = f"http://127.0.0.1:{port}/v1/chat/completions"
            os.environ["LOCAL_MODEL"] = manifest["model"]
            tasks, _ = generate(41, steps)
            local_inference(tasks[0])  # warm-up excluded
            warmed = telemetry()
            if int(warmed["used_vram_mib"]) > int(warmed["total_vram_mib"]) * .8:
                raise RuntimeError("GPU headroom below 20%; reduce model or context before profiling")
            rows, samples = [], [before, warmed]
            for repeat in range(repetitions):
                tasks, truth = generate(41 + repeat, steps)
                for i, task in enumerate(tasks):
                    result, latency = local_inference(task)
                    verdict = check(task, result)
                    rows.append({"seed": 41 + repeat, "step_id": task.id, "kind": task.kind,
                                 "latency_ms": latency, "verifier_passed": verdict["passed"],
                                 "true_correct": result == truth[task.id], "output": result,
                                 "verification_reason": verdict["reason"]})
                    if i % 10 == 0:
                        samples.append(telemetry())
                print(f"Measured seed {41 + repeat}: {steps} calls", flush=True)
            text = logpath.read_text(encoding="utf-8", errors="replace")
            offloaded = re.findall(r"offloaded (\d+)/(\d+) layers", text)
            allocation_confirmed = int(warmed["used_vram_mib"]) - int(before["used_vram_mib"]) > 200
            gpu_confirmed = bool(selected and allocation_confirmed)
            latencies = sorted(r["latency_ms"] for r in rows)
            report = {"mode": "LOCAL_MEASURED", "payments": "NONE", "provider_tier": tier,
                      "gpu_offload_confirmed": gpu_confirmed, "offloaded_layers": offloaded[-1] if offloaded else None,
                      "gpu_confirmation": {"selected_device": selected[0], "n_gpu_layers_requested": 99,
                                           "exclusive_device_selection": True, "nvidia_vram_allocation_observed": allocation_confirmed},
                      "decoding": "json-schema-v1",
                      "source_sha256": {name: digest(ROOT / "touchstone" / name)
                                        for name in ("providers.py", "verifier.py", "workload.py")},
                      "warmups_discarded": 1, "steps_per_seed": steps, "seeds": list(range(41, 41 + repetitions)),
                      "verifier_version": VERIFIER_VERSION, "environment": {k: v for k, v in manifest.items() if k not in {"executable", "model_path"}},
                      "python": platform.python_version(), "hardware_samples": samples,
                      "true_success_rate": sum(r["true_correct"] for r in rows) / len(rows),
                      "verifier_acceptance_rate": sum(r["verifier_passed"] for r in rows) / len(rows),
                      "latency_p50_ms": statistics.median(latencies), "latency_p95_ms": latencies[int((len(latencies)-1)*.95)], "rows": rows}
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({k: report[k] for k in ("mode", "gpu_offload_confirmed", "true_success_rate", "latency_p50_ms", "latency_p95_ms")}, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=15)
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=["economy", "balanced"], default="economy")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--port", type=int, default=8089)
    args = parser.parse_args()
    if not 1 <= args.steps <= 200 or not 1 <= args.repetitions <= 5:
        parser.error("Use 1-200 steps and 1-5 repetitions")
    run(args.tier, args.steps, args.repetitions, args.port)
