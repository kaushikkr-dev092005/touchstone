import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from tools.bundle import build
from tools.bundle import safe_path,inspect_payload


class BundleTests(unittest.TestCase):
    def test_private_paths_and_traversal_are_refused(self):
        for name in ['../key','/absolute','data/local-config.json','.env','apps/web/.env.local','archive/funding-wallet.json','node_modules/sdk/index.js']:
            self.assertFalse(safe_path(name),name)
        self.assertTrue(safe_path('.env.example'))
        self.assertTrue(safe_path('integrations/metal/package-lock.json'))
        self.assertTrue(safe_path('bench/results/m2/current-wallet-preflight.json'))

    def test_secret_shapes_and_configured_values_cannot_enter_the_archive(self):
        with self.assertRaises(ValueError):inspect_payload('.env.example',('AIRWALLEX_API_KEY='+'A'*24).encode(),[])
        with self.assertRaises(ValueError):inspect_payload('README.md',b'contains a sensitive fixture value',[b'sensitive fixture'])
        inspect_payload('.env.example',b'AIRWALLEX_API_KEY=<your-scoped-key>',[])
        with self.assertRaises(ValueError):inspect_payload('bench/results/m2/current-wallet-preflight.json',('private_key="'+'a'*64+'"').encode(),[])

    def test_working_tree_archive_binds_edits_and_excludes_untracked_files(self):
        def fixture_git(*args):
            if args[0]=='rev-parse':return b'a'*40
            if args[0]=='ls-tree':return b'100644 blob fixture\tREADME.md\0'
            if args[0]=='cat-file':return b'committed\n'
            self.fail(args)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'README.md').write_bytes(b'reviewable edit\r\n')
            (root/'untracked.txt').write_bytes(b'excluded')
            with patch('tools.bundle.ROOT',root),patch('tools.bundle.git',side_effect=fixture_git):
                committed=build()
                self.assertFalse(committed['working_tree_edits_included'])
                with zipfile.ZipFile(root/'dist/touchstone-source.zip') as archive:
                    self.assertEqual(archive.read('touchstone/README.md'),b'committed\n')
                edited=build(working_tree=True)
                self.assertEqual(edited['source_mode'],'TRACKED_WORKING_TREE')
                self.assertEqual(edited['changed_files'],['README.md'])
                self.assertFalse(edited['untracked_files_included'])
                with zipfile.ZipFile(root/'dist/touchstone-source.zip') as archive:
                    self.assertEqual(archive.namelist(),['touchstone/README.md'])
                    self.assertEqual(archive.read('touchstone/README.md'),b'reviewable edit\r\n')
                manifest=json.loads((root/'dist/bundle-manifest.json').read_text())
                self.assertEqual(set(manifest['source_sha256']),{'README.md'})
                with self.assertRaises(ValueError):build(extra_paths=['untracked.txt'])
                added=build(working_tree=True,extra_paths=['untracked.txt'])
                self.assertTrue(added['untracked_files_included'])
                self.assertEqual(added['added_files'],['untracked.txt'])
                with self.assertRaises(ValueError):build(working_tree=True,extra_paths=['../outside'])
                (root/'README.md').unlink()
                with self.assertRaises(ValueError):build(working_tree=True)
