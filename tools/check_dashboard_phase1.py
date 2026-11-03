"""Opt-in browser acceptance. Isolated mock ledger; no private data or credentials.

Requires the existing optional Playwright development installation and Chromium.
Run: python tools/check_dashboard_phase1.py
"""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / 'docs/evidence/design-phase1'
BASE = 'http://127.0.0.1:8093'


def serve_isolated(root):
    sys.path.insert(0, str(ROOT))
    import touchstone.server as server
    import touchstone.readiness as readiness
    import touchstone.procurement_evidence as procurement
    server.ROOT = readiness.ROOT = procurement.ROOT = Path(root)
    server.serve(port=8093, data_dir=Path(root) / 'mock-runtime')


def main():
    from playwright.sync_api import sync_playwright
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='touchstone-design-') as temporary:
        isolated = Path(temporary)
        # Copy only public tracked evidence and the current dashboard. Never data/ or .env.
        files = subprocess.check_output(['git', 'ls-files', 'bench', 'touchstone'], cwd=ROOT, text=True).splitlines()
        for name in ['apps/dashboard/index.html', *files]:
            source = ROOT / name
            if source.is_file():
                target = isolated / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        env = {key: value for key, value in os.environ.items() if key.upper() in {
            'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'COMSPEC', 'PATHEXT'}}
        env['TOUCHSTONE_IGNORE_LOCAL_CONFIG'] = '1'
        process = subprocess.Popen([sys.executable, __file__, '--serve', temporary], cwd=ROOT, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(BASE + '/api/state', timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise AssertionError('Isolated server did not start')
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={'width':1440,'height':900}, device_scale_factor=1)
                errors, external = [], []
                context.on('request', lambda request: external.append(request.url) if not request.url.startswith(BASE) else None)
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(BASE, wait_until='domcontentloaded')
                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
                page.wait_for_function("() => !document.getElementById('planning-summary').textContent.includes('Loading')")
                planning_status = page.request.get(BASE+'/api/procurement-evidence').json()['status']
                if planning_status == 'CURRENT':
                    page.wait_for_function("() => !document.getElementById('planning-case').disabled")
                    page.select_option('#planning-case',label='foreign currency')
                    assert page.locator('#planning-decision').inner_text() == 'Pause for review'
                else:
                    assert page.locator('#planning-case').is_disabled()
                assert page.locator('#measured-cost').inner_text() == '—'
                assert page.locator('h1').count() == 1
                assert page.locator('#float').inner_text() == '—'
                assert page.locator('#spent').inner_text() == '—'
                page.wait_for_function('() => introFinished')
                assert page.evaluate('starFrame===0'), 'Intro must stop requesting frames'
                page.evaluate("replayIntro();window.scrollTo({top:document.getElementById('overview').offsetTop,behavior:'instant'})")
                page.wait_for_function('() => !heroVisible && starFrame===0')
                assert page.locator('.horizon').evaluate("el=>getComputedStyle(el).animationPlayState") == 'paused'
                page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                def contrast_check():
                    return page.evaluate('''() => {
                      const lum=s=>{const c=s.match(/[\\d.]+/g).slice(0,3).map(Number).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return c[0]*.2126+c[1]*.7152+c[2]*.0722};
                      const pairs=[['ledger text','#overview','#overview'],['ledger secondary','.panel-description','#overview'],['gold figure','.node-icon','#overview'],['rejection','.fail, .is-failed','#overview'],['primary button','.hero-primary','.hero-primary'],['secondary button','.hero-secondary','.hero-secondary']];
                      return Object.fromEntries(pairs.map(([name,a,b])=>{const el=document.querySelector(a);if(!el)return[name,null];const x=lum(getComputedStyle(el).color),y=lum(getComputedStyle(document.querySelector(b)).backgroundColor);return[name,Number(((Math.max(x,y)+.05)/(Math.min(x,y)+.05)).toFixed(2))]}));
                    }''')
                contrast={'light':contrast_check()}
                assert all(value is None or value>=4.5 for value in contrast['light'].values())
                screenshots=[]
                def shot(name):
                    page.screenshot(path=str(ARTIFACTS / name), animations='allow')
                    screenshots.append(name)
                for width,height,label in [(1440,900,'desktop'),(390,844,'mobile')]:
                    page.set_viewport_size({'width':width,'height':height})
                    page.evaluate("window.scrollTo(0,0)")
                    page.wait_for_timeout(100)
                    page.evaluate('replayIntro()')
                    # Pause and seek the actual CSS animation for reproducible timeline captures.
                    # Screenshots are design inspection, not frame-rate evidence.
                    for ms in [0,1000,3000]:
                        page.evaluate('''ms=>{const a=document.querySelector('.horizon').getAnimations()[0];
                          if(a){a.pause();a.currentTime=Math.min(ms,2500);}starProgress=ms;paintStars();}''',ms)
                        if ms >= 2500:
                            page.evaluate('finishIntro()')
                            page.wait_for_timeout(350)
                        shot(f'{label}-ignition-{ms}ms.png')
                    page.evaluate("finishIntro();window.scrollTo({top:document.getElementById('overview').offsetTop,behavior:'instant'})")
                    page.wait_for_timeout(500)
                    shot(f'{label}-ledger.png')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'{label} overflow'
                page.set_viewport_size({'width':1440,'height':900})
                page.click('#theme-toggle')
                assert page.locator('body').get_attribute('data-theme') == 'dark'
                contrast['dark']=contrast_check()
                assert all(value is None or value>=4.5 for value in contrast['dark'].values())
                shot('desktop-ledger-dark.png')
                page.reload(wait_until='domcontentloaded')
                assert page.locator('body').get_attribute('data-theme') == 'dark'
                page.click('#theme-toggle')
                page.emulate_media(reduced_motion='reduce')
                page.evaluate('window.scrollTo(0,0);replayIntro()')
                page.wait_for_timeout(100)
                assert page.evaluate('starFrame===0')
                assert page.locator('.horizon').evaluate("el=>getComputedStyle(el).opacity") == '1'
                shot('desktop-ignition-reduced-motion.png')
                page.emulate_media(reduced_motion='no-preference')
                # The session token stays only in browser memory, never printed or persisted.
                assert page.request.post(BASE+'/api/demo',data={}).status == 403
                token=page.locator('meta[name="touchstone-token"]').get_attribute('content')
                assert page.request.post(BASE+'/api/demo',headers={'X-Touchstone-Token':token,'Origin':'https://untrusted.example'},data={}).status == 403
                request=urllib.request.Request(BASE+'/api/state',headers={'Host':'untrusted.example'})
                try:
                    urllib.request.urlopen(request,timeout=3)
                    raise AssertionError('Invalid Host accepted')
                except urllib.error.HTTPError as error:
                    assert error.code==403
                page.click('#hero-demo')
                page.wait_for_function("() => document.querySelectorAll('#payment-rows tr').length>=3")
                page.click('#halt')
                page.wait_for_function("() => document.body.dataset.eventLight==='kill'")
                page.wait_for_function("() => getComputedStyle(document.querySelector('.horizon-shift')).opacity==='0'")
                page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                shot('desktop-halted.png')
                def wait_state(predicate):
                    deadline=time.monotonic()+60
                    while time.monotonic()<deadline:
                        state=page.request.get(BASE+'/api/state').json()
                        if predicate(state):
                            return state
                        page.wait_for_timeout(200)
                    raise AssertionError('Mock workflow did not reach expected state')
                wait_state(lambda s:not s['worker_running'])
                page.click('#kill-resume')
                paused=wait_state(lambda s:not s['halted'] and not s['worker_running'] and len(s['jobs'])==3 and all(j['status']!='RUNNING' for j in s['jobs']))
                job=next(j for j in paused['jobs'] if j['status']=='PAUSED_POLICY')
                for field,value in {'job':job['id'],'version':str(job['mandate_version']),
                                    'hold':str((job['hold']+10000)/1e6),'budget':str((job['budget']+10000)/1e6),
                                    'cap':str(job['price_cap']/1e6),'allocation':str(job['allocation']/1e6),
                                    'approver':'Browser acceptance / MOCK','reason':'Isolated simulated UI validation'}.items():
                    page.fill('#mandate-'+field,value)
                page.click('#mandate-increase-form button[type="submit"]')
                page.wait_for_function("() => document.getElementById('mandate-approval-result').textContent.includes('approved')")
                approved=page.request.get(BASE+'/api/state').json()
                revised=next(j for j in approved['jobs'] if j['id']==job['id'])
                assert revised['mandate_version']==job['mandate_version']+1 and revised['status']=='PAUSED_POLICY'
                # A stale form version must produce a visible error, never another increase.
                page.click('#mandate-increase-form button[type="submit"]')
                page.wait_for_function("() => document.getElementById('mandate-approval-result').textContent.includes('version changed')")
                page.wait_for_function("() => !document.getElementById('close').disabled")
                page.click('#close')
                state=wait_state(lambda s:len(s['jobs'])==3 and all(j['status']=='COMPLETED' for j in s['jobs']))
                assert state['reconciliation']['matched'] and state['audit']['valid']
                assert all(j['captured']==j['spent'] and j['captured']+j['released']==j['hold'] for j in state['jobs'])
                page.locator('#flow').scroll_into_view_if_needed()
                page.click('[data-node="pay"]')
                assert page.locator('#evidence-drawer').is_visible()
                assert 'SIMULATED' in page.locator('#evidence-content').inner_text()
                page.keyboard.press('Escape')
                assert not page.locator('#evidence-drawer').is_visible()
                assert page.locator('[data-node="pay"]').evaluate('el=>el===document.activeElement')
                # Drop network, observe EventSource reconnect, and ensure replayed history is deduplicated.
                audit_count = page.request.get(BASE+'/api/audit').json()['audit']['events']
                page.wait_for_function('(count) => lastEvent===count',arg=audit_count)
                count=page.evaluate('eventHistory.length')
                await_before=page.evaluate('lastEvent')
                # Restart the isolated server to close an established SSE socket. Chromium's
                # offline flag alone does not reliably terminate existing localhost sockets.
                process.terminate()
                process.wait(timeout=10)
                page.wait_for_function("() => document.getElementById('connection').textContent==='RECONNECTING'")
                process = subprocess.Popen([sys.executable, __file__, '--serve', temporary], cwd=ROOT, env=env,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')",timeout=15000)
                page.wait_for_timeout(1200)
                assert page.evaluate('eventHistory.length')==count
                assert page.evaluate('lastEvent')==await_before
                assert page.evaluate("!document.body.classList.contains('event-pulse')")
                # Fully loaded dashboard remains usable without a network connection.
                context.set_offline(True)
                page.click('#theme-toggle')
                page.emulate_media(reduced_motion='reduce')
                page.evaluate("window.scrollTo(0,0);replayIntro()")
                assert page.evaluate('starFrame===0')
                context.set_offline(False)
                page.set_viewport_size({'width':390,'height':844})
                page.evaluate("window.scrollTo({top:document.getElementById('payments').offsetTop,behavior:'instant'})")
                shot('mobile-purchases.png')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                # A fixture checks the longer numeric layout; it is not saved as live evidence.
                page.evaluate("renderMeasuredCost({runs:[{policy:'real-touchstone',valid_live_evidence:true,reconciled:true,verified_correct_steps:2,steps:3,cost_per_verified_correct_micro_usd:15000,scope:'MOCK layout fixture'}]})")
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.evaluate('renderMeasuredCost({})')
                assert not errors,errors
                assert not external,external
                result={'label':'MEASURED browser checks / MOCK financial workflow','viewport_sizes':[[1440,900],[390,844]],
                        'html_bytes':(ROOT/'apps/dashboard/index.html').stat().st_size,'python_runtime_dependencies_added':0,
                        'html_sha256':hashlib.sha256((ROOT/'apps/dashboard/index.html').read_bytes()).hexdigest(),
                        'computed_text_contrast':contrast,
                        'browser':browser.version,'browser_errors':errors,'external_requests':external,'saved_planning_evidence':planning_status,
                        'checks':['empty metric gating','responsive overflow','theme persistence','reduced motion','token Origin Host rejection',
                                  'three-job demo','halt and resume','capture and release','reconciliation','audit chain','evidence drawer keyboard dismissal',
                                  'SSE reconnect and deduplication','offline controls','simulated mandate approval and stale-version error','drawer focus return',
                                  'intro animation shutdown','off-screen animation suspension'],
                        'screenshots':screenshots,'fps':'NOT MEASURED; headless Chromium is not an RTX 3050 performance qualification'}
                (ARTIFACTS/'browser-checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
                print(json.dumps(result,indent=2))
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--serve':
        serve_isolated(sys.argv[2])
    else:
        main()
