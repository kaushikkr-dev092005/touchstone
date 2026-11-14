"""The public dashboard shares the current design without operator authority."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent


class PublicDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.build_public_dashboard import build
        build()
        cls.folder = ROOT/'apps/web/public/dashboard'
        cls.html = (cls.folder/'index.html').read_text(encoding='utf-8')

    def test_design_is_the_canonical_console(self):
        original = (ROOT/'apps/dashboard/index.html').read_text(encoding='utf-8')
        for style in re.findall(r'<style>(.*?)</style>', original, re.S):
            self.assertIn(style, self.html)
        for view in ('overview','transactions','spend','approvals','evidence','integrations'):
            self.assertIn('id="v-'+view+'"', self.html)
        report=json.loads((self.folder/'reports.json').read_text())
        self.assertEqual(report['console_sha256'], hashlib.sha256(original.encode()).hexdigest())

    def test_no_operator_scripts_or_inline_execution(self):
        self.assertNotIn('{{TOKEN}}', self.html)
        self.assertNotIn('touchstone-token', self.html)
        self.assertNotIn('/procurement.js', self.html)
        scripts = re.findall(r'<script\b([^>]*)>(.*?)</script>', self.html, re.S)
        self.assertEqual(len(scripts),1)
        self.assertEqual(scripts[0][1], '')
        script=next(self.folder.glob('public-evidence-*.mjs')).read_text(encoding='utf-8')
        for forbidden in ('/api/', 'EventSource', 'eth_signTypedData', 'AGENT_PRIVATE_KEY', "method:'POST'", 'setInterval'):
            self.assertNotIn(forbidden,script)
        self.assertIn("disabled = ['start','halt','resume','close'",script)

    def test_saved_financial_units_and_comparison_preserved(self):
        reports=json.loads((self.folder/'reports.json').read_text())
        self.assertEqual(reports['scope'],'SAVED_PUBLIC_EVIDENCE')
        original=json.loads((ROOT/'bench/results/m4-live-20261112/actual-financial-results.json').read_text())
        self.assertEqual(reports['comparison'],original)
        self.assertEqual(reports['comparison']['completed_outcomes'],64)
        self.assertEqual(reports['comparison']['provider_micro_usdz'],263390)
        self.assertNotIn('account_fingerprint',reports['fx'])
        self.assertNotIn('card_id',reports['card'])

    def test_saved_call_decision_belongs_to_that_purchase(self):
        # Escalation outputs must not borrow another policy/call's final decision.
        from tools import build_site_evidence
        build_site_evidence.build()
        public=json.loads((ROOT/'apps/web/public/data/evidence.json').read_text())
        raw=json.loads((ROOT/'bench/results/m4-live-20261112/live-report.json').read_text())
        calls={c['reservation_key']:c for c in raw['calls'].values()}
        for row in public['records'][1:]:
            call=calls[row['purchaseKey']]
            self.assertEqual(row['policy'],call['policy'])
            if row['state']=='Confirmed unpaid':
                self.assertEqual(row['costMicro'],0)
                continue
            matched=next((r for r in raw['rows'] if call['reservation_key'] in r.get('calls',[])),None)
            self.assertEqual(row['verification'],matched['decision'] if matched else 'UNRESOLVED')


if __name__=='__main__':unittest.main()
