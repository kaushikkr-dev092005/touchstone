import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("scan_secrets", Path(__file__).resolve().parent.parent / "tools/scan_secrets.py")
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class ScanSecrets(unittest.TestCase):
    def rules(self, text):
        return {name for name, _ in scan.scan_text(text)}

    def test_detects_secret_shapes_without_returning_values(self):
        self.assertIn("anthropic-key", self.rules("k = sk-" + "ant-" + "a" * 30))
        self.assertIn("labelled-hex-key", self.rules("AGENT_PRIVATE_KEY=0x" + "ab" * 32))
        self.assertIn("pem-private-key", self.rules("-----BEGIN " + "PRIVATE KEY-----"))
        self.assertIn("airwallex-env-assignment", self.rules("AIRWALLEX_API_KEY=" + "x1" * 12))
        for _, length in scan.scan_text("AGENT_PRIVATE_KEY=0x" + "ab" * 32):
            self.assertIsInstance(length, int)

    def test_ignores_placeholders_empty_assignments_and_loopback_digests(self):
        self.assertFalse(self.rules("AIRWALLEX_CLIENT_ID=\nAIRWALLEX_API_KEY=\n"))
        self.assertFalse(self.rules("AIRWALLEX_API_KEY=<sandbox-api-key-goes-here>"))
        self.assertFalse(self.rules("http://127.0.0.1:8092/" + "a" * 64))
        self.assertFalse(self.rules("tx 0x" + "a" * 64))


if __name__ == "__main__":
    unittest.main()
