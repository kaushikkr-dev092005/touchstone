import unittest

from touchstone import throughput

SHA = 'ab' * 64 and 'ab' * 32


def sample(tps, basis='SERVER_DECODE_TIMING', throttled=False):
    return {'basis': basis, 'decode_tps': tps, 'telemetry': {'thermal_throttling_active': throttled}}


class ThroughputTests(unittest.TestCase):
    def test_decode_rate_prefers_server_timing_and_rejects_missing_usage(self):
        raw = {'usage': {'completion_tokens': 50}, 'timings': {'predicted_per_second': 125.5}}
        self.assertEqual(throughput.decode_rate(raw, 1), (50, 125.5, 'SERVER_DECODE_TIMING'))
        self.assertEqual(throughput.decode_rate({'usage': {'completion_tokens': 50}}, 2)[1:], (25.0, 'WALL_CLOCK_INCLUDING_PROMPT'))
        for bad in ({}, {'usage': {'completion_tokens': 0}}, {'usage': {'completion_tokens': True}}):
            with self.assertRaises(ValueError):
                throughput.decode_rate(bad, 1)

    def test_calibration_requires_enough_stable_unthrottled_server_timed_samples(self):
        good = [sample(100 + (i % 3)) for i in range(24)]
        result = throughput.calibrate(good + [sample(1, throttled=True), sample(5, 'WALL_CLOCK_INCLUDING_PROMPT')],
                                      model='m', model_sha256=SHA, now=1000)
        body = result['body']
        self.assertEqual((body['samples'], body['excluded_samples']), (24, {'throttled': 1, 'not_server_timed': 1}))
        self.assertFalse(body['temperature_changes_price'])
        self.assertTrue(throughput.verify(result, SHA, now=1001))
        for samples in (good[:5], [sample(10 + 40 * (i % 2)) for i in range(24)]):
            with self.assertRaises(ValueError):
                throughput.calibrate(samples, model='m', model_sha256=SHA)
        for multiplier in (1.0, 2.0):
            with self.assertRaises(ValueError):
                throughput.calibrate(good, model='m', model_sha256=SHA, max_multiplier=multiplier)

    def test_multiplier_is_bounded_and_falls_back_to_one_without_valid_evidence(self):
        calibration = throughput.calibrate([sample(100.0)] * 24, model='m', model_sha256=SHA, now=1000)
        self.assertEqual(throughput.multiplier(calibration, [100] * 5, now=1001), 1.0)
        self.assertAlmostEqual(throughput.multiplier(calibration, [80] * 5, now=1001), 1.25)
        self.assertEqual(throughput.multiplier(calibration, [1] * 5, now=1001), 1.25)
        self.assertEqual(throughput.multiplier(calibration, [80] * 4, now=1001), 1.0)
        self.assertEqual(throughput.multiplier(calibration, [80] * 5, now=1000 + throughput.VALID_SECONDS + 1), 1.0)
        calibration['body']['baseline_tps'] = 1
        self.assertEqual(throughput.multiplier(calibration, [0.5] * 5, now=1001), 1.0)
        self.assertEqual(throughput.multiplier(None, [1] * 5), 1.0)

    def test_measurement_pairs_each_call_with_a_hardware_sample_and_stays_loopback(self):
        raw = {'usage': {'completion_tokens': 10}, 'timings': {'predicted_per_second': 50}}
        rows = throughput.measure(lambda m, n: (raw, 0.2), lambda: {'sample_id': 'x', 'temperature_c': 50}, model='m', runs=4, clock=lambda: 1)
        self.assertEqual([r['max_tokens'] for r in rows], [64, 128, 256, 64])
        self.assertTrue(all(r['telemetry']['temperature_c'] == 50 for r in rows))
        with self.assertRaises(ValueError):
            throughput.http_request('http://example.com/v1/chat/completions', 'm', 10)


if __name__ == '__main__':
    unittest.main()


class CapacitySummaryTests(unittest.TestCase):
    def test_summary_reports_valid_expired_altered_and_missing_calibrations(self):
        import json
        from pathlib import Path
        import tempfile
        from unittest import mock
        from touchstone import feature_evidence
        calibration = throughput.calibrate([sample(100.0)] * 24, model='m', model_sha256=SHA, now=1000)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / 'bench/results/features'
            target.mkdir(parents=True)
            with mock.patch.object(feature_evidence, 'ROOT', root):
                self.assertEqual(feature_evidence.capacity_summary(now=1001)['label'], 'BLOCKED')
                (target / 'capacity-calibration.json').write_text(json.dumps(calibration))
                good = feature_evidence.capacity_summary(now=1001)
                self.assertEqual((good['label'], good['markup_enabled'], good['temperature_changes_price']), ('MEASURED', True, False))
                self.assertFalse(feature_evidence.capacity_summary(now=1000 + throughput.VALID_SECONDS + 5)['markup_enabled'])
                calibration['body']['baseline_tps'] = 1
                (target / 'capacity-calibration.json').write_text(json.dumps(calibration))
                self.assertFalse(feature_evidence.capacity_summary(now=1001)['markup_enabled'])
