import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("scan_secrets", Path(__file__).resolve().parent.parent / "tools/scan_secrets.py")
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class ScanSecrets(unittest.TestCase):
    def test_private_paths_are_excluded_but_lockfile_is_scanned(self):
        for path in ("data/local-config.json", "data/metal/funding-wallet.json",
                     "archive/funding-wallet.json", ".env", ".env.local"):
            self.assertTrue(scan.excluded_path(path), path)
        self.assertFalse(scan.excluded_path(".env.example"))
        self.assertFalse(scan.excluded_path("integrations/metal/package-lock.json"))

    def test_scan_reports_private_history_without_reading_it(self):
        def fake_git(*args, **kwargs):
            if args[0] == "ls-files":
                return "data/local-config.json\0"
            if args[0] == "log":
                return "data/local-config.json\n"
            if args[0] == "rev-parse":
                return "false\n"
            self.fail("Private history content must not be read")
        output = io.StringIO()
        with patch.object(scan, "git", side_effect=fake_git), \
             patch.object(scan, "history_blobs", return_value=[("abc", ["data/local-config.json"], 100)]), \
             patch.object(scan.sys, "argv", ["scan_secrets.py", "--json"]), \
             patch.object(Path, "read_bytes", side_effect=AssertionError("Private file read")), \
             contextlib.redirect_stdout(output):
            self.assertEqual(scan.main(), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["blobs_scanned"], 0)
        self.assertEqual(result["sensitive_paths_in_history"], ["data/local-config.json"])

    def test_isolated_configuration_never_reads_private_paths(self):
        from touchstone.config import load_local
        with patch.dict(os.environ, {"TOUCHSTONE_IGNORE_LOCAL_CONFIG": "1"}), \
             patch.object(Path, "exists", side_effect=AssertionError("Private path inspected")):
            load_local()

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
