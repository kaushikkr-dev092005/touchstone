import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error

from tools.configure_hosted import check_and_save


KEY = 'sk-ant-' + 'fixture-key-not-a-real-credential'
MODEL = 'claude-fixture'


class HostedSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'local-config.json'
        self.calls = []

    def opener(self, metadata=None):
        def send(request, timeout):
            self.calls.append(request)
            return io.BytesIO(json.dumps(metadata if metadata is not None else
                {'id': MODEL, 'type': 'model', 'capabilities': {'structured_outputs': {'supported': True}}}).encode())
        return send

    def save(self, **kwargs):
        options = {'opener': self.opener(), 'path': self.path}
        options.update(kwargs)
        return check_and_save(KEY, MODEL, credits=True, **options)

    def test_only_model_metadata_is_requested_and_secret_is_not_reported(self):
        result = self.save()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0].get_method(), 'GET')
        self.assertEqual(self.calls[0].full_url, 'https://api.anthropic.com/v1/models/' + MODEL)
        self.assertIsNone(self.calls[0].data)
        self.assertTrue(result['model_metadata_verified'])
        self.assertEqual((result['model_inference_calls'], result['financial_transactions']), (0, 0))
        self.assertNotIn(KEY, json.dumps(result))
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['ANTHROPIC_API_KEY'], KEY)
        self.assertFalse(self.path.with_suffix('.pending').exists())

    def test_workspace_and_partner_credit_declaration_are_preserved_locally(self):
        result = check_and_save(KEY, MODEL, 'wrkspc_fixture', credits=True, opener=self.opener(), path=self.path)
        headers = {k.lower(): v for k, v in self.calls[0].header_items()}
        self.assertEqual(headers['anthropic-workspace-id'], 'wrkspc_fixture')
        self.assertTrue(result['workspace_configured'])
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['TOUCHSTONE_HOSTED_FUNDING_SOURCE'], 'PARTNER_CREDITS')

    def test_existing_bank_and_rpc_settings_are_preserved(self):
        original = {'AIRWALLEX_ACCOUNT_ID': 'acct_fixture', 'METAL_RPC_URL': 'https://fixture.invalid'}
        self.path.write_text(json.dumps(original))
        self.save()
        saved = json.loads(self.path.read_text())
        self.assertTrue(all(saved[k] == v for k, v in original.items()))

    def test_invalid_input_and_missing_credit_confirmation_make_no_request(self):
        for key, model, workspace, credits in [('', MODEL, '', True), (KEY, '../model', '', True),
                (KEY, MODEL, 'bad workspace', True), (KEY, MODEL, '', False), (KEY + '\nunsafe', MODEL, '', True)]:
            with self.subTest(model=model, credits=credits), self.assertRaises(ValueError):
                check_and_save(key, model, workspace, credits, opener=self.opener(), path=self.path)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.path.exists())

    def test_refused_or_malformed_metadata_never_overwrites_configuration(self):
        self.path.write_text('{}')
        for metadata in ([], {}, {'id': MODEL, 'type': 'model', 'capabilities': {'structured_outputs': {'supported': False}}}):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                self.save(opener=self.opener(metadata))
            self.assertEqual(self.path.read_text(), '{}')

    def test_http_errors_are_redacted(self):
        def refused(*args, **kwargs):
            raise urllib.error.HTTPError('https://fixture.invalid', 401, KEY, {}, None)
        with self.assertRaises(ValueError) as caught:
            self.save(opener=refused)
        self.assertNotIn(KEY, str(caught.exception))
        self.assertFalse(self.path.exists())

    def test_invalid_existing_configuration_is_preserved(self):
        self.path.write_text('{"unsupported_setting":"fixture"}')
        with self.assertRaises(ValueError):
            self.save()
        self.assertEqual(self.path.read_text(), '{"unsupported_setting":"fixture"}')


if __name__ == '__main__':
    unittest.main()
