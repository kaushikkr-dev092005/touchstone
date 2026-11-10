import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from touchstone import feature_evidence as module


class CurrentFaultProjection(unittest.TestCase):
    def fixture(self,root):
        file=root/'bench/results/faults/current-paid-fault-20261110.json'
        file.parent.mkdir(parents=True);file.write_text('{}')
        proof={'commitment':{'root':'root'},'fault_signature':{'signature':'fixture'},
            'body':{'requirements':{'payTo':'seller'},'payment':{'invoice':{'id':'invoice'}},
                    'counterexample':{'error_code':'INVOICE_TOTAL_MISMATCH'}}}
        ack={'root':'root','acknowledgement':{'decision':'REJECTED','credit_status':'NONE'},
             'independent_receipt_check':{'operator_signature_verified':True,'provider_output_attribution':'SIGNED_BY_INVOICE_RECIPIENT'}}
        def loader(path):
            if path==file:return proof
            if path.name=='current-seller-fault-acknowledgement.json':return ack
            return {}
        return loader,ack

    def test_signed_rejection_is_exposed_without_claiming_refund_or_finality(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);loader,ack=self.fixture(root)
            with patch.object(module,'ROOT',root),patch.object(module,'load',loader),\
                 patch('touchstone.fault_proof.validate'),patch('touchstone.fault_pipeline.node_ack_verifier',return_value=True) as verify:
                result=module.summary()['fault']
                verify.assert_called_once_with(ack['acknowledgement'],'seller','root','invoice')
                self.assertTrue(result['seller_ack_signature_verified']);self.assertEqual(result['seller_ack_decision'],'REJECTED')
                self.assertFalse(result['credit_issued']);self.assertFalse(result['refund_executed']);self.assertFalse(result['final_settlement_verified'])

    def test_missing_node_keeps_python_demo_available_and_does_not_promote_ack(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);loader,_=self.fixture(root)
            with patch.object(module,'ROOT',root),patch.object(module,'load',loader),\
                 patch('touchstone.fault_proof.validate'),patch('touchstone.fault_pipeline.node_ack_verifier',side_effect=RuntimeError('Node unavailable')):
                result=module.summary()['fault']
                self.assertEqual(result['label'],'MEASURED');self.assertFalse(result['seller_ack_signature_verified'])
                self.assertIsNone(result['seller_ack_decision']);self.assertEqual(result['seller_credit_status'],'UNVERIFIED')
