import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.validate_release import clean_environment, extract_verified


class ReleaseValidationTests(unittest.TestCase):
    def test_environment_removes_financial_credentials_and_live_modes(self):
        private = {'AIRWALLEX_API_KEY': 'bank-fixture', 'METAL_RPC_URL': 'rpc-fixture',
                   'ANTHROPIC_API_KEY': 'hosted-fixture', 'AGENT_PRIVATE_KEY': 'wallet-fixture',
                   'TOUCHSTONE_LIVE_AUTHORIZATION': 'approval-fixture', 'TOUCHSTONE_PROVIDER_MODE': 'anthropic',
                   'TOUCHSTONE_HOSTED_FUNDING_SOURCE': 'PARTNER_CREDITS'}
        with patch.dict(os.environ, {**private, 'PATH': 'tools'}, clear=True):
            env = clean_environment(str(Path('runtime/node.exe').resolve()))
        self.assertTrue(all(key not in env for key in private))
        self.assertEqual(env['TOUCHSTONE_IGNORE_LOCAL_CONFIG'], '1')

    def archive(self, root, entries):
        archive = root / 'source.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            for name, payload in entries.items():
                zipped.writestr(name, payload)
        manifest = {'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                    'source_sha256': {name.removeprefix('touchstone/'): hashlib.sha256(payload).hexdigest()
                                      for name, payload in entries.items()}}
        return archive, manifest

    def test_extracted_files_match_every_committed_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive, manifest = self.archive(root, {'touchstone/README.md': b'fixture'})
            self.assertEqual(extract_verified(archive, manifest, root / 'source'), 1)
            self.assertEqual((root / 'source/README.md').read_bytes(), b'fixture')
            manifest['source_sha256']['README.md'] = 'bad'
            with self.assertRaises(ValueError):
                extract_verified(archive, manifest, root / 'other')

    def test_traversal_wrong_prefix_and_incomplete_archives_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('touchstone/../outside', '/touchstone/absolute', 'other/file',
                         'touchstone/C:/drive', 'touchstone/a\\b'):
                archive, manifest = self.archive(root, {name: b'fixture'})
                with self.subTest(name=name), self.assertRaises(ValueError):
                    extract_verified(archive, manifest, root / 'source')
            archive, manifest = self.archive(root, {'touchstone/README.md': b'fixture'})
            manifest['source_sha256']['missing'] = 'bad'
            with self.assertRaises(ValueError):
                extract_verified(archive, manifest, root / 'source')


if __name__ == '__main__':
    unittest.main()
