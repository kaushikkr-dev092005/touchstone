import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tools import prove_metal
from touchstone.banked import resource_url
from touchstone.workload import Task


class MetalProofRecovery(unittest.TestCase):
    def test_withdraw_only_preserves_queue_and_does_not_replay_purchase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = Task('protocol-probe', 'arithmetic', {'amounts_cents': [1250, 275, 499], 'discount_cents': 24})
            terms = {
                'job': 'funded-proof-001',
                'provider_url': resource_url('http://127.0.0.1:8092', task),
                'price_cap_micro_usd': 10000,
                'allocation_micro_usd': 100000,
                'purpose': 'INTEGRATION_PROBE',
                'task': task.public(),
            }
            private_path = root / 'data/metal-proofs/funded-proof-001.json'
            public_path = root / 'bench/results/metal-paid-proof.json'
            private_path.parent.mkdir(parents=True)
            public_path.parent.mkdir(parents=True)
            report = {
                'mode': 'REAL_TESTNET_PROTOCOL_PROBE',
                'terms': terms,
                'phase': 'DELIVERED',
                'result': {'state': 'DELIVERED'},
            }
            queue = {'tx': '0x' + '1' * 64}
            private_path.write_text(json.dumps(report), encoding='utf-8')
            public_path.write_text(json.dumps({
                'mode': report['mode'],
                'terms': {key: value for key, value in terms.items() if key != 'provider_url'},
                'withdrawal': {'status': 'waiting', 'queued': queue},
            }), encoding='utf-8')
            owner = MagicMock()
            rail = MagicMock()
            rail.withdraw.return_value = {
                'mode': 'TESTNET',
                'status': 'waiting',
                'epoch': '93301',
                'returned_float_confirmed': False,
            }

            with patch.object(prove_metal, 'ROOT', root), \
                 patch.object(prove_metal, 'load_local'), \
                 patch.object(prove_metal, 'BankedStore', return_value=owner), \
                 patch.object(prove_metal, 'MetalRail', return_value=rail) as rail_factory, \
                 patch('sys.argv', ['prove_metal.py', '--withdraw-only']), \
                 contextlib.redirect_stdout(io.StringIO()):
                prove_metal.main()

            rail_factory.assert_called_once_with('funded-proof-001', terms['provider_url'], 10000, 100000)
            rail.withdraw.assert_called_once_with()
            rail.pay.assert_not_called()
            rail.recover.assert_not_called()
            saved_private = json.loads(private_path.read_text(encoding='utf-8'))
            saved_public = json.loads(public_path.read_text(encoding='utf-8'))
            self.assertEqual(saved_private['withdrawal']['queued'], queue)
            self.assertEqual(saved_public['withdrawal']['queued'], queue)
            self.assertEqual(saved_public['withdrawal_transactions'], [{'kind': 'queue', **queue}])
            self.assertNotIn('provider_url', saved_public['terms'])

    def test_withdraw_only_records_claim_and_keeps_confirmation_on_later_empty_poll(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = Task('protocol-probe', 'arithmetic', {'amounts_cents': [1250, 275, 499], 'discount_cents': 24})
            terms = {
                'job': 'funded-proof-001',
                'provider_url': resource_url('http://127.0.0.1:8092', task),
                'price_cap_micro_usd': 10000,
                'allocation_micro_usd': 100000,
                'purpose': 'INTEGRATION_PROBE',
                'task': task.public(),
            }
            private_path = root / 'data/metal-proofs/funded-proof-001.json'
            public_path = root / 'bench/results/metal-paid-proof.json'
            private_path.parent.mkdir(parents=True)
            public_path.parent.mkdir(parents=True)
            report = {
                'mode': 'REAL_TESTNET_PROTOCOL_PROBE',
                'terms': terms,
                'phase': 'DELIVERED',
                'result': {'state': 'DELIVERED'},
                'withdrawal': {'status': 'waiting', 'queued': {'tx': '0x' + '1' * 64}},
            }
            claim = {'amount': '90000000000000000', 'tx': '0x' + '2' * 64, 'deferred': False}
            private_path.write_text(json.dumps(report), encoding='utf-8')
            public_path.write_text(json.dumps({
                'mode': report['mode'],
                'terms': {key: value for key, value in terms.items() if key != 'provider_url'},
                'withdrawal': report['withdrawal'],
            }), encoding='utf-8')
            owner = MagicMock()
            rail = MagicMock()
            rail.withdraw.return_value = {
                'mode': 'TESTNET',
                'status': 'sent',
                'claimed': [claim],
                'queued': None,
                'returned_float_confirmed': True,
            }

            with patch.object(prove_metal, 'ROOT', root), \
                 patch.object(prove_metal, 'load_local'), \
                 patch.object(prove_metal, 'BankedStore', return_value=owner), \
                 patch.object(prove_metal, 'MetalRail', return_value=rail), \
                 patch('sys.argv', ['prove_metal.py', '--withdraw-only']), \
                 contextlib.redirect_stdout(io.StringIO()):
                prove_metal.main()

            first_public = json.loads(public_path.read_text(encoding='utf-8'))
            self.assertTrue(first_public['withdrawal']['returned_float_confirmed'])
            self.assertEqual(first_public['withdrawal_transactions'], [
                {'kind': 'queue', 'tx': '0x' + '1' * 64},
                {'kind': 'claim', **claim},
            ])

            rail.withdraw.return_value = {
                'mode': 'TESTNET',
                'status': 'empty',
                'returned_float_confirmed': False,
            }
            with patch.object(prove_metal, 'ROOT', root), \
                 patch.object(prove_metal, 'load_local'), \
                 patch.object(prove_metal, 'BankedStore', return_value=owner), \
                 patch.object(prove_metal, 'MetalRail', return_value=rail), \
                 patch('sys.argv', ['prove_metal.py', '--withdraw-only']), \
                 contextlib.redirect_stdout(io.StringIO()):
                prove_metal.main()

            second_public = json.loads(public_path.read_text(encoding='utf-8'))
            self.assertEqual(second_public['withdrawal']['status'], 'empty')
            self.assertTrue(second_public['withdrawal']['returned_float_confirmed'])
            self.assertEqual(second_public['withdrawal_transactions'], first_public['withdrawal_transactions'])


if __name__ == '__main__':
    unittest.main()
