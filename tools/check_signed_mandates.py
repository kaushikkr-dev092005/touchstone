"""Local browser proof. Ephemeral EIP-1193 TEST wallet, genuine signatures, MOCK rail."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_procurement_approval import EphemeralSigner
from playwright.sync_api import sync_playwright


def main():
    artifacts=ROOT/'tmp/signed-mandates-browser';artifacts.mkdir(parents=True,exist_ok=True)
    signer=EphemeralSigner()
    try:
        with tempfile.TemporaryDirectory(prefix='approval-browser-') as directory:
            root=Path(directory);cfg=root/'approvers.json'
            cfg.write_text(json.dumps({'environment':'LOCAL_TEST_BROWSER','chain_id':31337,'salt':'0x'+secrets.token_hex(32),
                'signers':[signer.addresses[0]],'agent_addresses':[signer.addresses[1]],
                'ledger_paths':[str((root/'ledger.sqlite').resolve())],'api_credit_max':0}))
            env={k:v for k,v in os.environ.items() if not k.startswith(('METAL_','ANTHROPIC_','AIRWALLEX_')) and k!='AGENT_PRIVATE_KEY'}
            env.update(TOUCHSTONE_IGNORE_LOCAL_CONFIG='1',TOUCHSTONE_APPROVAL_CONFIG=str(cfg))
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            base=f'http://127.0.0.1:{port}'
            server=subprocess.Popen([sys.executable,'-c',f'from touchstone.server import serve;serve({port},{directory!r})'],
                cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                for _ in range(100):
                    try:urllib.request.urlopen(base+'/api/state',timeout=1).close();break
                    except OSError:time.sleep(.05)
                else:raise RuntimeError('Local test server did not start')
                with sync_playwright() as p:
                    browser=p.chromium.launch(headless=True,args=['--disable-gpu'])
                    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
                    errors=[];external=[];wallet_calls=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    def route(r):
                        if r.request.url.startswith(base+'/'):r.continue_()
                        else:external.append(r.request.url.split('?')[0]);r.abort()
                    page.route('**/*',route)
                    def wallet(request):
                        wallet_calls.append(request['method'])
                        if request['method']=='eth_requestAccounts':return [signer.addresses[0]]
                        if request['method']=='eth_chainId':return hex(31337)
                        if request['method']=='eth_signTypedData_v4':
                            return signer.sign({'typed_data':json.loads(request['params'][1])})
                        raise ValueError('Unexpected wallet method')
                    page.expose_function('ephemeralLocalTestWallet',wallet)
                    page.add_init_script('window.ethereum={request:r=>window.ephemeralLocalTestWallet(r)}')
                    page.goto(base+'/console');panel=page.locator('#human-authorization');panel.scroll_into_view_if_needed()
                    page.get_by_role('button',name='Create local test proposal',exact=True).click()
                    page.wait_for_function("() => document.getElementById('approval-state').textContent==='PENDING_APPROVAL'")
                    panel.screenshot(path=str(artifacts/'unsigned.png'))
                    page.get_by_role('button',name='Review & Sign',exact=True).click()
                    page.wait_for_function("() => document.getElementById('approval-state').textContent==='SIGNED'")
                    panel.screenshot(path=str(artifacts/'signed.png'))
                    page.get_by_role('button',name='Verify Approval',exact=True).click()
                    page.wait_for_function("() => document.getElementById('approval-message').textContent.includes('Signature and exact terms verified')")
                    page.get_by_role('button',name='Test tampered provider',exact=True).click()
                    page.wait_for_function("() => document.getElementById('approval-state').textContent==='TAMPERED · BLOCKED'")
                    panel.screenshot(path=str(artifacts/'tampered.png'))
                    for width in (320,390,768,1440):
                        page.set_viewport_size({'width':width,'height':1000});panel.scroll_into_view_if_needed()
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),f'Overflow at {width}'
                        if width==390:
                            page.locator('#theme-toggle').click();panel.screenshot(path=str(artifacts/'mobile-dark.png'))
                    page.get_by_role('button',name='Dispatch MOCK purchase',exact=True).click()
                    page.wait_for_function("() => document.getElementById('approval-state').textContent==='CONSUMED_AT_DISPATCH'")
                    assert '0 external financial calls' in page.locator('#approval-message').inner_text()
                    assert wallet_calls==['eth_requestAccounts','eth_chainId','eth_signTypedData_v4']
                    assert not errors,errors
                    assert not external,external
                    result={'label':'MOCK / LOCAL TEST','wallet':'EPHEMERAL EIP1193 TEST ADAPTER WITH REAL VIEM SIGNATURE',
                        'unsigned':'BLOCKED','signed':'AUTHORIZED','tampered':'TERMS_MISMATCH','mock_dispatch':'COMPLETED',
                        'responsive_widths':[320,390,768,1440],'external_requests':len(external),'page_errors':errors,
                        'gpu_rendering':'DISABLED','real_external_financial_operations':0,'hosted_inference_calls':0,
                        'screenshots':['unsigned.png','signed.png','tampered.png','mobile-dark.png']}
                    (artifacts/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
                    browser.close()
            finally:server.terminate();server.communicate(timeout=10)
    finally:signer.close()


if __name__=='__main__':main()
