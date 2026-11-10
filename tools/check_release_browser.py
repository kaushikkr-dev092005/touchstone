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


def record_demo(browser, base, folder):
    """Record actual simulated UI actions; saved live proofs keep their own labels."""
    context=browser.new_context(viewport={'width':1440,'height':900},record_video_dir=str(folder/'video'),
        record_video_size={'width':1440,'height':900},reduced_motion='reduce')
    errors=[];external=[]
    def route(request_route):
        if urlparse(request_route.request.url).hostname!='127.0.0.1':
            external.append(request_route.request.resource_type);request_route.abort()
        else:request_route.continue_()
    context.route('**/*',route)
    page=context.new_page();video=page.video
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(base,wait_until='domcontentloaded')
    page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
    page.evaluate("""() => {const c=document.createElement('div');c.id='recording-caption';
        Object.assign(c.style,{position:'fixed',bottom:'24px',left:'50%',transform:'translateX(-50%)',
        width:'min(1000px,90vw)',padding:'18px 24px',background:'#111',color:'#fff',border:'1px solid #d8b65a',
        font:'18px/1.5 system-ui',zIndex:'10000',boxShadow:'0 8px 32px #0005'});document.body.append(c);} """)
    scenes=[]
    def scene(text,selector=None,milliseconds=4000):
        scenes.append(text)
        page.evaluate('(text)=>document.getElementById("recording-caption").textContent=text',text)
        if selector:page.locator(selector).first.scroll_into_view_if_needed()
        page.wait_for_timeout(milliseconds)
    def idle():
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            state=page.request.get(base+'/api/state').json()
            if not state['worker_running']:return state
            page.wait_for_timeout(250)
        raise AssertionError('Simulated recording did not reach an idle state')
    scene('Touchstone: an approved budget, a checked result, and a receipt for every attempt.')
    scene('SAVED TESTNET EVIDENCE: a paid answer failed verification. Replaying its receipt did not purchase again.','#featured-evidence',6000)
    scene('SAVED QUALIFICATION: Sonnet passed unchanged criteria: 120/120 calibration, 59/60 fresh holdout trials. Synthetic review drafts; no automatic invoice payment.','#completion-evidence',6500)
    scene('SAVED INTEGRATION: USD 1 sandbox hold, USD 0.01 capture, separate 0.01 USDZ model charge. Customer closed; unused tokens retained.','#completion-evidence',6500)
    scene('HONEST STUDY STOP: clearing refusals and the credit guard left the matched comparison incomplete. Conservative API exposure stays below $3. No savings claim.','#completion-evidence',6000)
    scene('A signed fault statement binds checkable evidence. It does not reverse a charge or promise a refund.','#fault-summary',5000)
    scene('LOCAL TOOLS: supported sources need no model purchase; unfamiliar or ambiguous sources pause for review.','#planning',5000)
    page.locator('#start').click()
    page.wait_for_function("() => document.querySelectorAll('#payment-rows tr').length>=3")
    scene('SIMULATED THREE-JOB RUN: 2.50 USD in customer holds, 1.50 USD in operator float. Limits stay in code.','#jobs',5000)
    page.locator('#halt').click()
    idle()
    scene('Kill stops new dispatch. Any already dispatched attempt still needs reconciliation.','#notice',4000)
    page.locator('#resume').click()
    state=idle()
    scene('Resume preserves the approved limits. Jobs pause when policy or available float prevents further work.','#jobs',5000)
    scene('Every attempt stays visible. Confirmed charges are separate from quotes, reservations, and void attempts.','#transactions',5000)
    page.locator('.tx-chip[data-f="fail"]').click()
    scene('Rejected calls remain in the transaction history and retain their costs.',milliseconds=3500)
    page.locator('.tx-chip[data-f="all"]').click()
    page.locator('#tx-rows tr[data-key]').first.click()
    scene('The receipt drawer records the provider, mandate, quoted amounts, confirmed charges, and verification outcome.',milliseconds=4000)
    page.locator('#tx-close').click()
    page.locator('#close').click()
    idle()
    scene('SIMULATED SETTLEMENT: close accounts for every attempt, captures the agreed cost, and releases the unused hold.','#financial-story',5000)
    scene('Reproducible controls and saved measured proofs. Issuing writes, Visa onboarding and signed-in portal submission remain external requirements.', 'footer',5000)
    context.close()
    video.save_as(str(folder/'touchstone-demo.webm'))
    assert not errors and not external, 'Recording contains a script error or external asset request'
    (folder/'demo-transcript.md').write_text('# Touchstone demo recording\n\n'
        +'\n\n'.join(scenes)+'\n\nAll new financial activity in this recording is SIMULATED. No live purchase, conversion, card charge or hosted inference was sent.\n',encoding='utf-8')
    return {'file':'touchstone-demo.webm','transcript':'demo-transcript.md','scenes':len(scenes),
        'mode':'SIMULATED_UI_WITH_SEPARATELY_LABELLED_SAVED_PROOFS','financial_transactions':0,
        'hosted_inference_calls':0,'page_errors':errors,'external_requests':external}


def isolated_environment():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('AIRWALLEX_', 'METAL_', 'ANTHROPIC_', 'TOUCHSTONE_LIVE_'))
           and k != 'AGENT_PRIVATE_KEY'}
    env['TOUCHSTONE_IGNORE_LOCAL_CONFIG'] = '1'
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-landing', action='store_true')
    parser.add_argument('--record-demo',action='store_true',help='Record a captioned simulated workflow and transcript after the offline browser checks')
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
                recording=None
                if args.record_demo:
                    process.terminate();process.wait(timeout=10)
                    data=str(Path(data)/'recording')
                    process=start()
                    recording=record_demo(browser,base,folder)
                browser.close()
            report = {'label': 'MEASURED', 'scope': 'ISOLATED_SIMULATED_RELEASE',
                'sse_restart_reconnect': 'passed', 'old_process_token_rejected': True,
                'fresh_process_token_accepted': True, 'viewports': [[1440, 900], [390, 844]],
                'reduced_motion_on_and_off': 'passed', 'landing_built_and_checked': args.include_landing,
                'offline_loaded_page': 'passed', 'external_requests': external, 'page_errors': errors,
                'screenshots': captures, 'financial_transactions': 0}
            if recording:report['demo_recording']=recording
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
