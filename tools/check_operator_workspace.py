"""Real local authenticated jobs/SSE/restart browser check. No financial credentials."""
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
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.operator_auth import make_config


def main():
    from playwright.sync_api import sync_playwright
    artifacts=ROOT/'tmp/operator-browser';artifacts.mkdir(parents=True,exist_ok=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('AIRWALLEX_','METAL_','ANTHROPIC_','TOUCHSTONE_')) and k!='AGENT_PRIVATE_KEY'}
    env['TOUCHSTONE_IGNORE_LOCAL_CONFIG']='1'
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='operator-qa-',dir=artifacts) as folder:
        directory=Path(folder);config=directory/'config.json';password=secrets.token_urlsafe(24)
        config.write_text(json.dumps(make_config(base,'operator',password)))
        def start():
            process=subprocess.Popen([sys.executable,'tools/run_operator.py','serve','--config',str(config),
                '--data-dir',str(directory/'jobs'),'--port',str(port)],cwd=ROOT,env=env,
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            for _ in range(100):
                try:urllib.request.urlopen(base+'/healthz',timeout=1).close();return process
                except OSError:time.sleep(.1)
            process.terminate();process.wait(timeout=5);raise RuntimeError('Operator service failed to start')
        server=start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,args=['--disable-gpu'])
                context=browser.new_context(viewport={'width':1440,'height':1000})
                external=[];errors=[]
                def route(r):
                    if urlsplit(r.request.url).hostname=='127.0.0.1':r.continue_()
                    else:external.append(r.request.url.split('?')[0]);r.abort()
                context.route('**/*',route)
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/control-room')
                assert page.request.get(base+'/operator-api/jobs').status==401
                page.get_by_label('Username',exact=True).fill('operator')
                page.get_by_label('Password',exact=True).fill(password)
                page.get_by_role('button',name='Sign in',exact=True).click()
                page.get_by_role('button',name='Create backend job',exact=True).wait_for()
                page.get_by_role('button',name='Create backend job',exact=True).click()
                page.get_by_role('button',name='Start zero-charge processing',exact=True).click()
                page.wait_for_function("() => document.querySelector('.cr-panel pre')?.textContent.includes('2000')")
                assert page.request.get(base+'/operator-api/jobs').json()['jobs'][0]['state']=='COMPLETED'
                page.get_by_text('JOB_COMPLETED',exact=False).first.wait_for()
                page.screenshot(path=str(artifacts/'completed.png'),full_page=True)
                page.reload()
                page.get_by_role('button',name='arithmetic',exact=False).first.wait_for()
                assert len(page.request.get(base+'/operator-api/jobs').json()['jobs'])==1
                # Database and hashed server-side session survive a real process restart.
                server.terminate();server.wait(timeout=5);server=start()
                page.reload();page.get_by_role('button',name='arithmetic',exact=False).first.wait_for()
                state=page.request.get(base+'/operator-api/jobs').json()
                assert state['jobs'][0]['output']=={'total_cents':2000}
                assert state['audit']['valid'] is True
                widths=[]
                for width in (320,390,768,1440):
                    page.set_viewport_size({'width':width,'height':1000})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),width
                    widths.append(width)
                page.set_viewport_size({'width':390,'height':1000})
                page.screenshot(path=str(artifacts/'mobile.png'),full_page=True)
                page.get_by_role('button',name='Sign out',exact=True).click()
                page.get_by_role('button',name='Sign in',exact=True).wait_for()
                assert page.request.get(base+'/operator-api/jobs').status==401
                assert not external,external
                assert not errors,errors
                report={'label':'MEASURED_LOCAL_OPERATIONAL_NO_SPEND','authenticated_job_creation':True,
                    'actual_local_tool_output':{'total_cents':2000},'actual_backend_events':True,
                    'browser_refresh_persistence':True,'backend_restart_persistence':True,'audit_valid':True,
                    'session_revocation':True,'responsive_widths':widths,'external_requests':0,'page_errors':[],
                    'financial_operations':0,'model_calls':0,'gpu_rendering':'DISABLED_FOR_HEADLESS_TEST',
                    'public_deployment_verified':False}
                (artifacts/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
                print(json.dumps(report,indent=2));browser.close()
        finally:server.terminate();server.wait(timeout=10)


if __name__=='__main__':main()
