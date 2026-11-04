import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import configure_airwallex as setup


class AirwallexSetupTests(unittest.TestCase):
    def test_form_uses_environment_and_pinned_sandbox_without_disclosure(self):
        values = dict(zip(setup.KEYS, ('fixture-client', 'PRIVATE_FIXTURE', 'acct_fixture_one')))

        def doctor(*, probe_reads):
            self.assertTrue(probe_reads)
            self.assertEqual(os.environ['AIRWALLEX_API_KEY'], 'PRIVATE_FIXTURE')
            self.assertEqual(os.environ['AIRWALLEX_BASE_URL'], setup.BASE_URL)
            return {'read_probe': 'PASS', 'money_moved': False}

        with patch.dict(os.environ, {}, clear=True), patch.object(setup, 'inspect', side_effect=doctor):
            result = setup.check(values)
        self.assertNotIn('PRIVATE_FIXTURE', json.dumps(result))

    def test_missing_fields_stop_before_network(self):
        with patch.object(setup, 'inspect') as doctor:
            with self.assertRaises(ValueError):
                setup.check({'AIRWALLEX_API_KEY': 'PRIVATE_FIXTURE'})
            doctor.assert_not_called()

    def test_dashboard_is_not_opened_when_saved_key_is_rejected(self):
        report = {'read_probe': 'BLOCKED_AUTHENTICATION'}
        with tempfile.TemporaryDirectory() as directory:
            target = str(Path(directory)/'status.json')
            with patch('sys.argv', ['configure_airwallex', '--check-saved', '--open-dashboard', '--status', target]), \
                 patch.object(setup, 'check_saved', return_value=report), \
                 patch.object(setup, 'open_dashboard') as launch, \
                 patch.object(setup, 'publish_readiness') as readiness, \
                 patch('builtins.print'):
                self.assertEqual(setup.main(), 2)
            launch.assert_not_called()
            readiness.assert_not_called()

    def test_dashboard_opens_only_after_saved_key_passes(self):
        report = {'read_probe': 'PASS'}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'status.json'
            with patch('sys.argv', ['configure_airwallex', '--check-saved', '--open-dashboard', '--status', str(target)]), \
                 patch.object(setup, 'check_saved', return_value=report), \
                 patch.object(setup, 'open_dashboard', return_value=False) as launch, \
                 patch.object(setup, 'publish_readiness') as readiness, \
                 patch('builtins.print'):
                self.assertEqual(setup.main(), 0)
            launch.assert_called_once_with()
            readiness.assert_called_once_with(report)
            self.assertFalse(json.loads(target.read_text())['existing_dashboard_kept'])


if __name__ == '__main__':
    unittest.main()
