"""Optional offline browser checks, including restart/reconnect and fresh session tokens."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def isolated_environment():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('AIRWALLEX_', 'METAL_', 'ANTHROPIC_', 'TOUCHSTONE_LIVE_'))
           and k != 'AGENT_PRIVATE_KEY'}
    env['TOUCHSTONE_IGNORE_LOCAL_CONFIG'] = '1'
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-landing', action='store_true')
    parser.add_argument('--output', default='tmp/release-browser')
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    folder = (ROOT / args.output).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    env = isolated_environment()

    with tempfile.TemporaryDirectory(prefix='mock-release-', dir=folder) as data:
        def start():
            process = subprocess.Popen([sys.executable, 'tools/run_mock.py', '--port', str(port), '--data-dir', data],
                cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError('Isolated mock server exited')
                try:
                    with urllib.request.urlopen(base + '/api/state', timeout=1):
                        return process
                except OSError:
                    time.sleep(.1)
            process.terminate()
            process.wait(timeout=10)
            raise RuntimeError('Isolated mock server did not start')

        process = start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={'width': 1440, 'height': 900})
                page = context.new_page()
                errors, external = [], []
                page.on('pageerror', lambda error: errors.append(str(error)))

                def route(request_route):
                    request = request_route.request
                    if urlparse(request.url).hostname != '127.0.0.1':
                        external.append(request.resource_type)
                        request_route.abort()
                    else:
                        request_route.continue_()

                context.route('**/*', route)
                page.goto(base, wait_until='domcontentloaded')
                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
                original_token = page.locator('meta[name="touchstone-token"]').get_attribute('content')
                process.terminate()
                process.wait(timeout=10)
                page.wait_for_function("() => document.getElementById('connection').textContent==='RECONNECTING'")
                process = start()
                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')", timeout=20000)
                refused = page.request.post(base + '/api/halt', headers={'X-Touchstone-Token': original_token}, data={})
                assert refused.status == 403, 'A prior-process token was accepted'
                page.reload(wait_until='domcontentloaded')
                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
                fresh_token = page.locator('meta[name="touchstone-token"]').get_attribute('content')
                assert fresh_token and fresh_token != original_token
                accepted = page.request.post(base + '/api/halt', headers={'X-Touchstone-Token': fresh_token}, data={})
                assert accepted.status == 200, 'The fresh session token was rejected'

                captures = []
                for reduced in (False, True):
                    page.emulate_media(reduced_motion='reduce' if reduced else 'no-preference')
                    for width, height in ((1440, 900), (390, 844)):
                        page.set_viewport_size({'width': width, 'height': height})
                        for name, path in [('dashboard', '/'), *([('landing', '/site/')] if args.include_landing else [])]:
                            response = page.goto(base + path, wait_until='networkidle') if name == 'landing' else page.goto(base + path, wait_until='domcontentloaded')
                            assert response.status == 200
                            if name == 'dashboard':
                                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
                            page.wait_for_timeout(250)
                            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{name} overflow'
                            assert page.locator('h1').first.is_visible()
                            filename = f'{name}-{width}-{"reduced" if reduced else "motion"}.png'
                            page.screenshot(path=str(folder / filename))
                            captures.append(filename)
                context.set_offline(True)
                assert page.locator('h1').first.is_visible()
                assert not external, 'A page requested an external resource'
                assert not errors, 'Browser script errors occurred'
                browser.close()
            report = {'label': 'MEASURED', 'scope': 'ISOLATED_SIMULATED_RELEASE',
                'sse_restart_reconnect': 'passed', 'old_process_token_rejected': True,
                'fresh_process_token_accepted': True, 'viewports': [[1440, 900], [390, 844]],
                'reduced_motion_on_and_off': 'passed', 'landing_built_and_checked': args.include_landing,
                'offline_loaded_page': 'passed', 'external_requests': external, 'page_errors': errors,
                'screenshots': captures, 'financial_transactions': 0}
            (folder / 'review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            print(json.dumps(report))
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'label': 'BLOCKED', 'failure_type': type(error).__name__,
                          'financial_transactions': 0}))
        raise SystemExit(1) from None
