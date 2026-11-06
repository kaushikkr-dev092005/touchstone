import json
from pathlib import Path
import re
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from touchstone.live import LiveSession, mandate_from_args
from touchstone.server import serve


class NoQuoteClient:
    """Stands in for the Metal bridge: no provider quotes, and any payment attempt is a test failure."""
    mode = 'TESTNET'
    provider_url = 'http://127.0.0.1:9'

    def __init__(self, *args, **kwargs):
        self.paid = 0
        self.execute = kwargs.get('execute')

    def quote(self, url):
        raise RuntimeError('no live provider in this test')

    def pay(self, *args, **kwargs):
        self.paid += 1
        raise AssertionError('payment must never be dispatched')

    def invoke(self, command, **fields):
        return []


def mandate(**overrides):
    values = dict(scope='live_test', provider_urls=['http://127.0.0.1:9'], budget_usd='0.50', price_cap_usd='0.05', steps=3)
    values.update(overrides)
    return mandate_from_args(**values)


class LiveModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)

    def session(self, m=None, phrase=None):
        m = m or mandate()
        return LiveSession(self.temp.name, m, phrase or m.phrase(), client_factory=NoQuoteClient)

    def test_requires_exact_authorization_and_binds_terms_to_scope(self):
        m = mandate()
        for bad in (None, '', m.phrase() + ' ', m.phrase().replace('0.500000', '0.600000')):
            with self.assertRaises(ValueError):
                LiveSession(self.temp.name, m, bad, client_factory=NoQuoteClient)
        first = self.session(m)
        other = mandate(budget_usd='0.40')
        with self.assertRaisesRegex(ValueError, 'different'):
            LiveSession(self.temp.name, other, other.phrase(), client_factory=NoQuoteClient)
        self.assertEqual(self.session(m).run_id, first.run_id)

    def test_limits_and_origins_are_validated(self):
        for kwargs in ({'budget_usd': '9'}, {'steps': 0}, {'steps': 51}, {'price_cap_usd': '0.60'},
                       {'provider_urls': ['http://example.com']}, {'provider_urls': ['http://127.0.0.1:9'] * 2},
                       {'provider_urls': ['http://u:p@127.0.0.1:9']}, {'scope': '../x'}):
            with self.assertRaises(ValueError):
                mandate(**kwargs)

    def test_server_enforces_confirmation_and_disables_simulated_controls(self):
        live = self.session()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        threading.Thread(target=serve, args=(port, self.temp.name, live), daemon=True).start()
        base = f'http://127.0.0.1:{port}'
        for _ in range(80):
            try:
                page = urllib.request.urlopen(base + '/', timeout=1).read().decode(); break
            except OSError:
                time.sleep(.1)
        token = re.search(r'name="touchstone-token" content="([^"]+)"', page).group(1)

        def post(path, body):
            request = urllib.request.Request(base + path, json.dumps(body).encode(), {'Content-Type': 'application/json', 'X-Touchstone-Token': token})
            try:
                with urllib.request.urlopen(request, timeout=5) as r:
                    return r.status, json.load(r)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)
        state = json.load(urllib.request.urlopen(base + '/api/state'))
        self.assertEqual(state['live']['mode'], 'LIVE_TESTNET_AUTHORIZED')
        self.assertEqual(state['live']['customer_hold'], 'SIMULATED')
        for path in ('/api/demo', '/api/close', '/api/approve-increase'):
            self.assertEqual(post(path, {})[0], 409)
        self.assertEqual(post('/api/live/run', {})[0], 400)
        self.assertEqual(post('/api/live/run', {'confirm_budget_usd': '0.5'})[0], 400)
        self.assertEqual(post('/api/resume', {})[0], 400)
        status, body = post('/api/live/quote', {})
        self.assertEqual(status, 200); self.assertEqual(body['payments_sent'], 0); self.assertEqual(body['quotes'], [])
        status, body = post('/api/live/run', {'confirm_budget_usd': '0.500000'})
        self.assertEqual(status, 202)
        for _ in range(50):
            if json.load(urllib.request.urlopen(base + '/api/state'))['jobs'][0]['status'] == 'PAUSED_POLICY':
                break
            time.sleep(.1)
        final = json.load(urllib.request.urlopen(base + '/api/state'))
        self.assertEqual(final['jobs'][0]['status'], 'PAUSED_POLICY')
        self.assertEqual(final['live']['rail_spent_micro_usd'], 0)
        self.assertEqual(json.load(urllib.request.urlopen(base + '/api/fault-receipts'))['refund_executed'], False)


if __name__ == '__main__':
    unittest.main()
