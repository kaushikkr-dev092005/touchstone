from pathlib import Path
import subprocess
import unittest
from touchstone.metal import node_executable


class MerchantServiceTests(unittest.TestCase):
    def test_oauth_and_signed_quote_protocols_without_financial_dispatch(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run([node_executable(), '--test', str(root/'apps/merchant/merchant.test.mjs')],
                                cwd=root, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
