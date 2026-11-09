import json
from contextlib import contextmanager
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
from touchstone.banked import BankedStore
from touchstone.providers import quotes
from touchstone.workload import generate
from tools.validate_release import clean_environment


class TransactionsApi(unittest.TestCase):
    @contextmanager
    def server(self, root):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0))
            port=probe.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        process=subprocess.Popen([sys.executable,'-m','touchstone','serve','--port',str(port),'--data-dir',str(root)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=clean_environment(sys.executable),
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            for _ in range(80):
                if process.poll() is not None:self.fail('Server exited')
                try:
                    with urllib.request.urlopen(base+'/api/state',timeout=1):break
                except OSError:time.sleep(.1)
            else:self.fail('Server did not become ready')
            yield base
        finally:
            process.terminate()
            process.wait(timeout=10)

    def test_banked_history_uses_selected_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            store=BankedStore(root/'banked/ledger.sqlite')
            store.bind('isolated-fixture',{'fixture':True})
            with self.server(root) as base:
                with urllib.request.urlopen(base+'/api/banked-jobs') as response:
                    report=json.load(response)
                self.assertEqual([j['scope'] for j in report['jobs']],['isolated-fixture'])
                self.assertTrue(report['audit']['valid'])
            with self.server(root/'empty') as base:
                for endpoint,key in (('/api/banked-jobs','jobs'),('/api/real-provider-runs','runs')):
                    with urllib.request.urlopen(base+endpoint) as response:
                        self.assertEqual(json.load(response)[key],[])
                self.assertFalse((root/'empty/banked').exists())

    def test_transaction_charges_exclude_reservations_and_voids(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            ledger=Ledger(root/'ledger.sqlite')
            tasks,_=generate(42,4)
            run=ledger.create_run([{'seed':42,'policy':'touchstone','hold':1000000,
                'allocation':1000000,'price_cap':60000,'tasks':[t.public() for t in tasks]}],1000000)
            job=ledger.jobs(run)[0]['id']
            offer=quotes(42,0)[0]
            keys=[ledger.reserve(job,task,0,offer,1000) for task in tasks]
            ledger.void(keys[1],'No purchase')
            for key in keys[2:]:
                ledger.record_paid(key,{'key':key,'amount':offer.price,'quote_id':offer.id,
                    'provider':offer.provider,'id':'fixture-'+key})
            ledger.finish_attempt(keys[3],{}, {'passed':False,'score':0,'reason':'Rejected fixture'})
            with self.server(root) as base:
                with urllib.request.urlopen(base+'/api/transactions') as response:
                    rows=json.load(response)['transactions']
                self.assertEqual([r['state'] for r in rows],['RESERVED','VOID','PAID','VERIFIED_FAIL'])
                self.assertEqual([r['charged_provider'] for r in rows],[0,0,offer.price,offer.price])
                self.assertEqual([r['charged_verification'] for r in rows],[0,0,0,1000])
                self.assertTrue(all(r['price']==offer.price and r['verify_cost']==1000 for r in rows))

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
