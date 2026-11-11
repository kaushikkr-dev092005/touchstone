"""Offline browser QA for the shared site, vault entry and private console embedding."""
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
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/site/',wait_until='networkidle')
                for width,height in [(1440,1000),(1024,900),(768,1024),(390,844),(320,740)]:
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(80)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Overflow at {width}'
                    assert page.locator('.hero-locker .vault-svg').is_visible()
                    page.screenshot(path=str(folder/('landing-'+str(width)+'.png')))
                page.set_viewport_size({'width':1440,'height':1000})
                page.get_by_role('button',name='Open dashboard',exact=True).click()
                portal=page.get_by_role('dialog',name='Opening dashboard');portal.wait_for(state='visible')
                page.wait_for_timeout(500);before=page.locator('.vault-portal .vault-focus').get_attribute('cx')
                page.screenshot(path=str(folder/'vault-opening.png'))
                page.wait_for_timeout(700);after=page.locator('.vault-portal .vault-focus').get_attribute('cx')
                assert before!=after,'Original vault door did not animate'
                page.wait_for_url('**/dashboard');assert page.get_by_role('heading',name='The control room.').is_visible()
                assert page.locator('.record-table tbody tr').count()==9
                page.screenshot(path=str(folder/'dashboard-1440.png'))
                page.get_by_role('button',name='Transaction ledger',exact=True).click();page.wait_for_url('**/ledger')
                page.get_by_role('button',name='Charged',exact=True).click();assert page.locator('.record-table tbody tr').count()==4
                page.get_by_role('button',name='Unpaid',exact=True).click();assert page.locator('.record-table tbody tr').count()==5
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
                page.wait_for_url('**/site/')
                page.get_by_role('button',name='Open navigation',exact=True).click();assert page.locator('#primary-nav').is_visible()
                page.keyboard.press('Escape');assert not page.locator('#primary-nav').is_visible()
                page.get_by_role('button',name='Explore the ledger',exact=True).click();portal=page.get_by_role('dialog',name='Opening ledger');portal.wait_for(state='visible')
                page.keyboard.press('Escape');assert page.url.endswith('/site/') and not page.locator('.vault-portal').count()
                page.emulate_media(reduced_motion='reduce')
                page.get_by_role('button',name='Open dashboard',exact=True).click();page.wait_for_url('**/dashboard')
                assert not page.locator('.vault-portal').count()
                page.go_back();assert page.locator('.hero-locker').is_visible()
                context.close()
                touch=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True,reduced_motion='reduce')
                touch.route('**/*',route)
                phone=touch.new_page();phone.on('pageerror',lambda e:errors.append(str(e)))
                phone.goto(base+'/site/',wait_until='networkidle')
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
                frame.locator('#start').wait_for(state='visible')
                frame.locator('#start').click();frame.locator('#payment-rows tr').first.wait_for()
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
                'vault_opening_and_cancel':'passed','same_origin_dashboard_and_ledger':'passed',
                'history_navigation':'passed','public_ledger_filters_and_receipt':'passed',
                'touch_dock_and_mobile_menu':'passed','reduced_motion':'passed','operator_iframe_and_csrf':'passed',
                'page_errors':errors,'external_requests':external,'financial_transactions':0,'model_calls':0}
            (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
        finally:
            process.terminate();process.wait(timeout=15)


if __name__=='__main__':main()
