import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

from touchstone.engine import Engine
from touchstone.ledger import Ledger
from touchstone.payments import MockRail


class TransactionsApi(unittest.TestCase):
    def test_transactions_lists_every_attempt_across_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            engine = Engine(Ledger(root / "ledger.sqlite"), MockRail(root / "rail.sqlite"))
            run_id = engine.create_demo(count=3)
            engine.run(run_id, delay=0)
            expected = len(engine.ledger.attempts())
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            process = subprocess.Popen([sys.executable, "-m", "touchstone", "serve", "--port", str(port), "--data-dir", str(root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for _ in range(80):
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/transactions", timeout=1) as response:
                            data = json.load(response)
                        break
                    except OSError:
                        time.sleep(.1)
                else:
                    self.fail("Server did not become ready")
                self.assertEqual(len(data["transactions"]), expected)
                self.assertGreater(expected, 0)
                self.assertEqual({t["run_id"] for t in data["transactions"]}, {run_id})
                self.assertEqual([t["seq"] for t in data["transactions"]], list(range(1, expected + 1)))
                self.assertNotIn("output", data["transactions"][0])
            finally:
                process.terminate()
                process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
