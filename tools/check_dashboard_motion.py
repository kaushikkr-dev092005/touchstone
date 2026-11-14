"""Optional isolated visual QA; --record needs Playwright, OpenCV and Pillow."""
import argparse
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--record',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent;folder=root/'tmp/dashboard-redesign';folder.mkdir(parents=True,exist_ok=True)
with socket.socket() as probe:
    probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
base=f'http://127.0.0.1:{port}'
env={k:v for k,v in os.environ.items() if not k.startswith(('AIRWALLEX_','METAL_','ANTHROPIC_')) and k!='AGENT_PRIVATE_KEY'}
env['TOUCHSTONE_IGNORE_LOCAL_CONFIG']='1'
with tempfile.TemporaryDirectory(prefix='dashboard-style-',dir=folder) as data:
    process=subprocess.Popen([sys.executable,'-m','touchstone','serve','--port',str(port),'--data-dir',data],cwd=root,env=env,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        for _ in range(100):
            try:urllib.request.urlopen(base+'/api/state',timeout=1).close();break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Isolated dashboard did not start')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
            errors=[];external=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:external.append(request.url) if urlparse(request.url).hostname!='127.0.0.1' else None)
            page.goto(base,wait_until='domcontentloaded')
            page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
            page.wait_for_timeout(2300)
            stats=page.evaluate("({fps:document.getElementById('starfield').dataset.fps,render_ms:document.getElementById('starfield').dataset.renderMs,quality:document.getElementById('starfield').dataset.quality,particles:particleLimit})")
            page.click('#motion-toggle')
            assert page.locator('#motion-toggle').get_attribute('aria-pressed')=='true'
            paused=page.evaluate('starProgress');page.wait_for_timeout(100);assert page.evaluate('starProgress')==paused
            for phase,time_ms in [('starburst',600),('horizon',1800)]:
                page.evaluate('(time)=>{starProgress=time;paintStars()}',time_ms)
                page.screenshot(path=str(folder/f'desktop-{phase}.png'))
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('#console').scroll_into_view_if_needed();page.wait_for_timeout(400)
            assert page.evaluate('starFrame')==0
            page.screenshot(path=str(folder/'desktop-ledger.png'))
            # The current console is dark-only; verify the actual scheme rather
            # than clicking the removed legacy theme switch.
            assert 'dark' in page.locator('html').evaluate('e=>getComputedStyle(e).colorScheme')
            page.screenshot(path=str(folder/'desktop-ledger-dark.png'))
            page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(300)
            page.click('#motion-toggle');page.wait_for_timeout(150)
            assert page.evaluate('starFrame')!=0
            page.keyboard.press('l');assert page.evaluate('starProgress')<150
            page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
            page.locator('body').click(position={'x':2,'y':2})
            page.evaluate('motionPaused=true;scheduleStars();starProgress=1800;paintStars()')
            page.screenshot(path=str(folder/'mobile-horizon.png'))
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('#console').scroll_into_view_if_needed();page.wait_for_timeout(150)
            page.screenshot(path=str(folder/'mobile-ledger.png'))
            page.emulate_media(reduced_motion='reduce');page.reload(wait_until='domcontentloaded')
            page.wait_for_timeout(600)
            assert page.evaluate('starFrame')==0
            assert page.locator('#motion-toggle').is_disabled()
            page.screenshot(path=str(folder/'mobile-reduced.png'))
            assert not errors and not external
            report={'label':'MEASURED','scope':'ISOLATED_SIMULATED_DASHBOARD','desktop':[1440,900],'mobile':[390,844],
                'particle_preview':stats,'fps_environment':'HEADLESS_CHROMIUM_WINDOWS_NOT_A_HARDWARE_GUARANTEE',
                'pause_replay_offscreen_reduced_motion':'passed','current_dark_scheme':'passed',
                'horizontal_overflow':False,'page_errors':errors,'external_requests':external,'financial_transactions':0}
            if args.record:
                movie_context=browser.new_context(viewport={'width':1440,'height':900},
                    record_video_dir=str(folder/'video'),record_video_size={'width':1280,'height':800})
                movie=movie_context.new_page();video=movie.video
                movie.goto(base,wait_until='domcontentloaded');movie.wait_for_timeout(5400)
                movie_context.close();video.save_as(str(folder/'dashboard-motion.webm'))
                import cv2
                from PIL import Image,ImageDraw
                capture=cv2.VideoCapture(str(folder/'dashboard-motion.webm'))
                contact=Image.new('RGB',(4*480,3*190),'#111');draw=ImageDraw.Draw(contact)
                for index in range(12):
                    capture.set(cv2.CAP_PROP_POS_MSEC,index*.45*1000)
                    ok,frame=capture.read()
                    if not ok:continue
                    crop=frame[int(frame.shape[0]*.43):int(frame.shape[0]*.87),:]
                    im=Image.fromarray(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB));im.thumbnail((480,165))
                    x=(index%4)*480;y=(index//4)*190
                    draw.text((x+8,y+5),f'{index*.45:.2f}s',fill='white');contact.paste(im,(x,y+23))
                capture.release();contact.save(folder/'motion-contact-sheet.png')
                report['recording']='dashboard-motion.webm'
                report['recording_contact_sheet']='motion-contact-sheet.png'
            (folder/'review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(report))
            browser.close()
    finally:process.terminate();process.wait(timeout=10)
