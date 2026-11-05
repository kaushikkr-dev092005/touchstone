import unittest
from unittest.mock import patch
from touchstone.treasury import AirwallexSandbox, AirwallexHTTPError


class Treasury(unittest.TestCase):
    def test_missing_request_index_reconciles_exact_source_using_get_only(self):
        with patch.dict('os.environ', {'AIRWALLEX_CLIENT_ID': 'fixture-client', 'AIRWALLEX_API_KEY': 'fixture-key',
                                      'AIRWALLEX_ACCOUNT_ID': 'acct_fixture'}):
            client = AirwallexSandbox()
        expected = {'source_type': 'CONVERSION', 'source': 'conv_fixture', 'amount': -1}
        def request(method, path, *args):
            self.assertEqual(method, 'GET')
            if 'request_id=' in path and '/balances/history?' in path:
                raise AirwallexHTTPError(404, 'not_found')
            if '/fx/conversions?' in path:
                return {'items': [{'request_id': 'approved', 'conversion_id': 'conv_fixture'}]}
            if 'page_num=0' in path:
                return {'items': [{'source_type': 'CONVERSION', 'source': 'unrelated'}], 'has_more': True}
            return {'items': [expected], 'has_more': False}
        with patch.object(client, 'request', side_effect=request):
            self.assertEqual(client.conversion_balance_history('approved'), [expected])
        self.assertIn('REQUEST_ID_404', client.balance_history_lookup)

    def test_history_auth_denial_does_not_fall_back_to_scanning(self):
        with patch.dict('os.environ', {'AIRWALLEX_CLIENT_ID': 'fixture-client', 'AIRWALLEX_API_KEY': 'fixture-key',
                                      'AIRWALLEX_ACCOUNT_ID': 'acct_fixture'}):
            client = AirwallexSandbox()
        with patch.object(client, 'request', side_effect=AirwallexHTTPError(403, 'forbidden')) as transport:
            with self.assertRaises(AirwallexHTTPError):
                client.conversion_balance_history('approved')
        self.assertEqual(transport.call_count, 1)

    def test_smoke_uses_supported_page_size_and_authenticates_once(self):
        with patch.dict('os.environ', {'AIRWALLEX_CLIENT_ID': 'fixture-client', 'AIRWALLEX_API_KEY': 'fixture-key',
                                      'AIRWALLEX_ACCOUNT_ID': 'acct_fixture'}):
            client = AirwallexSandbox()
        def request(path, method='GET', headers=None, body=None):
            if path.endswith('/login'):
                return {'token': 'PRIVATE_FIXTURE'}
            if '?' in path:
                self.assertIn('page_size=10', path)
                return {'items': []}
            return []
        with patch.object(client, '_request', side_effect=request) as transport:
            report = client.smoke()
        self.assertTrue(report['fx_conversions_read'])
        self.assertTrue(report['checkout_sessions_read'])
        self.assertEqual(sum(c.args[0].endswith('/login') for c in transport.call_args_list), 1)
        self.assertNotIn('PRIVATE_FIXTURE', str(report))

    def test_explicit_authentication_reuses_token_and_rejects_missing_token(self):
        with patch.dict('os.environ', {'AIRWALLEX_CLIENT_ID':'fixture-client', 'AIRWALLEX_API_KEY':'fixture-key'}):
            client = AirwallexSandbox()
        with patch.object(client, '_request', return_value={'token':'DO_NOT_PRINT'}) as transport:
            self.assertTrue(client.authenticate())
            client.authenticate()
            self.assertEqual(transport.call_count, 1)
        client.token = None
        with patch.object(client, '_request', return_value={'token':None}):
            with self.assertRaises(ValueError):
                client.authenticate()

    def test_scoped_key_read_denial_is_reported_separately_from_valid_login(self):
        with patch.dict('os.environ', {'AIRWALLEX_CLIENT_ID':'fixture-client', 'AIRWALLEX_API_KEY':'fixture-key',
                                     'AIRWALLEX_ACCOUNT_ID':'fixture-account'}):
            client = AirwallexSandbox()
        def request(path, method='GET', headers=None, body=None):
            if path.endswith('/login'):
                self.assertEqual(headers['x-login-as'], 'fixture-account')
                return {'token':'DO_NOT_PRINT'}
            if '/checkout_sessions?' in path:
                self.assertEqual(headers['x-api-version'], '2026-05-29')
                return {'items': []}
            raise AirwallexHTTPError(401, 'unauthorized')
        client._request = request
        report = client.smoke()
        self.assertTrue(report['authenticated'])
        self.assertTrue(report['checkout_sessions_read'])
        self.assertFalse(report['checkout_sessions_write_verified'])
        self.assertFalse(report['balance_read'])
        self.assertFalse(report['global_accounts_read'])
        self.assertEqual(report['read_errors']['balance_read']['http_status'], 401)
        self.assertNotIn('DO_NOT_PRINT', str(report))


if __name__ == '__main__':
    unittest.main()
