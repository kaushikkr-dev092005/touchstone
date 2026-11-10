import unittest
from tools.check_external_access import inspect_merchant
from touchstone.treasury import AirwallexHTTPError


class ExternalAccessTests(unittest.TestCase):
    def test_merchant_read_is_not_onboarding_and_private_config_is_omitted(self):
        class Client:
            def request(self, method, path):
                self_call = (method, path)
                assert self_call == ('GET', '/api/v1/pa/agentic_commerce/config')
                return {'secret': 'private-config-value'}
        result = inspect_merchant(Client())
        self.assertTrue(result['configuration_read'])
        self.assertFalse(result['onboarding_verified'])
        self.assertFalse(result['writes_performed'])
        self.assertNotIn('private-config-value', str(result))

    def test_denied_read_is_not_reported_as_successful_merchant_setup(self):
        class Client:
            def request(self, method, path):
                raise AirwallexHTTPError(401, 'unauthorized')
        result = inspect_merchant(Client())
        self.assertEqual(result['status'], 'ACCESS_DENIED')
        self.assertEqual(result['http_status'], 401)
        self.assertFalse(result['configuration_read'])
        self.assertFalse(result['payment_submitted'])

    def test_missing_merchant_configuration_is_distinct_from_denied_permission(self):
        class Client:
            def request(self, method, path):
                raise AirwallexHTTPError(404, 'MERCHANT_CONFIG_NOT_FOUND')
        result = inspect_merchant(Client())
        self.assertEqual(result['status'], 'NOT_CONFIGURED')
        self.assertFalse(result['onboarding_verified'])
