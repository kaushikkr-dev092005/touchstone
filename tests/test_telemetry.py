import subprocess
import unittest
from unittest.mock import Mock,patch
from touchstone import telemetry


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.previous=(telemetry._sample,telemetry._sampled_at)
        telemetry._sample=None;telemetry._sampled_at=0
        self.addCleanup(lambda:setattr(telemetry,'_sample',self.previous[0]))
        self.addCleanup(lambda:setattr(telemetry,'_sampled_at',self.previous[1]))

    def test_high_temperature_is_not_evidence_of_throttling_or_a_price_rise(self):
        raw='GPU-fixture, Fixture, 83, 90, 1000, 4096, 40, 1500, 2100, Not Active, Not Active'
        r=telemetry.parse(raw,100)
        self.assertEqual(r['temperature_c'],83)
        self.assertFalse(r['thermal_throttling_active']);self.assertFalse(r['temperature_alone_changes_price'])
        self.assertIsNone(r['throughput_tokens_per_second'])

    def test_real_throttling_unknown_fields_and_cache(self):
        raw='GPU-fixture, Fixture, 83, 90, 1000, 4096, N/A, 1500, 2100, Active, Not Active'
        runner=Mock(return_value=Mock(returncode=0,stdout=raw))
        r=telemetry.sample(100,runner)
        self.assertTrue(r['thermal_throttling_active']);self.assertIsNone(r['power_w'])
        self.assertEqual(telemetry.sample(102,runner),r);self.assertEqual(runner.call_count,1)

    def test_failed_service_stays_blocked_instead_of_showing_old_live_data(self):
        runner=Mock(side_effect=OSError)
        result=telemetry.sample(100,runner)
        self.assertEqual(result['label'],'BLOCKED');self.assertIsNone(result['sample_id'])
