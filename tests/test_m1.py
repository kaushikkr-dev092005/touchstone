"""M1 controlled-adapter evidence: no account access or money movement."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_fx import FakeAirwallex as FakeFX, QUOTE
from test_holds import FakeAirwallex as FakeHolds
from test_banked import FixtureRail
from touchstone.airwallex_doctor import inspect
from touchstone.banked import BankedStore, BankedWorkflow
from touchstone.fx import FxJournal, ConversionOutcomeUnknown
from touchstone.holds import OperationJournal, SandboxHoldWorkflow, OutcomeUnknown, CreateRejected, ScopeRetired
from touchstone.treasury import AirwallexHTTPError
from touchstone.treasury_job import TreasuryFunding
from touchstone.workload import Task


class DoctorTests(unittest.TestCase):
    def test_account_separators_are_valid_but_header_injection_is_not(self):
        for account in ('acct_part_one', 'acct_part-one', 'acct_invalid\r\nX-Test: value'):
            with patch.dict(os.environ, {'AIRWALLEX_CLIENT_ID': 'fixture-client', 'AIRWALLEX_API_KEY': 'fixture-key',
                                         'AIRWALLEX_ACCOUNT_ID': account}, clear=True):
                result = inspect(False)
            self.assertEqual(result['account_context_valid'], '\r' not in account)

    def test_duplicate_client_id_and_key_stops_before_authentication(self):
        with patch.dict(os.environ, {'AIRWALLEX_CLIENT_ID': 'fixture-client', 'AIRWALLEX_API_KEY': 'fixture-client',
                                     'AIRWALLEX_ACCOUNT_ID': 'acct_fixture'}, clear=True):
            result = inspect(True, lambda: self.fail('Invalid credentials reached the network'))
        self.assertIn('CLIENT_ID_IS_NOT_AN_API_KEY', result['blockers'])

    def test_disabled_key_authentication_is_attempted_once_and_redacted(self):
        class Disabled:
            calls = 0
            def authenticate(self):
                self.calls += 1
                raise AirwallexHTTPError(401, 'unauthorized')
            def request(self, *_):
                raise AssertionError('Rejected login must not trigger repeated API requests')
        client = Disabled()
        with patch.dict(os.environ, {'AIRWALLEX_CLIENT_ID': 'fixture-client', 'AIRWALLEX_API_KEY': 'DO_NOT_PRINT',
                                     'AIRWALLEX_ACCOUNT_ID': 'acct_new_account'}, clear=True):
            result = inspect(True, lambda: client)
        self.assertEqual(client.calls, 1)
        self.assertEqual(result['read_probe'], 'BLOCKED_AUTHENTICATION')
        self.assertNotIn('DO_NOT_PRINT', json.dumps(result))
        self.assertEqual(result['reads'], {})

    def test_authenticated_key_with_missing_scopes_is_distinct_from_bad_login(self):
        class Denied:
            def authenticate(self):
                return True
            def request(self, *_):
                raise AirwallexHTTPError(403, 'access_denied')
        with patch.dict(os.environ, {'AIRWALLEX_CLIENT_ID': 'fixture-client', 'AIRWALLEX_API_KEY': 'fixture-key',
                                     'AIRWALLEX_ACCOUNT_ID': 'acct_fixture'}, clear=True):
            result = inspect(True, Denied)
        self.assertTrue(result['authenticated'])
        self.assertEqual(result['read_probe'], 'BLOCKED')

    def test_missing_environment_never_constructs_client_or_reads_files(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'read_text', side_effect=AssertionError('Private file read')):
            result = inspect(True, lambda: self.fail('Network client constructed'))
        self.assertEqual(result['label'], 'BLOCKED')
        self.assertEqual(result['reads'], {})
        self.assertFalse(result['writes_performed'])

    def test_only_gets_and_redacted_read_results_cannot_prove_write_scope(self):
        class ReadClient:
            def request(self, method, path):
                if method != 'GET':
                    raise AssertionError('Doctor must not write')
                if 'history' in path:
                    if not path.endswith('page_size=10'):
                        raise AssertionError('Balance-history API minimum page size is 10')
                    raise AirwallexHTTPError(403, 'access_denied')
                return [{'private': 'DO_NOT_PRINT'}] if path.endswith('/current') else {'items': []}
        with patch.dict(os.environ, {'AIRWALLEX_CLIENT_ID': 'fixture', 'AIRWALLEX_API_KEY': 'DO_NOT_PRINT',
                                     'AIRWALLEX_ACCOUNT_ID': 'acct_fixture'}, clear=True):
            result = inspect(True, ReadClient)
        self.assertTrue(result['reads']['balances']['allowed'])
        self.assertEqual(result['reads']['balance_history']['http_status'], 403)
        self.assertEqual(result['conversion_write']['status'], 'UNVERIFIED')
        self.assertNotIn('DO_NOT_PRINT', json.dumps(result))
        self.assertNotIn('acct_fixture', json.dumps(result))


class RejectedClient(FakeHolds):
    def __init__(self, code='configuration_error', status=400):
        super().__init__()
        self.code, self.status = code, status

    def request(self, method, path, body=None):
        if method == 'POST':
            self.calls.append((method, path, copy.deepcopy(body)))
            raise AirwallexHTTPError(self.status, self.code)
        return super().request(method, path, body)


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = OperationJournal(Path(self.temp.name) / 'holds.sqlite')

    def reject(self, client):
        flow = SandboxHoldWorkflow(client, self.journal)
        with self.assertRaises((OutcomeUnknown, CreateRejected)):
            flow.run('old')
        return flow

    def evidence(self, kind='RECORDED_CONFIGURATION_ERROR'):
        return {'scope': 'old', 'request_id': self.journal.get('old', 'create')['request_id'],
                'kind': kind, 'reference': 'case-123', 'no_object_created': True}

    def test_configuration_rejection_is_definitive_and_consumed_across_restart(self):
        client = RejectedClient()
        self.reject(client)
        self.assertEqual(self.journal.get('old', 'create')['state'], 'REJECTED_NO_OBJECT')
        reopened = SandboxHoldWorkflow(client, OperationJournal(self.journal.path))
        for recover in (False, True):
            with self.assertRaises(CreateRejected):
                reopened.run('old', recover=recover)
        self.assertEqual(sum(c[0] == 'POST' for c in client.calls), 1)

    def test_5xx_configuration_error_remains_unknown(self):
        self.reject(RejectedClient(status=503))
        self.assertEqual(self.journal.get('old', 'create')['state'], 'UNKNOWN')

    def test_duplicate_request_is_consumed_but_does_not_prove_no_object(self):
        client = RejectedClient('duplicate_request')
        flow = self.reject(client)
        self.assertEqual(self.journal.get('old', 'create')['state'], 'REQUEST_ID_CONSUMED')
        with self.assertRaises(OutcomeUnknown):
            flow.run('old', recover=True)
        self.assertEqual(sum(c[0] == 'POST' for c in client.calls), 1)
        with self.assertRaises(ValueError):
            self.journal.retire('old', 'fresh', self.evidence(), client)

    def test_retirement_preserves_request_and_blocks_all_reuse(self):
        client = RejectedClient()
        flow = self.reject(client)
        request_id = self.journal.get('old', 'create')['request_id']
        result = self.journal.retire('old', 'fresh', self.evidence(), client)
        self.assertFalse(result['remote_writes_performed'])
        self.assertEqual(self.journal.get('old', 'create')['request_id'], request_id)
        with self.assertRaises(ScopeRetired):
            flow.run('old', recover=True)
        self.assertTrue(SandboxHoldWorkflow(FakeHolds(), self.journal).run('fresh')['complete'])
        self.assertNotEqual(self.journal.get('fresh', 'create')['request_id'], request_id)

    def test_unknown_requires_support_attestation_and_empty_complete_readback(self):
        client = RejectedClient('duplicate_request')
        self.reject(client)
        evidence = self.evidence('AIRWALLEX_SUPPORT')
        with patch.object(client, 'request', return_value={'items': [], 'has_more': True}):
            with self.assertRaises(OutcomeUnknown):
                self.journal.retire('old', 'fresh', evidence, client)
        with patch.object(client, 'request', return_value={'items': [{'id': 'int_existing'}], 'has_more': False}):
            with self.assertRaises(OutcomeUnknown):
                self.journal.retire('old', 'fresh', evidence, client)
        self.assertEqual(self.journal.retire('old', 'fresh', evidence, client)['state'], 'RETIRED')

    def test_bad_evidence_or_used_replacement_is_rejected(self):
        client = RejectedClient()
        self.reject(client)
        for change in ({'request_id': 'wrong'}, {'no_object_created': False}, {'secret': 'not-allowed'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.journal.retire('old', 'fresh', {**self.evidence(), **change}, client)
        self.journal.bind_terms('fresh', 1000000, 500000)
        with self.assertRaises(ValueError):
            self.journal.retire('old', 'fresh', self.evidence(), client)


class TreasuryJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = BankedStore(root / 'banked.sqlite')
        self.client = FakeFX()
        self.journal = FxJournal(root / 'fx.sqlite')
        self.flow = TreasuryFunding(self.store, self.client, self.journal)
        self.flow.prepare('job', 'fx-one', QUOTE, 'USD', '1.00', '1')

    def execute(self):
        return self.flow.execute('job', True, 'USD', '1.00')

    def test_preview_and_cap_errors_never_convert(self):
        self.assertTrue(self.flow.execute('job')['requires_explicit_execute'])
        for currency, cap in [('EUR', '1'), ('USD', '.99'), ('USD', None), ('USD', 'NaN')]:
            with self.subTest(currency=currency, cap=cap), self.assertRaises(ValueError):
                self.flow.execute('job', True, currency, cap)
        self.assertEqual(self.client.create_count, 0)

    def test_separate_entries_reconcile_once_without_creating_spendable_token_float(self):
        report = self.execute()
        self.assertEqual(report['phase'], 'RECONCILED')
        self.assertEqual(report['label'], 'MOCK')
        self.assertFalse(report['metal_funded'])
        self.assertEqual([e['amount_microunits'] for e in report['accounts']], [-1000000, 920000, 920000])
        self.assertEqual(report['accounts'][-1]['label'], 'SIMULATED')
        self.execute()
        self.flow.reconcile('job')
        self.assertEqual(self.client.create_count, 1)
        with self.store.ledger.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM treasury_entries').fetchone()[0], 3)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM runs').fetchone()[0], 0)
        self.assertTrue(self.store.ledger.audit()['valid'])

    def test_request_or_scope_cannot_be_rebound(self):
        for scope, request, budget in [('other', 'fx-one', '1.00'), ('job', 'new', '1.00'), ('job', 'fx-one', '2.00')]:
            with self.subTest(scope=scope, request=request), self.assertRaises(ValueError):
                self.flow.prepare(scope, request, QUOTE, 'USD', budget, '1')

    def test_pending_or_mismatched_history_cannot_credit_float(self):
        original = self.client.create_conversion
        def mismatch(quote, request):
            result = original(quote, request)
            self.client.history[0]['amount'] = -9
            return result
        self.client.create_conversion = mismatch
        report = self.execute()
        self.assertEqual(report['phase'], 'AWAITING_WALLET_HISTORY')
        self.assertEqual(report['accounts'], [])
        self.client.history[0]['amount'] = -1
        self.assertEqual(self.flow.reconcile('job')['phase'], 'RECONCILED')
        self.assertEqual(self.client.create_count, 1)

    def test_uncertain_conversion_is_never_replaced_or_credited(self):
        def uncertain(*args):
            self.client.create_count += 1
            raise TimeoutError()
        self.client.create_conversion = uncertain
        for _ in range(2):
            with self.assertRaises(ConversionOutcomeUnknown):
                self.execute()
        self.assertEqual(self.client.create_count, 1)
        self.assertEqual(self.flow.report('job')['accounts'], [])

    def test_job_requires_matching_reconciled_treasury_and_separate_token_funding(self):
        bank = SandboxHoldWorkflow(FakeHolds(), OperationJournal(Path(self.temp.name) / 'holds.sqlite'))
        rail = FixtureRail()
        workflow = BankedWorkflow(self.store, bank, rail.factory)
        task = Task('probe', 'arithmetic', {'amounts_cents': [1250, 275, 499], 'discount_cents': 24})
        for request in (None, 'wrong', 'fx-one'):
            with self.assertRaises(ValueError):
                workflow.run('job', task, 'http://127.0.0.1:8092', integration_probe=True, treasury_request_id=request)
        self.execute()
        rail.spendable = 0
        rail.invoke = lambda command: {'usdz_balance_base_units': '0', 'native_balance_base_units': '0', 'address': 'fixture'}
        result = workflow.run('job', task, 'http://127.0.0.1:8092', integration_probe=True, treasury_request_id='fx-one')
        self.assertEqual(result['phase'], 'AWAITING_TESTNET_FUNDS')
        self.assertEqual(rail.payments, 0)
        self.assertEqual(rail.deposits, 0)
        self.assertEqual(result['treasury_funding']['phase'], 'RECONCILED')


class ExecuteGateTests(unittest.TestCase):
    def test_legacy_financial_commands_refuse_before_config_or_service_access(self):
        from touchstone.__main__ import main
        for args in (['airwallex-hold', '--scope', 's'], ['airwallex-hold', '--scope', 's', '--recover'],
                     ['airwallex-checkout', '--scope', 's'], ['banked-job', '--scope', 's', '--integration-probe', '--recover']):
            with self.subTest(command=args), patch('sys.argv', ['touchstone', *args]), \
                 patch('touchstone.config.load_local', side_effect=AssertionError('Private config read')), \
                 contextlib.redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main(), 1)
                self.assertIn('--execute', error.getvalue())


if __name__ == '__main__':
    unittest.main()
