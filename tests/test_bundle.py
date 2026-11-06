import unittest
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
