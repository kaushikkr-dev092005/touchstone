import copy
import json
from pathlib import Path
import unittest

from touchstone.fault_proof import create, validate, merkle


class FaultProofTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((Path(__file__).resolve().parent.parent/'bench/results/metal-paid-proof.json').read_text())
        self.proof = create(self.record)

    def test_recorded_fault_recomputes_from_original_public_inputs(self):
        self.assertTrue(validate(self.proof))
        c = self.proof['body']['counterexample']
        self.assertEqual((c['error_code'], c['claimed_total_minor'], c['recomputed_total_minor']),
                         ('INVOICE_TOTAL_MISMATCH', 1250, 2000))
        self.assertIsNone(self.proof['body']['delivery_attestation'])
        self.assertFalse(self.proof['limits']['refund_executed'])

    def test_source_answer_receipt_and_rule_tampering_break_commitment(self):
        mutations = [lambda b:b['output'].update(total_cents=1999),
                     lambda b:b['task']['source'].update(discount_cents=1),
                     lambda b:b['payment']['invoice'].update(amount='1'),
                     lambda b:b['counterexample'].update(recomputed_total_minor=1250),
                     lambda b:b['contract'].update(verifier_version='fabricated')]
        for mutate in mutations:
            proof = copy.deepcopy(self.proof)
            mutate(proof['body'])
            with self.assertRaises(ValueError): validate(proof)

    def test_rehashing_does_not_make_a_fake_counterexample_valid(self):
        self.proof['body']['counterexample']['recomputed_total_minor'] = 42
        self.proof['commitment'] = merkle(self.proof['body'])
        with self.assertRaisesRegex(ValueError, 'reproduce'): validate(self.proof)

    def test_correct_answer_unsupported_source_and_semantic_tasks_cannot_claim_fault(self):
        for mutate in [lambda r:r['result']['output']['body'].update(output={'total_cents':2000}),
                       lambda r:r['terms']['task']['source'].update(discount_cents=-1),
                       lambda r:r['terms']['task'].update(kind='classification',source={'text':'Ambiguous'})]:
            record=copy.deepcopy(self.record); mutate(record)
            with self.assertRaises(ValueError): create(record)

    def test_claims_and_nonces_do_not_silently_reuse_an_old_attestation(self):
        other=create(self.record)
        self.assertNotEqual(other['body']['nonce'], self.proof['body']['nonce'])
        self.assertNotEqual(other['commitment']['root'],self.proof['commitment']['root'])
        self.assertIsNone(self.proof['fault_signature'])


if __name__ == '__main__': unittest.main()
