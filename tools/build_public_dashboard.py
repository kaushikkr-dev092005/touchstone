"""Build a read-only projection of the canonical console, never its operator scripts."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def build():
    source = (ROOT/'apps/dashboard/index.html').read_text(encoding='utf-8')
    # Keep the current design in one place. None of the console's API, wallet,
    # session-token or SSE code is shipped to anonymous visitors.
    page = re.sub(r'<script\b[^>]*>.*?</script>', '', source, flags=re.S)
    page = re.sub(r'<meta name="touchstone-token"[^>]*>', '', page)
    page = page.replace('<body', '<body data-public-evidence="true"', 1)
    page = page.replace('aria-pressed="false">Accepted</button>', 'aria-pressed="false">Candidate</button>')
    page = page.replace('aria-pressed="false">In flight</button>', 'aria-pressed="false">Review / unresolved</button><button type="button" class="btn tx-chip" data-f="void" aria-pressed="false">Confirmed unpaid</button>')
    page = page.replace('href="/api/audit"', 'href="/site/dashboard/reports.json"')
    page = page.replace('Open audit JSON', 'Open saved evidence JSON')
    page = page.replace('</head>', '<style>.cinematic-hero{display:none}button[disabled]{cursor:not-allowed}</style></head>')
    script = (ROOT/'apps/dashboard/public-evidence.mjs').read_bytes()
    name = 'public-evidence-'+hashlib.sha256(script).hexdigest()[:16]+'.mjs'
    page = page.replace('</body>', f'<script type="module" src="/site/dashboard/{name}"></script></body>')
    assert '{{TOKEN}}' not in page and '/procurement.js' not in page
    folder = ROOT/'apps/web/public/dashboard'
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob('public-evidence-*.mjs'):
        old.unlink()
    (folder/name).write_bytes(script)
    (folder/'index.html').write_text(page, encoding='utf-8')

    from touchstone.invoice_study import dashboard
    from touchstone.procurement_evidence import summary
    # These readers use committed evidence only: no local configuration,
    # private database, credential lookup, telemetry, SDK or network call.
    def saved(path):
        return json.loads((ROOT/path).read_text(encoding='utf-8'))
    report = {
        'scope': 'SAVED_PUBLIC_EVIDENCE',
        'console_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'completion': saved('bench/results/m4-live-20261112/completion-status.json'),
        'comparison': saved('bench/results/m4-live-20261112/actual-financial-results.json'),
        'simulated': saved('bench/results/simulated.json'),
        'invoice': dashboard(ROOT/'bench/results/m3-v2'),
        'planning': summary(),
    }
    card = saved('bench/results/completion-20261110/issuing-proof.json')['card']
    fx = saved('bench/results/m1/live-fx-single-conversion.json')['conversion']
    fault = saved('bench/results/completion-20261110/current-seller-fault-acknowledgement.json')
    ack = fault.get('acknowledgement') or {}
    report.update(card={key: card.get(key) for key in ('controls_verified', 'authorization_controls', 'merchant_payment_completed', 'visa_approved_agent')},
                  fx={key: fx.get(key) for key in ('status', 'sell_amount', 'sell_currency', 'buy_amount', 'buy_currency', 'conversion_id')},
                  fault={'root': fault.get('root'), 'signature_verified': fault.get('seller_ack_signature_verified'),
                         'decision': ack.get('decision'), 'credit_status': ack.get('credit_status')})
    (folder/'reports.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    chart = ROOT/'bench/results/noisy-verification.svg'
    if chart.is_file():
        (folder/'noisy-verification.svg').write_bytes(chart.read_bytes())
    # The old console chart URL must never reach an operator endpoint publicly.
    page = page.replace('/api/noisy-verification-chart', '/site/dashboard/noisy-verification.svg')
    (folder/'index.html').write_text(page, encoding='utf-8')
    return {'canonical_console': 'apps/dashboard/index.html', 'operator_scripts_included': False,
            'network_calls': 0, 'financial_operations': 0}


if __name__ == '__main__':
    print(json.dumps(build()))
