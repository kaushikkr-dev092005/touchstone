import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from touchstone import readiness


class ReadinessAccountTests(unittest.TestCase):
    def observe(self, observation_account, hold_account=None, fx_account=None, card_account=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'data').mkdir()
            (root/'bench/results').mkdir(parents=True)
            digest = lambda s: hashlib.sha256(s.encode()).hexdigest()
            (root/'data/airwallex-readiness.json').write_text(json.dumps({
                'authenticated': True, 'balance_read': True, 'account_fingerprint': digest(observation_account)}))
            hold = {'failure': {'code': 'configuration_error'}}
            if hold_account:
                hold['account_fingerprint'] = digest(hold_account)
            (root/'bench/results/airwallex-hold-proof.json').write_text(json.dumps(hold))
            (root/'bench/results/m1').mkdir()
            if fx_account:
                (root/'bench/results/m1/live-fx-single-conversion.json').write_text(json.dumps({
                    'label': 'MEASURED', 'account_fingerprint': digest(fx_account),
                    'reconciliation': 'MATCHED_WALLET_HISTORY', 'conversion': {'status': 'SETTLED'}}))
            if card_account:
                (root/'bench/results/m1/current-hosted-card-proof.json').write_text(json.dumps({
                    'label': 'MEASURED', 'account_fingerprint': digest(card_account),
                    'result': {'complete': True, 'operator_capture_recorded': True,
                               'payment_status': 'SUCCEEDED', 'captured_micro_usd': 10000}}))
            with patch.object(readiness, 'ROOT', root), patch('touchstone.config.load_local'), \
                 patch.dict(os.environ, {'AIRWALLEX_ACCOUNT_ID': 'acct_current'}, clear=True):
                return readiness.inspect()['airwallex']

    def test_old_account_cannot_claim_current_authentication(self):
        report = self.observe('acct_old')
        self.assertFalse(report['authenticated'])
        self.assertFalse(report['observation_matches_account'])

    def test_matching_account_keeps_measured_reads(self):
        report = self.observe('acct_current')
        self.assertTrue(report['authenticated'])
        self.assertTrue(report['balance_read'])

    def test_unbound_historical_hold_error_is_not_a_current_merchant_verdict(self):
        report = self.observe('acct_current')
        self.assertEqual(report['hold_workflow'], 'HISTORICAL_MERCHANT_CONFIGURATION_ERROR')
        self.assertIsNone(report['hold_error'])

    def test_matching_hold_error_remains_blocked(self):
        report = self.observe('acct_current', 'acct_current')
        self.assertEqual(report['hold_workflow'], 'BLOCKED_MERCHANT_CONFIGURATION')

    def test_fx_proof_requires_the_same_account(self):
        self.assertEqual(self.observe('acct_current', fx_account='acct_old')['fx_proof']['status'], 'UNVERIFIED')
        proof = self.observe('acct_current', fx_account='acct_current')['fx_proof']
        self.assertEqual(proof['status'], 'RECONCILED')
        self.assertFalse(proof['metal_funded'])

    def test_recorded_card_capture_is_not_a_new_active_authorization(self):
        report = self.observe('acct_current', card_account='acct_current')
        self.assertEqual(report['hold_workflow'], 'MEASURED_HOSTED_CAPTURE_COMPLETE')
        self.assertTrue(report['hosted_checkout']['write_access_verified'])
        self.assertFalse(report['hosted_checkout']['authorization_active'])
        self.assertEqual(report['hosted_checkout']['captured_micro_usd'], 10000)

    def test_old_account_card_proof_cannot_verify_current_writes(self):
        report = self.observe('acct_current', card_account='acct_old')
        self.assertFalse(report['hosted_checkout']['write_access_verified'])


if __name__ == '__main__':
    unittest.main()
