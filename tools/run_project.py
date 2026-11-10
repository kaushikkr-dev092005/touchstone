"""Start the installed local stack without purchasing inference or moving funds."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.config import KEYS, load_local
from touchstone.treasury import NoRedirect


def environment():
    if os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
            for key in KEYS | {'AIRWALLEX_BASE_URL'}:
                try:
                    value = winreg.QueryValueEx(registry, key)[0]
                    if isinstance(value, str) and value:
                        os.environ.setdefault(key, value)
                except FileNotFoundError:
                    pass
    load_local()
    return os.environ.copy()


def child_environment(env, service):
    result = dict(env)
    for key in list(result):
        if service != 'dashboard' and (key.startswith('AIRWALLEX_') or key == 'AGENT_PRIVATE_KEY'):
            result.pop(key)
        if service != 'premium' and key.startswith('ANTHROPIC_'):
            result.pop(key)
        if service == 'model' and key.startswith('METAL_'):
            result.pop(key)
    result['TOUCHSTONE_IGNORE_LOCAL_CONFIG'] = '1'
    return result


def occupied(port):
    with socket.socket() as probe:
        probe.settimeout(.3)
        return probe.connect_ex(('127.0.0.1', port)) == 0


def health(port, path):
    try:
        with urllib.request.build_opener(NoRedirect()).open(f'http://127.0.0.1:{port}{path}', timeout=2) as response:
            result = json.load(response)
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def launch(command, env):
    return subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), start_new_session=os.name != 'nt')


def ensure(port, path, valid, command, env, start, seconds=40):
    current = health(port, path)
    if valid(current):
        return {'label': 'MEASURED', 'status': 'RUNNING', 'existing_service_kept': True}
    if occupied(port):
        return {'label': 'BLOCKED', 'status': 'PORT_IN_USE_OR_SERVICE_NOT_READY'}
    if not start:
        return {'label': 'BLOCKED', 'status': 'STOPPED'}
    process = launch(command, env)
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if valid(health(port, path)):
            return {'label': 'MEASURED', 'status': 'RUNNING', 'pid': process.pid, 'existing_service_kept': False}
        if process.poll() is not None:
            return {'label': 'BLOCKED', 'status': 'START_FAILED', 'exit_code': process.returncode}
        time.sleep(.25)
    return {'label': 'BLOCKED', 'status': 'STARTING_OR_UNAVAILABLE', 'pid': process.pid}


def run(start=True, tier='balanced', ctx_size=8192, start_model=True):
    env = environment()
    services = {}
    services['dashboard'] = ensure(8088, '/api/state', lambda r: isinstance(r.get('jobs'), list),
        [sys.executable, '-m', 'touchstone', 'serve'], child_environment(env, 'dashboard'), start)
    manifest_path = ROOT/'.tools/models'/f'{tier}-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    if not start_model:
        running=health(8080,'/health').get('status')=='ok'
        services['model']={'label':'MEASURED' if running else 'BLOCKED',
            'status':'RUNNING' if running else 'SKIPPED_BY_REQUEST','existing_service_kept':running}
    elif manifest and all(Path(manifest.get(k, '')).is_file() for k in ('executable', 'model_path')):
        services['model'] = ensure(8080, '/health', lambda r: r.get('status') == 'ok',
            [sys.executable, str(ROOT/'tools/run_local.py'), '--tier', tier, '--ctx-size', str(ctx_size)],
            child_environment(env, 'model'), start)
        if services['model']['status'] == 'RUNNING':
            props = health(8080, '/props')
            if Path(props.get('model_path') or '').resolve() != Path(manifest['model_path']).resolve():
                services['model'] = {'label': 'BLOCKED', 'status': 'DIFFERENT_MODEL_RUNNING'}
    else:
        services['model'] = {'label': 'BLOCKED', 'status': 'INSTALL_MODEL_FIRST'}
    for name, port, provider, mode in (('local_seller', 8092, 'local-gpu', 'model'),
                                      ('premium', 8093, 'hosted-premium', 'anthropic')):
        if name == 'premium' and not env.get('ANTHROPIC_API_KEY'):
            services[name] = {'label': 'BLOCKED', 'status': 'HOSTED_CREDENTIALS_REQUIRED'}
            continue
        if name == 'local_seller' and services['model']['status'] != 'RUNNING' and start_model:
            services[name] = {'label': 'BLOCKED', 'status': 'LOCAL_MODEL_NOT_READY'}
            continue
        if not env.get('METAL_RPC_URL'):
            services[name] = {'label': 'BLOCKED', 'status': 'RPC_CONFIGURATION_REQUIRED'}
            continue
        # Starting a service must preserve the existing signer, not generate another wallet.
        store = ROOT/'data/metal'/f'provider-{provider}'/'wallet.sqlite'
        if not store.is_file():
            services[name] = {'label': 'BLOCKED', 'status': 'EXISTING_SELLER_WALLET_REQUIRED'}
            continue
        seller_env = child_environment(env, name)
        seller_env.update(TOUCHSTONE_PROVIDER_ID=provider, TOUCHSTONE_PROVIDER_MODE=mode,
            TOUCHSTONE_PROVIDER_PORT=str(port), TOUCHSTONE_PYTHON=sys.executable)
        if name == 'local_seller':
            seller_env.update(LOCAL_INFERENCE_URL='http://127.0.0.1:8080/v1/chat/completions',
                LOCAL_MODEL=manifest['model'], LOCAL_MODEL_SHA256=manifest['model_sha256'])
        from touchstone.metal import node_executable
        services[name] = ensure(port, '/health', lambda r, p=provider, m=mode:
            r.get('provider_id') == p and r.get('provider_type') == m and
            (r.get('inference_ready') is True or (m=='model' and not start_model)),
            [node_executable(), str(ROOT/'integrations/metal/provider.mjs')], seller_env, start)
    return {'label': 'MEASURED', 'observed_at': time.time(), 'scope': 'LOCAL_STARTUP_ONLY',
        'services': services, 'dashboard_url': 'http://127.0.0.1:8088/',
        'local_stack_running': all(services[k]['status'] == 'RUNNING' for k in ('dashboard', 'model', 'local_seller')),
        'requested_services_running':all(services[k]['status']=='RUNNING' for k in
            (('dashboard','model','local_seller') if start_model else ('dashboard','local_seller'))),
        'model_start_requested':start_model,
        'dashboard_mode': 'SIMULATED', 'live_paid_integration': 'NOT_CHECKED_BY_STARTUP',
        'money_moved': False, 'payments_sent': 0,
        'notice': 'Seller health is not RPC authentication, funded-wallet, model-quality or paid-delivery proof.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', action='store_true', help='Only inspect local services')
    parser.add_argument('--tier', choices=('economy', 'balanced'), default='balanced')
    parser.add_argument('--ctx-size', type=int, default=8192)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--skip-model',action='store_true',help='Start dashboard/sellers without starting a model; existing models are kept')
    parser.add_argument('--output', default='tmp/project-runtime.json')
    args = parser.parse_args()
    if not 512 <= args.ctx_size <= 16384:
        parser.error('--ctx-size must be between 512 and 16384')
    try:
        report = run(not args.status, args.tier, args.ctx_size,start_model=not args.skip_model)
    except Exception as error:
        report = {'label': 'BLOCKED', 'failure_type': type(error).__name__, 'money_moved': False, 'payments_sent': 0}
    from tools.configure_airwallex import save_status
    save_status(report, ROOT/args.output)
    print(json.dumps(report, indent=2))
    if not args.status and not args.no_browser and report.get('services', {}).get('dashboard', {}).get('status') == 'RUNNING':
        webbrowser.open(report['dashboard_url'])
    return 0 if report.get('requested_services_running',report.get('local_stack_running')) else 2


if __name__ == '__main__':
    raise SystemExit(main())
