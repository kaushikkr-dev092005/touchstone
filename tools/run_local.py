"""Run the installed, hash-pinned model on one NVIDIA GPU for the provider."""
import argparse
import json
from pathlib import Path
import re
import socket
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=['economy', 'balanced'], default='balanced')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--ctx-size', type=int, default=2048)
    args = parser.parse_args()
    if not 512 <= args.ctx_size <= 16384:
        parser.error('--ctx-size must be between 512 and 16384; profiling checks actual VRAM headroom')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))
    manifest = json.loads((ROOT / '.tools/models' / f'{args.tier}-manifest.json').read_text())
    result = subprocess.run([manifest['executable'], '--list-devices'], capture_output=True, text=True, timeout=20)
    selected = re.search(r'(Vulkan\d+):\s*NVIDIA[^\r\n]*', result.stdout + result.stderr)
    if not selected:
        raise RuntimeError('NVIDIA Vulkan device unavailable')
    command = [manifest['executable'], '-m', manifest['model_path'], '--host', '127.0.0.1', '--port', str(args.port),
               '--ctx-size', str(args.ctx_size), '--parallel', '1', '--n-gpu-layers', '99', '--device', selected[1],
               '--split-mode', 'none', '--jinja']
    log_path = ROOT / 'tmp/inference/provider-model.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'mode': 'LOCAL_MODEL', 'tier': args.tier, 'device': selected[0],
                      'url': f'http://127.0.0.1:{args.port}', 'model_sha256': manifest['model_sha256']}), flush=True)
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, cwd=ROOT)
        try:
            return process.wait()
        except KeyboardInterrupt:
            process.terminate()
            process.wait(timeout=15)
            return 0


if __name__ == '__main__':
    raise SystemExit(main())
