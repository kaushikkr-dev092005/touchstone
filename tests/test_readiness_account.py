import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from touchstone import readiness,feature_evidence


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


class IssuingEvidenceTests(unittest.TestCase):
    def test_saved_creation_remains_historical_and_binds_the_original_account(self):
        from touchstone.ledger import canonical
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            folder=root/'bench/results/completion-20261110';folder.mkdir(parents=True)
            plan={'account_fingerprint':hashlib.sha256(b'acct_original').hexdigest()}
            digest=hashlib.sha256(canonical(plan).encode()).hexdigest()
            (folder/'issuing-plan.json').write_text(json.dumps({'plan':plan,'plan_sha256':digest,'approved':True}))
            (folder/'issuing-proof.json').write_text(json.dumps({'label':'MEASURED','card_controls_verified':True,
                'original_plan_sha256':digest,'card':{'status':'ACTIVE','authorization_controls':{}}}))
            with patch.object(feature_evidence,'ROOT',root),patch.dict(os.environ,{'AIRWALLEX_ACCOUNT_ID':'acct_original'},clear=True):
                saved=feature_evidence.summary()['card']['saved_creation']
                self.assertTrue(saved['current_account_matches'])
                self.assertFalse(saved['merchant_payment_completed'])
                self.assertFalse(saved['visa_approved_agent'])
            with patch.object(feature_evidence,'ROOT',root),patch.dict(os.environ,{'AIRWALLEX_ACCOUNT_ID':'acct_other'},clear=True):
                saved=feature_evidence.summary()['card']['saved_creation']
                self.assertFalse(saved['current_account_matches'])
                self.assertEqual(saved['scope'],'SAVED_SANDBOX_ISSUING')
            (folder/'issuing-proof.json').write_text(json.dumps({'label':'MEASURED','card_controls_verified':True,
                'original_plan_sha256':'tampered'}))
            with patch.object(feature_evidence,'ROOT',root):
                self.assertNotIn('saved_creation',feature_evidence.summary()['card'])

    def test_refresh_saves_only_read_diagnostics_and_binds_selected_account(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        request=Mock(side_effect=[{'items':[{'secret_card_detail':'never expose'}]},[],
            {'items':[{'private_cardholder':'never expose'}]},{'private_config':'never expose'}])
        client=SimpleNamespace(account_id='acct_current',evidence_label='MEASURED',request=request)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(feature_evidence,'ROOT',root):
                result=feature_evidence.refresh_issuing(client)
                self.assertEqual(result['operation'],'READ_ONLY_ISSUING_DIAGNOSIS')
                self.assertTrue(result['issuing_read'])
                saved=(root/'data/issuing-readiness.json').read_text()
                public=root/'bench/results/features/card-readiness.json'
                public.parent.mkdir(parents=True);public.write_text(saved)
                self.assertNotIn('never expose',saved)
                self.assertNotIn('acct_current',saved)
                self.assertTrue(all(call.args[0]=='GET' for call in request.call_args_list))
                with patch.dict(os.environ,{'AIRWALLEX_ACCOUNT_ID':'acct_current'},clear=True):
                    self.assertEqual(feature_evidence.summary()['card'],result)
                with patch.dict(os.environ,{'AIRWALLEX_ACCOUNT_ID':'acct_other'},clear=True):
                    self.assertFalse(feature_evidence.summary()['card']['issuing_read'])
                with patch.dict(os.environ,{},clear=True):
                    self.assertFalse(feature_evidence.summary()['card']['issuing_read'])


if __name__ == '__main__':
    unittest.main()
