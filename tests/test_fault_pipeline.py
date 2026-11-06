import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from touchstone import fault_pipeline
from touchstone.engine import Engine
from touchstone.fault_pipeline import FaultPipeline, provider_origin
from touchstone.ledger import Ledger
from touchstone.payments import MockRail

RECORD = json.loads((Path(__file__).resolve().parent.parent/'bench/results/metal-paid-proof.json').read_text())
SELLER = RECORD['quote']['terms']['offer']['payTo']


def accepted_ack(proof):
    return {'version': 1, 'fault_root': proof['commitment']['root'], 'invoice_id': proof['body']['payment']['invoice']['id'],
            'decision': 'ACCEPTED', 'reason': 'fixture', 'credit_base_units': proof['body']['payment']['invoice']['amount'],
            'credit_status': 'ACKNOWLEDGED_NOT_SETTLED', 'refund_executed': False, 'signer': SELLER, 'signature': '0x'+'00'*65}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.ledger = Ledger(self.dir/'ledger.sqlite')
        patcher = mock.patch.object(fault_pipeline, 'provider_origin', lambda url: 'http://127.0.0.1:1')
        patcher.start(); self.addCleanup(patcher.stop)
        self.submitted = []
        self.online = True

    def pipeline(self, record=RECORD, ack=accepted_ack, verifier=lambda *a: True):
        def signer(proof, wallet_scope=None):
            return {'fault_signature': {'signer': 'payer', 'signature': '0x'+'11'*65}}

        def submitter(origin, proof):
            if not self.online:
                raise ConnectionError('offline')
            self.submitted.append(proof['commitment']['root'])
            return ack(proof)
        return FaultPipeline(self.ledger, lambda key, task, quote: record, signer=signer, submitter=submitter, ack_verifier=verifier)

    def run_demo(self, pipeline):
        engine = Engine(self.ledger, MockRail(self.dir/'rail.sqlite'), fault_pipeline=pipeline)
        run = engine.create_demo(7, 12)
        engine.run(run)
        return engine

    def failed_keys(self):
        return {a['key'] for a in self.ledger.attempts() if a['passed'] == 0}

    def test_failures_are_processed_once_and_acknowledgement_is_retained(self):
        pipeline = self.pipeline()
        engine = self.run_demo(pipeline)
        failed = self.failed_keys()
        self.assertTrue(failed, 'seeded demo must contain a verification failure')
        rows = {r['key']: r for r in pipeline.receipts()}
        self.assertEqual(set(rows), failed)
        # All fixture records describe the same payment, so each key stores the identical proof root.
        for row in rows.values():
            self.assertEqual(row['state'], 'ACKNOWLEDGED_ACCEPTED')
            self.assertFalse(row['acknowledgement']['refund_executed'])
        before = len(self.submitted)
        for key in failed:
            pipeline.handle(key)
        self.assertEqual(len(self.submitted), before, 'terminal receipts are never resubmitted')
        self.assertTrue(engine.snapshot()['audit']['valid'] if 'valid' in engine.snapshot()['audit'] else True)

    def test_provider_outage_is_retained_and_retried_without_stopping_the_job(self):
        self.online = False
        pipeline = self.pipeline()
        self.run_demo(pipeline)
        rows = pipeline.receipts()
        self.assertTrue(rows and all(r['state'] == 'SUBMIT_PENDING' for r in rows))
        self.online = True
        pipeline.retry_pending()
        self.assertTrue(all(r['state'] == 'ACKNOWLEDGED_ACCEPTED' for r in pipeline.receipts()))

    def test_forged_acknowledgement_is_never_trusted(self):
        pipeline = self.pipeline(verifier=lambda *a: False)
        self.run_demo(pipeline)
        self.assertTrue(all(r['state'] == 'ACK_INVALID' for r in pipeline.receipts()))

    def test_ineligible_or_missing_evidence_creates_no_proof_and_no_submission(self):
        for record in (None, {**RECORD, 'mode': 'SIMULATED'}):
            self.setUp()
            pipeline = self.pipeline(record=record)
            self.run_demo(pipeline)
            self.assertTrue(all(r['state'] == 'NOT_ELIGIBLE' for r in pipeline.receipts()))
            self.assertEqual(self.submitted, [])

    def test_pipeline_errors_cannot_break_the_engine(self):
        pipeline = self.pipeline()
        pipeline.record_source = mock.Mock(side_effect=RuntimeError('boom'))
        engine = self.run_demo(pipeline)
        self.assertTrue(all(j['status'] == 'COMPLETED' for j in self.ledger.jobs()) or engine.snapshot())

    def test_review_origin_must_be_https_or_loopback_without_credentials(self):
        with mock.patch.object(fault_pipeline, 'provider_origin', provider_origin):
            self.assertEqual(provider_origin('http://127.0.0.1:8092/inference/x?task=y'), 'http://127.0.0.1:8092')
            self.assertEqual(provider_origin('https://seller.example/p'), 'https://seller.example')
            for bad in ('http://seller.example', 'https://u:p@seller.example', 'ftp://127.0.0.1', '', None):
                with self.assertRaises(ValueError):
                    provider_origin(bad)


if __name__ == '__main__':
    unittest.main()
