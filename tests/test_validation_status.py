import unittest

from tools.validation_status import provider_status


class ValidationStatusTests(unittest.TestCase):
    def test_stopped_or_unconfigured_providers_never_pass(self):
        report = provider_status(lambda *_: {})
        self.assertFalse(report['model'])
        self.assertFalse(report['dashboard'])
        self.assertEqual(report['local-gpu']['label'], 'BLOCKED')
        self.assertEqual(report['hosted-premium']['label'], 'BLOCKED')

    def test_health_requires_identity_chain_readiness_and_hosted_funding_declaration(self):
        rows = {8088: {'jobs': []}, 8080: {'status': 'ok'},
                8092: {'provider_id': 'local-gpu', 'provider_type': 'model', 'chain': 63825, 'inference_ready': True},
                8093: {'provider_id': 'hosted-premium', 'provider_type': 'anthropic', 'chain': 63825,
                       'inference_ready': True, 'upstream_funding': 'PARTNER_CREDITS_OPERATOR_DECLARED'}}
        reader = lambda port, _: rows[port]
        self.assertEqual(provider_status(reader)['hosted-premium']['label'], 'MEASURED')
        for key, value in [('provider_id', 'another-seller'), ('chain', 1), ('inference_ready', False),
                           ('upstream_funding', 'UNVERIFIED')]:
            original = rows[8093][key]
            rows[8093][key] = value
            with self.subTest(key=key):
                self.assertEqual(provider_status(reader)['hosted-premium']['label'], 'BLOCKED')
            rows[8093][key] = original


if __name__ == '__main__':
    unittest.main()
