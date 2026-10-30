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


class ServerRecovery(unittest.TestCase):
    def test_restarted_server_pauses_orphaned_jobs_before_any_new_purchase(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            engine = Engine(Ledger(root / "ledger.sqlite"), MockRail(root / "rail.sqlite"))
            engine.create_demo(count=3)
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            process = subprocess.Popen([sys.executable, "-m", "touchstone", "serve", "--port", str(port), "--data-dir", str(root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for _ in range(80):
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=1) as response:
                            state = json.load(response)
                        break
                    except OSError:
                        time.sleep(.1)
                else:
                    self.fail("Restarted server did not become ready")
                self.assertTrue(state["halted"])
                self.assertFalse(state["worker_running"])
                self.assertEqual({j["status"] for j in state["jobs"]}, {"PAUSED_KILL"})
                self.assertEqual(state["reconciliation"]["rail_total"], 0)
            finally:
                process.terminate()
                process.communicate(timeout=10)
