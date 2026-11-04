"""Inline the editable cinematic sources; serving still needs only index.html."""
from pathlib import Path
import re
import base64

ROOT = Path(__file__).resolve().parent.parent
page = ROOT / 'apps/dashboard/index.html'
html = page.read_text(encoding='utf-8')
for suffix, end in [('css', '</style>'), ('js', '</script>')]:
    start, stop = f'/* cinematic-{suffix}:start */', f'/* cinematic-{suffix}:end */'
    source = (ROOT / f'apps/dashboard/cinematic.{suffix}').read_text(encoding='utf-8')
    if suffix == 'js':
        still = ROOT / 'apps/dashboard/specimen-fallback.webp'
        source = source.replace('__SPECIMEN_STILL__', 'data:image/webp;base64,' + base64.b64encode(still.read_bytes()).decode() if still.exists() else '')
    block = start + '\n' + source + '\n' + stop
    pattern = re.escape(start) + r'[\s\S]*?' + re.escape(stop)
    html = re.sub(pattern, lambda _: block, html) if start in html else html.replace(end, block + '\n' + end, 1)
page.write_text(html, encoding='utf-8')
