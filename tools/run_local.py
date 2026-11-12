"""Run the installed, hash-pinned model on one NVIDIA GPU for the provider."""
import argparse
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.telemetry import sample

START_LIMIT_C=65
STOP_LIMIT_C=75
CHECK_INTERVAL_SECONDS=5


def stop_reason(observation, *, starting=False):
    temperature=observation.get('temperature_c')
    if (observation.get('label')!='MEASURED' or type(temperature) not in (int,float)
            or not 0<=temperature<150):
        return 'GPU_TEMPERATURE_UNAVAILABLE'
    if observation.get('thermal_throttling_active') is True:return 'GPU_THERMAL_THROTTLING'
    if temperature>=(START_LIMIT_C if starting else STOP_LIMIT_C):return 'GPU_TEMPERATURE_LIMIT'
    return None


def stop_owned_process(process):
    if process.poll() is not None:return
    process.terminate()
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill();process.wait(timeout=5)


def supervise(process, *, observe=sample, sleep=time.sleep, record=lambda _:None):
    """Monitor only the child we launched; never restarts after a thermal stop."""
    peak=None
    try:
        while process.poll() is None:
            observation=observe()
            reason=stop_reason(observation)
            temperature=observation.get('temperature_c')
            if type(temperature) in (int,float) and 0<=temperature<150:
                peak=max(peak or temperature,temperature)
            record({'state':'STOPPED' if reason else 'MONITORING','reason':reason,
                'observed_at':time.time(),'temperature_c':temperature,'peak_temperature_c':peak,
                'start_limit_c':START_LIMIT_C,'stop_limit_c':STOP_LIMIT_C,
                'check_interval_seconds':CHECK_INTERVAL_SECONDS,'automatic_restart':False})
            if reason:
                stop_owned_process(process)
                return 2
            sleep(CHECK_INTERVAL_SECONDS)
        record({'state':'EXITED','exit_code':process.returncode,'peak_temperature_c':peak,
            'automatic_restart':False})
        return process.returncode
    finally:
        stop_owned_process(process)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=['economy', 'balanced'], default='balanced')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--ctx-size', type=int, default=2048)
    parser.add_argument('--log-name', default='provider-model', help='Log stem; lets two tiers run side by side')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', args.log_name):
        parser.error('--log-name must be 1-40 safe characters')
    if not 512 <= args.ctx_size <= 16384:
        parser.error('--ctx-size must be between 512 and 16384; profiling checks actual VRAM headroom')
    observation=sample()
    reason=stop_reason(observation,starting=True)
    if reason:
        print(json.dumps({'mode':'BLOCKED','reason':reason,'temperature_c':observation.get('temperature_c'),
            'start_limit_c':START_LIMIT_C,'model_started':False}),flush=True)
        return 2
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
    log_path = ROOT / 'tmp/inference' / f'{args.log_name}.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'mode': 'LOCAL_MODEL', 'tier': args.tier, 'device': selected[0],
                      'url': f'http://127.0.0.1:{args.port}', 'model_sha256': manifest['model_sha256'],
                      'gpu_start_limit_c':START_LIMIT_C,'gpu_stop_limit_c':STOP_LIMIT_C}), flush=True)
    def record(value):
        path=log_path.with_name('gpu-guard.json' if args.log_name=='provider-model' else f'{args.log_name}-gpu-guard.json')
        temporary=path.with_suffix('.pending')
        temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');temporary.replace(path)
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log, cwd=ROOT)
        try:
            return supervise(process,record=record)
        except KeyboardInterrupt:
            return 0


if __name__ == '__main__':
    raise SystemExit(main())
