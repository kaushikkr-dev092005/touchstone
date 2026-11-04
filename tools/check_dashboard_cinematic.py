"""Isolated cinematic browser captures. Optional Playwright, OpenCV and Pillow only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'docs/evidence/cinematic'
BASE='http://127.0.0.1:8094'


def serve(root):
    sys.path.insert(0,str(ROOT))
    import touchstone.server as server
    import touchstone.readiness as readiness
    import touchstone.procurement_evidence as procurement
    server.ROOT=readiness.ROOT=procurement.ROOT=Path(root)
    server.serve(port=8094,data_dir=Path(root)/'mock-runtime')


def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image,ImageDraw
    import cv2
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='touchstone-cinema-') as temporary:
        root=Path(temporary)
        for name in ['apps/dashboard/index.html',*subprocess.check_output(['git','ls-files','bench','touchstone'],cwd=ROOT,text=True).splitlines()]:
            src=ROOT/name;dest=root/name
            if src.is_file():
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
        env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA','COMSPEC','PATHEXT'}}
        env['TOUCHSTONE_IGNORE_LOCAL_CONFIG']='1'
        proc=subprocess.Popen([sys.executable,__file__,'--serve',temporary],env=env,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:urllib.request.urlopen(BASE+'/api/state',timeout=1).close();break
                except OSError:time.sleep(.1)
            else:raise AssertionError('Isolated server failed to start')
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='msedge',headless=True,args=['--enable-gpu'])
                context=browser.new_context(viewport={'width':1440,'height':900},device_scale_factor=1,
                                           record_video_dir=str(root/'captures'),record_video_size={'width':1440,'height':900})
                page=context.new_page();errors=[];external=[];posts=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                context.on('request',lambda r:external.append(r.url) if not r.url.startswith(BASE) and not r.url.startswith('data:') else None)
                context.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
                page.goto(BASE,wait_until='domcontentloaded')
                page.wait_for_function('() => typeof TouchstoneCinema!=="undefined"')
                page.wait_for_function("() => document.getElementById('connection').textContent.includes('CONNECTED')")
                assert page.locator('#measured-cost').inner_text()=='—'
                screenshots=[];performance={}
                def snap(name):
                    page.screenshot(path=str(OUT/name));screenshots.append(name)
                def inspect(value):
                    target='ledger-gateway' if value['scene']=='gateway' else 'evidence-scene'
                    page.evaluate("id=>window.scrollTo({top:document.getElementById(id).offsetTop,behavior:'instant'})",target)
                    page.wait_for_timeout(100)
                    page.evaluate('value=>TouchstoneCinema.inspect(value)',value)
                    page.wait_for_timeout(900)
                page.wait_for_timeout(1200);snap('assay-ambient.png')
                page.wait_for_timeout(700)
                assert page.locator('.dia-word').evaluate("el=>getComputedStyle(el).color!=='rgba(0, 0, 0, 0)'")
                page.click('#hero-demo')
                page.wait_for_function('() => TouchstoneCinema.stats.demoPasses===3',timeout=20000)
                assert page.locator('.assay-pass-counter').inner_text().startswith('INSPECTED 3 / 3')
                snap('assay-three-passes.png')
                readiness_before=page.locator('#metal-health').inner_text()
                for state in range(4):
                    inspect({'scene':'specimen','morph':state,'wipe':0})
                    snap(f'specimen-{state}.png')
                    assert page.locator('#specimen-heading').inner_text()==['A job arrives','Every purchase leaves a record','Every result faces a test','Verdict'][state]
                    page.evaluate('TouchstoneCinema.sample(true)')
                    page.wait_for_timeout(2500)
                    performance[f'specimen-{state}']=page.evaluate('TouchstoneCinema.sample()')
                    if state==1:
                        page.evaluate('TouchstoneCinema.sample(true)')
                        for movement in range(24):
                            page.mouse.move(950+(movement%8)*20,350+(movement%5)*15)
                            page.wait_for_timeout(80)
                        performance['specimen-interacting']=page.evaluate('TouchstoneCinema.sample()')
                assert not page.evaluate('TouchstoneCinema.stats.shaderErrors')
                assert 'SIMULATED / MOCK' in page.locator('#graph-source').inner_text()
                assert page.locator('#graph-nodes').text_content().strip()
                assert page.locator('#metal-health').inner_text()==readiness_before
                inspect({'scene':'specimen','morph':2,'wipe':0})
                inspect({'scene':'specimen','morph':3,'wipe':0})
                assert 0<page.evaluate('TouchstoneCinema.stats.oreSweep')<1,'Ore sweep did not play on entry'
                page.wait_for_timeout(500)
                assert page.evaluate('TouchstoneCinema.stats.oreSweep')==1,'Ore sweep did not finish'
                page.locator('#halt').evaluate('el=>el.click()')
                page.wait_for_function("() => TouchstoneCinema.stats.suspended==='halted'")
                stopped=page.evaluate('TouchstoneCinema.stats.frames')
                page.wait_for_timeout(700)
                assert page.evaluate('TouchstoneCinema.stats.frames')==stopped,'Halt continued rendering'
                assert not page.locator('#cinema-canvas').evaluate("el=>el.classList.contains('is-rendering')")
                page.locator('#resume').evaluate('el=>el.click()')
                page.wait_for_function("() => TouchstoneCinema.stats.suspended===''&&TouchstoneCinema.stats.frames>"+str(stopped))
                for i,value in enumerate([.16,.36,.49,.68,.9]):
                    inspect({'scene':'specimen','morph':3,'wipe':value});snap(f'wipe-{i}.png')
                page.evaluate("TouchstoneCinema.inspect({scene:'specimen',morph:3,wipe:.2})")
                page.wait_for_timeout(80)
                page.evaluate("TouchstoneCinema.inspect({scene:'specimen',morph:3,wipe:.49})")
                page.wait_for_timeout(50);snap('transition-flash.png')
                page.wait_for_timeout(250)
                assert page.evaluate('TouchstoneCinema.stats.flash')==0,'Stopped scroll held the flash'
                # Reversal must reproduce S0 rather than retaining the ore or graph.
                inspect({'scene':'specimen','morph':0,'wipe':0})
                assert page.locator('#specimen-heading').inner_text()=='A job arrives'
                assert float(page.locator('#specimen-graph').evaluate('el=>getComputedStyle(el).opacity'))==0
                for glow in [0,.5,1]:
                    inspect({'scene':'gateway','glow':glow});snap(f'gateway-{glow}.png')
                page.evaluate('TouchstoneCinema.sample(true)');page.wait_for_timeout(2500);performance['gateway']=page.evaluate('TouchstoneCinema.sample()')
                assert page.locator('#cinema-canvas').count()==1
                page.set_viewport_size({'width':390,'height':844})
                inspect({'scene':'specimen','morph':2,'wipe':0});snap('mobile-specimen.png')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert page.locator('#graph-nodes text').first.evaluate('el=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<innerHeight&&r.left>=0&&r.right<=innerWidth;}'),'Mobile graph label left the viewport'
                inspect({'scene':'gateway','glow':1});snap('mobile-gateway.png')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.emulate_media(reduced_motion='reduce')
                inspect({'scene':'specimen','morph':3,'wipe':.49});snap('reduced-motion.png')
                before=page.evaluate('TouchstoneCinema.stats.frames');page.wait_for_timeout(500)
                assert page.evaluate('TouchstoneCinema.stats.frames')==before,'Reduced motion kept rendering'
                page.emulate_media(reduced_motion='no-preference')
                # Force context loss and check that the embedded, pre-rendered still is available.
                page.evaluate("() => {const gl=document.getElementById('cinema-canvas').getContext('webgl');window.testContextLoss=gl.getExtension('WEBGL_lose_context');window.testContextLoss.loseContext();}")
                page.wait_for_function("() => document.body.classList.contains('no-webgl')")
                assert page.locator('#specimen-still').evaluate('el=>el.complete&&el.naturalWidth>0')
                snap('webgl-fallback.png')
                page.wait_for_timeout(200)
                fallback_frames=page.evaluate('TouchstoneCinema.stats.draws')
                page.wait_for_timeout(500)
                assert page.evaluate('TouchstoneCinema.stats.draws')==fallback_frames,'Fallback kept drawing to WebGL'
                page.evaluate("window.testContextLoss.restoreContext()")
                page.wait_for_function("() => !document.body.classList.contains('no-webgl')&&TouchstoneCinema.stats.draws>"+str(fallback_frames))
                assert not page.evaluate('TouchstoneCinema.stats.shaderErrors')
                assert not errors,errors
                assert not external,external
                reduced=browser.new_context(viewport={'width':390,'height':844},reduced_motion='reduce')
                reduced_page=reduced.new_page();reduced_page.goto(BASE+'/?cinematic=1',wait_until='domcontentloaded')
                reduced_page.wait_for_function('() => typeof TouchstoneCinema!=="undefined"')
                assert not reduced_page.locator('body').evaluate("el=>el.classList.contains('cinematic-mode')"),'Reduced motion started cinematic playback'
                reduced.close()
                main_video=page.video
                context.close()
                main_video.save_as(str(OUT/'effects-capture.webm'))
                # Cinematic mode must not create a demo or authorize a payment.
                film_context=browser.new_context(viewport={'width':1440,'height':900},record_video_dir=str(root/'film'),record_video_size={'width':1440,'height':900})
                film=film_context.new_page();film_posts=[]
                film.on('request',lambda r:film_posts.append(r.url) if r.method=='POST' else None)
                film.goto(BASE+'/?cinematic=1',wait_until='domcontentloaded');film.wait_for_timeout(1000)
                assert film.locator('body').evaluate("el=>el.classList.contains('cinematic-mode')")
                assert not film_posts
                film.wait_for_function("() => !document.body.classList.contains('cinematic-mode')",timeout=60000)
                assert not film.locator('body').evaluate("el=>el.classList.contains('cinematic-mode')")
                assert not film_posts
                film_video=film.video;film_context.close();film_video.save_as(str(OUT/'cinematic-capture.webm'));browser.close()
                result={'label':'MEASURED local browser / SIMULATED financial data','browser':'Microsoft Edge / headless hardware WebGL',
                        'viewport':[1440,900],'device_pixel_ratio':1,'html_sha256':hashlib.sha256((root/'apps/dashboard/index.html').read_bytes()).hexdigest(),
                        'performance':performance,'page_errors':errors,'external_requests':external,'financial_posts':'only explicitly clicked MOCK demo, halt and resume',
                        'cinematic_posts':film_posts,'screenshots':screenshots,
                        'lifecycle_checks':['one-time ore sweep','halt suspends render loop','resume wakes renderer','context loss stops GPU draws','context restoration rebuilds renderer','reduced motion disables cinematic autoplay'],
                        'limits':'FPS includes video capture and other local GPU load; Intel integrated GPU, not RTX 3050 with llama.cpp. A 60fps target is not a guarantee.'}
                (OUT/'browser-checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
                print(json.dumps(result,indent=2))
            # A timestamped sheet uses the same sampling/tile idea as the supplied ffmpeg commands.
            video=cv2.VideoCapture(str(OUT/'effects-capture.webm'));count=video.get(cv2.CAP_PROP_FRAME_COUNT);fps=video.get(cv2.CAP_PROP_FPS);duration=count/fps
            sheet=Image.new('RGB',(1280,6*220),'#151515');draw=ImageDraw.Draw(sheet)
            for i in range(24):
                stamp=duration*i/24;video.set(cv2.CAP_PROP_POS_MSEC,stamp*1000);ok,frame=video.read()
                if ok:
                    image=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));image.thumbnail((320,195));x=i%4*320;y=i//4*220;sheet.paste(image,(x,y+22));draw.text((x+6,y+4),f'{stamp:.2f}s',fill='white')
            video.release();sheet.save(OUT/'capture-sheet.jpg',quality=85)
        finally:
            proc.terminate();proc.wait(timeout=10)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--serve':serve(sys.argv[2])
    else:main()
