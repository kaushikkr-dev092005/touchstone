"""Measured local decode throughput and an auditable capacity-pricing calibration.

Pricing principle: a seller's marginal cost is GPU-seconds, which is completion tokens divided
by observed decode throughput. The calibrated multiplier is therefore baseline_tps / recent_tps,
clamped to [1, max_multiplier]. It is driven by measured throughput only; temperature, power and
clock readings are recorded as context and never price a quote.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
import statistics
import time
import urllib.request
from urllib.parse import urlparse

VERSION = 'touchstone-capacity-calibration-v1'
MAX_MULTIPLIER_LIMIT = 1.5
VALID_SECONDS = 7 * 24 * 3600
PROMPT = ('Return one JSON object only. Count aloud from one to forty as words in the field "numbers", '
          'then explain in the field "note" why steady inference throughput matters for pricing.')


def decode_rate(raw, elapsed_s):
    """Prefer the server's own decode timing; otherwise completion tokens over wall time."""
    tokens = (raw.get('usage') or {}).get('completion_tokens')
    if type(tokens) is not int or tokens <= 0 or elapsed_s <= 0:
        raise ValueError('Response has no usable completion-token count')
    timings = raw.get('timings') or {}
    reported = timings.get('predicted_per_second')
    if isinstance(reported, (int, float)) and not isinstance(reported, bool) and 0 < reported < 1e6:
        return tokens, float(reported), 'SERVER_DECODE_TIMING'
    return tokens, tokens / elapsed_s, 'WALL_CLOCK_INCLUDING_PROMPT'


def http_request(url, model, max_tokens, prompt=PROMPT, timeout=120):
    parsed = urlparse(url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise ValueError('Throughput measurement is limited to a loopback HTTP endpoint')
    body = json.dumps({'model': model, 'temperature': 0, 'max_tokens': max_tokens,
                       'messages': [{'role': 'user', 'content': prompt}]}).encode()
    request = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)
    return raw, time.perf_counter() - started


def measure(requester, sampler, *, model, runs=24, max_tokens=(64, 128, 256), clock=time.time):
    """Sequential calls, each paired with a hardware sample taken immediately afterwards."""
    samples = []
    for index in range(runs):
        limit = max_tokens[index % len(max_tokens)]
        raw, elapsed = requester(model, limit)
        tokens, rate, basis = decode_rate(raw, elapsed)
        hardware = sampler()
        samples.append({'index': index, 'observed_at': clock(), 'max_tokens': limit, 'completion_tokens': tokens,
                        'elapsed_s': round(elapsed, 4), 'decode_tps': round(rate, 3), 'basis': basis,
                        'telemetry': {k: hardware.get(k) for k in ('sample_id', 'temperature_c', 'gpu_utilization_percent',
                                      'power_w', 'sm_clock_mhz', 'thermal_throttling_active')}})
    return samples


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def calibrate(samples, *, model, model_sha256, max_multiplier=1.25, minimum_samples=20, now=None):
    """Fit the pricing coefficients from raw samples, or refuse. Never extrapolates a trend."""
    now = time.time() if now is None else now
    if not 1 < max_multiplier <= MAX_MULTIPLIER_LIMIT:
        raise ValueError('Maximum multiplier must be in (1, %s]' % MAX_MULTIPLIER_LIMIT)
    if not isinstance(model_sha256, str) or len(model_sha256) != 64:
        raise ValueError('A pinned model digest is required for a calibration')
    usable = [s for s in samples if s['basis'] == 'SERVER_DECODE_TIMING' and s['telemetry'].get('thermal_throttling_active') is not True]
    if len(usable) < minimum_samples:
        raise ValueError(f'At least {minimum_samples} unthrottled server-timed samples are required; got {len(usable)}')
    rates = [s['decode_tps'] for s in usable]
    median, spread = statistics.median(rates), statistics.pstdev(rates)
    if median <= 0 or spread / median > 0.5:
        raise ValueError('Throughput is too unstable to calibrate a price coefficient')
    ordered = sorted(rates)
    # Distribution-free 90% interval for the median, from order statistics.
    n = len(ordered)
    half = 0.82 * math.sqrt(n)
    low, high = ordered[max(0, int(n / 2 - half))], ordered[min(n - 1, int(math.ceil(n / 2 + half)))]
    body = {'version': VERSION, 'model': model, 'model_sha256': model_sha256,
            'fitted_at': datetime.fromtimestamp(now, timezone.utc).isoformat(), 'valid_until': now + VALID_SECONDS,
            'samples': n, 'baseline_tps': round(median, 3), 'baseline_tps_interval_90': [low, high],
            'coefficient_of_variation': round(spread / median, 4), 'max_multiplier': max_multiplier,
            'minimum_live_samples': 5,
            'pricing_rule': 'multiplier = clamp(baseline_tps / median(recent live decode tps), 1, max_multiplier)',
            'temperature_changes_price': False,
            'excluded_samples': {'throttled': sum(s['telemetry'].get('thermal_throttling_active') is True for s in samples),
                                 'not_server_timed': sum(s['basis'] != 'SERVER_DECODE_TIMING' for s in samples)},
            'sample_set_sha256': hashlib.sha256(json.dumps(samples, sort_keys=True).encode()).hexdigest()}
    return {'label': 'MEASURED', 'body': body,
            'digest': hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


def verify(calibration, model_sha256, now=None):
    now = time.time() if now is None else now
    body = calibration['body']
    expected = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if body.get('version') != VERSION or calibration.get('digest') != expected:
        raise ValueError('Calibration was altered')
    if body['model_sha256'] != model_sha256:
        raise ValueError('Calibration belongs to a different model')
    if now > body['valid_until']:
        raise ValueError('Calibration expired; remeasure')
    return True


def multiplier(calibration, recent_tps, now=None):
    """Quote multiplier from live decode samples. 1.0 whenever evidence is missing or invalid."""
    try:
        body = calibration['body']
        verify(calibration, body['model_sha256'], now)
        if len(recent_tps) < body['minimum_live_samples']:
            return 1.0
        recent = statistics.median(recent_tps)
        return min(body['max_multiplier'], max(1.0, body['baseline_tps'] / recent)) if recent > 0 else 1.0
    except (KeyError, TypeError, ValueError, statistics.StatisticsError):
        return 1.0
