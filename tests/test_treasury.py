import unittest
from unittest.mock import patch
from touchstone.treasury import AirwallexSandbox, AirwallexHTTPError


class Treasury(unittest.TestCase):
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
