import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.run_final_live_proofs import reconcile_unpaid


class FinalContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scope = 'test-no-retry'
        self.path = self.root/'journal.json'
        self.wallet = self.root/'data/metal'/self.scope/'wallet.sqlite'
        self.wallet.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.wallet)) as db, db:
            db.execute('CREATE TABLE purchases(id TEXT,state TEXT,result TEXT)')
            db.execute("INSERT INTO purchases VALUES('key','UNKNOWN',NULL)")
        self.row = dict(seed=1, index=0, source_id='source', template_id='layout', partition='holdout',
                        task={'source':{'text':'uncertain document','purchase_order':{},'payments':[]}})
        self.runner = SimpleNamespace(directory=self.root, plan={'scope':self.scope,
            'tasks':[self.row], 'schedule':{'faults':{}}})
        self.state = {'rows':[], 'calls':{'key':{'policy':'always-cheapest','task_id':'M4-1-0-1','latency_ms':9}}}
        self.path.write_text(json.dumps(self.state))
        self.ledger = Mock()
        self.ledger.attempts.return_value = [{'state':'DISPATCHING','receipt':None,'key':'key'}]
        self.client = Mock()
        self.client.invoke.return_value = {'confirmed_nonpayment':True,'pending_invoice':False,
            'new_receipt_ids':[],'transactions_sent':0,'inference_requests_sent':0}

    def reconcile(self):
        with patch('tools.run_final_live_proofs.ROOT', self.root), patch('touchstone.ledger.Ledger', return_value=self.ledger):
            return reconcile_unpaid(self.runner,self.client,self.path)

    def test_uncertain_original_cannot_release_or_continue(self):
        self.client.invoke.return_value['pending_invoice'] = True
        with self.assertRaises(ValueError):self.reconcile()
        self.ledger.void.assert_not_called()
        self.assertEqual(json.loads(self.path.read_text()),self.state)

    def test_confirmed_unpaid_is_counted_incorrect_without_repayment(self):
        result = self.reconcile()
        state = json.loads(self.path.read_text())
        self.assertFalse(result['request_repeated'])
        self.assertEqual(state['rows'][0]['protocol_failure'],'CONFIRMED_UNPAID_NO_RETRY')
        self.assertIsNone(state['rows'][0]['output'])
        self.assertFalse(state['rows'][0]['accepted'])
        self.client.invoke.assert_called_once_with('inspect-purchase',id='key')
        self.ledger.void.assert_called_once_with('key','PINNED_SDK_CONFIRMED_UNPAID_NO_RETRY',authoritative=True)
        with closing(sqlite3.connect(self.wallet)) as db:
            self.assertEqual(db.execute('SELECT state FROM purchases').fetchone()[0],'UNPAID_CONFIRMED')
        with self.assertRaises(ValueError):self.reconcile()
        self.assertEqual(len(json.loads(self.path.read_text())['rows']),1)

    def test_receipt_bearing_attempt_never_treated_as_unpaid(self):
        self.ledger.attempts.return_value[0]['receipt'] = 'real-charge'
        with self.assertRaises(ValueError):self.reconcile()
        self.client.invoke.assert_not_called()
        self.ledger.void.assert_not_called()
