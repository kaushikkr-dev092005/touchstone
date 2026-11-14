"""Offline browser QA for the shared site, cinematic intro, vault entry and private console embedding."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent.parent


def main():
    from playwright.sync_api import sync_playwright
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='tmp/site-design')
    args=parser.parse_args();folder=(ROOT/args.output).resolve();folder.mkdir(parents=True,exist_ok=True)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    base='http://127.0.0.1:'+str(port)
    errors=[];external=[]
    records=json.loads((ROOT/'apps/web/public/data/evidence.json').read_text())['records']
    charged_count=sum((r['costMicro'] or 0)>0 for r in records)
    unpaid_count=sum(r['state']=='Confirmed unpaid' for r in records)
    with tempfile.TemporaryDirectory(prefix='site-qa-',dir=folder) as data:
        process=subprocess.Popen([sys.executable,'tools/run_mock.py','--port',str(port),'--data-dir',data],cwd=ROOT,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(base+'/api/site-context',timeout=1).close();break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Isolated preview unavailable')
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True)
                context=browser.new_context(viewport={'width':1440,'height':1000})
                def route(r):
                    if urlsplit(r.request.url).hostname!='127.0.0.1':external.append(r.request.resource_type);r.abort()
                    elif urlsplit(r.request.url).path=='/api/site-context':r.fulfill(json={'operator_console':False,'mode':'SAVED_PUBLIC_EVIDENCE'})
                    else:r.continue_()
                context.route('**/*',route)
                # Full intro once: plays from black, can be skipped smoothly, and unmounts the vault.
                intro=context.new_page();intro.on('pageerror',lambda e:errors.append(str(e)))
                intro.goto(base+'/site/?intro=force',wait_until='domcontentloaded')
                assert intro.evaluate("() => document.documentElement.dataset.intro")=='full'
                intro.locator('.vault-sequence').wait_for(state='attached')
                intro.get_by_role('button',name='Skip intro').wait_for(state='visible',timeout=5000)
                intro.screenshot(path=str(folder/'intro-vault.png'))
                intro.keyboard.press('Escape')
                intro.wait_for_function("() => document.documentElement.dataset.intro==='done'",timeout=8000)
                assert intro.locator('.vault-sequence').count()==0,'Vault remains mounted after the intro'
                assert not intro.locator('.lp-hero').evaluate('e=>e.inert')
                intro.close()
                context.add_init_script("sessionStorage.setItem('ts-intro','1')")
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/site/',wait_until='networkidle')
                page.wait_for_function("() => document.documentElement.dataset.intro==='done'",timeout=8000)
                for width,height in [(1440,1000),(1024,900),(768,1024),(390,844),(320,740)]:
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(120)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Overflow at {width}'
                    assert page.get_by_role('heading',name='Buy inference. Prove it passes.').is_visible()
                    assert page.locator('.vault-sequence').count()==0
                    page.screenshot(path=str(folder/('landing-'+str(width)+'.png')))
                page.set_viewport_size({'width':1440,'height':1000})
                page.get_by_role('button',name='Open Dashboard',exact=True).click()
                page.locator('.vault-sequence').wait_for(state='attached')
                page.wait_for_timeout(2300);before=page.locator('#door-assembly').get_attribute('transform')
                page.screenshot(path=str(folder/'vault-opening.png'))
                page.wait_for_timeout(500);after=page.locator('#door-assembly').get_attribute('transform')
                assert before!=after,'Vault door did not animate'
                page.wait_for_url('**/dashboard',timeout=8000);page.locator('.vault-sequence').wait_for(state='detached',timeout=8000)
                assert page.get_by_role('heading',name='The control room.').is_visible()
                assert page.locator('.record-table tbody tr').count()==len(records)
                page.screenshot(path=str(folder/'dashboard-1440.png'))
                page.get_by_role('button',name='Transaction ledger',exact=True).click();page.wait_for_url('**/ledger')
                page.get_by_role('button',name='Charged',exact=True).click();assert page.locator('.record-table tbody tr').count()==charged_count
                page.get_by_role('button',name='Unpaid',exact=True).click();assert page.locator('.record-table tbody tr').count()==unpaid_count
                page.get_by_role('button',name='All attempts',exact=True).click()
                page.get_by_role('textbox',name='Search ledger').fill('no-such-receipt');assert page.locator('.record-table tbody tr').count()==0
                page.get_by_role('textbox',name='Search ledger').fill('')
                page.locator('.record-link').first.click();assert page.locator('.receipt-dialog').is_visible()
                page.keyboard.press('Escape');assert not page.locator('.receipt-dialog').is_visible()
                page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(folder/'ledger-390.png'))
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.get_by_role('button',name='Expand quick navigation',exact=True).click()
                page.wait_for_function("() => document.querySelector('.glass-dock').getBoundingClientRect().width>300")
                page.get_by_role('navigation',name='Quick navigation').get_by_role('link',name='Home',exact=True).click()
                page.wait_for_url('**/site/');page.wait_for_function("() => document.documentElement.dataset.intro==='done'",timeout=8000)
                page.get_by_role('button',name='Open navigation',exact=True).click();assert page.locator('#primary-nav').is_visible()
                page.keyboard.press('Escape');assert not page.locator('#primary-nav').is_visible()
                # Escape fast-forwards the Dashboard transition instead of cutting it.
                page.set_viewport_size({'width':1440,'height':1000})
                page.get_by_role('button',name='Open Dashboard',exact=True).click();page.locator('.vault-sequence').wait_for(state='attached')
                page.get_by_role('button',name='Skip',exact=True).wait_for(state='visible',timeout=4000)
                page.keyboard.press('Escape');page.wait_for_url('**/dashboard',timeout=4000)
                page.locator('.vault-sequence').wait_for(state='detached',timeout=4000)
                page.go_back();page.wait_for_function("() => document.documentElement.dataset.intro==='done'",timeout=8000)
                assert page.locator('.vault-sequence').count()==0
                page.emulate_media(reduced_motion='reduce')
                page.get_by_role('button',name='Open Dashboard',exact=True).click();page.wait_for_url('**/dashboard')
                assert not page.locator('.vault-sequence').count()
                page.go_back();page.wait_for_function("() => document.documentElement.dataset.intro==='done'",timeout=8000)
                assert page.locator('.lp-hero').is_visible()
                context.close()
                touch=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,reduced_motion='reduce')
                touch.route('**/*',route)
                phone=touch.new_page();phone.on('pageerror',lambda e:errors.append(str(e)))
                phone.goto(base+'/dashboard',wait_until='networkidle')
                phone.get_by_role('button',name='Expand quick navigation').tap()
                assert phone.get_by_role('navigation',name='Quick navigation').get_by_role('link',name='Ledger',exact=True).is_visible()
                phone.get_by_role('navigation',name='Quick navigation').get_by_role('link',name='Ledger',exact=True).tap()
                phone.wait_for_url('**/ledger')
                phone.get_by_role('button',name='Expand quick navigation').tap()
                phone.get_by_role('heading',name='Every attempt. On record.').tap()
                assert phone.locator('.dock-trigger').get_attribute('aria-expanded')=='false'
                touch.close()
                # Local operators retain their actual same-origin console and CSRF controls.
                local=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
                local.route('**/*',lambda r:r.continue_() if urlsplit(r.request.url).hostname=='127.0.0.1' else r.abort())
                operator=local.new_page();operator.on('pageerror',lambda e:errors.append(str(e)))
                operator.goto(base+'/dashboard',wait_until='domcontentloaded')
                frame=operator.frame_locator('iframe[title="Touchstone operator dashboard"]')
                frame.locator('[data-nav="overview"]').click()
                frame.locator('#start').wait_for(state='visible')
                frame.locator('#start').click()
                frame.locator('[data-nav="transactions"]').click()
                frame.locator('#payment-rows tr').first.wait_for()
                frame.locator('[data-nav="overview"]').click()
                frame.locator('#halt').click()
                operator.wait_for_function("async()=>!(await(await fetch('/api/state')).json()).worker_running")
                assert operator.request.post(base+'/api/demo',data={}).status==403
                assert "frame-ancestors 'none'" in operator.request.get(base+'/').headers['content-security-policy']
                assert "frame-ancestors 'self'" in operator.request.get(base+'/console').headers['content-security-policy']
                operator.set_viewport_size({'width':390,'height':844})
                assert operator.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert frame.locator('body').evaluate('document.documentElement.scrollWidth<=innerWidth')
                operator.screenshot(path=str(folder/'operator-console.png'))
                local.close();browser.close()
            assert not errors and not external
            report={'label':'MEASURED_OFFLINE_SITE_QA','viewports':[320,390,768,1024,1440],
                'intro_skip_and_vault_unmount':'passed','vault_opening_and_skip':'passed','same_origin_dashboard_and_ledger':'passed',
                'history_navigation':'passed','public_ledger_filters_and_receipt':'passed',
                'touch_dock_and_mobile_menu':'passed','reduced_motion':'passed','operator_iframe_and_csrf':'passed',
                'page_errors':errors,'external_requests':external,'financial_transactions':0,'model_calls':0}
            (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
        finally:
            process.terminate();process.wait(timeout=15)


if __name__=='__main__':main()
