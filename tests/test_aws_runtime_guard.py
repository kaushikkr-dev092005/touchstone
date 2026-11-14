"""Controlled local clocks only. Never powers off, contacts IMDS or invokes AWS."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.aws_runtime_guard import GuardError,epoch,evaluate,run,validate


class RuntimeGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.state=Path(self.directory.name)/'state.sqlite'
        self.policy={'version':1,'approval_reference':'a'*64,'account_id':'123456789012',
            'region':'ap-south-1','instance_type':'t4g.micro','month_utc':'2026-11',
            'window_started_at_utc':'2026-11-01T00:00:00Z','window_ends_at_utc':'2026-11-15T23:50:00Z',
            'prior_consumed_seconds':0,'maximum_compute_seconds':1296000,'stop_margin_seconds':600}
        self.start=epoch(self.policy['window_started_at_utc']);self.end=epoch(self.policy['window_ends_at_utc'])

    def check(self,seconds=10,uptime=10,boot='boot-one',policy=None):
        return evaluate(policy or self.policy,self.state,now=self.start+seconds,uptime=uptime,boot_id=boot)

    def test_normal_execution_records_allocation_not_an_aws_billing_claim(self):
        result=self.check()
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['conservative_allocated_seconds'],10)
        self.assertFalse(result['billing_meter']);self.assertFalse(result['financial_dispatch_enabled'])

    def test_reboot_and_manual_stop_start_do_not_reset_elapsed_allocation(self):
        self.check(60,60)
        result=self.check(7200,15,'boot-two')
        self.assertEqual(result['conservative_allocated_seconds'],7200)
        self.assertEqual(result['observed_host_seconds'],75)
        self.assertEqual(result['status'],'PASS')

    def test_manual_start_after_window_stops_immediately(self):
        self.check()
        result=self.check(self.end-self.start+30,10,'manual-start')
        self.assertEqual(result['reason'],'RUNTIME_WINDOW_EXHAUSTED')

    def test_expired_window_is_blocked_even_without_prior_state(self):
        self.assertEqual(self.check(self.end-self.start,1)['status'],'STOP')

    def test_month_rollover_never_grants_fresh_allowance(self):
        self.check()
        self.assertEqual(self.check(epoch('2026-12-01T00:00:00Z')-self.start,10,'new-boot')['reason'],'MONTH_NOT_AUTHORIZED')

    def test_start_before_approved_window_is_blocked(self):
        policy=copy.deepcopy(self.policy);policy['window_started_at_utc']='2026-11-02T00:00:00Z'
        self.assertEqual(self.check(86399,0,policy=policy)['reason'],'WINDOW_NOT_STARTED')

    def test_prior_consumption_is_counted(self):
        policy=copy.deepcopy(self.policy);policy['prior_consumed_seconds']=3600
        policy['window_ends_at_utc']='2026-11-15T22:50:00Z'
        self.assertEqual(self.check(60,60,policy=policy)['conservative_allocated_seconds'],3660)

    def test_time_rollback_and_uptime_rollback_fail_closed(self):
        self.check(60,60)
        with self.assertRaisesRegex(GuardError,'RUNTIME_CLOCK_ROLLBACK'):self.check(30,90)
        with self.assertRaisesRegex(GuardError,'RUNTIME_CLOCK_INVALID'):self.check(61,10)

    def test_monotonic_elapsed_cannot_be_hidden_by_small_wall_adjustment(self):
        self.check(60,60)
        self.assertEqual(self.check(59,120)['conservative_allocated_seconds'],120)

    def test_forward_jump_stops_conservatively(self):
        self.check()
        self.assertEqual(self.check(self.end-self.start+1,11)['status'],'STOP')

    def test_changed_policy_cannot_renew_old_state(self):
        self.check();policy=copy.deepcopy(self.policy);policy['approval_reference']='b'*64
        with self.assertRaisesRegex(GuardError,'RUNTIME_POLICY_CHANGED'):self.check(11,11,policy=policy)

    def test_margin_and_prior_usage_must_fit_existing_ceiling(self):
        for key,value in [('prior_consumed_seconds',1),('stop_margin_seconds',601),('maximum_compute_seconds',1296001)]:
            policy=copy.deepcopy(self.policy);policy[key]=value
            with self.subTest(key=key),self.assertRaises(GuardError):validate(policy)

    def test_invalid_or_ambiguous_policy_is_rejected(self):
        for key,value in [('version',True),('region','us-east-1'),('account_id',123456789012),
                ('maximum_compute_seconds','1296000'),('window_ends_at_utc','2026-11-31T00:00:00Z'),('approved',True)]:
            policy=copy.deepcopy(self.policy);policy[key]=value
            with self.subTest(key=key),self.assertRaises(GuardError):validate(policy)

    def test_parallel_checks_serialize_and_restart_preserves_state(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda _:self.check(60,60),range(16)))
        self.assertTrue(all(r['conservative_allocated_seconds']==60 for r in results))
        self.assertEqual(self.check(90,90)['conservative_allocated_seconds'],90)

    def test_missing_or_corrupt_policy_and_state_return_stop(self):
        policy_path=Path(self.directory.name)/'policy.json'
        self.assertEqual(run(policy_path,self.state,now=self.start,boot_id='x',uptime=0)['status'],'STOP')
        policy_path.write_text(json.dumps(self.policy));self.state.write_bytes(b'not sqlite')
        self.assertEqual(run(policy_path,self.state,now=self.start,boot_id='x',uptime=0)['reason'],'RUNTIME_STATE_OR_POLICY_UNAVAILABLE')

    def test_inspect_mode_never_reads_identity_or_requests_poweroff(self):
        policy_path=Path(self.directory.name)/'policy.json';policy_path.write_text(json.dumps(self.policy))
        def forbidden():self.fail('Inspection cannot contact IMDS or power off')
        result=run(policy_path,self.state,now=self.end+1,boot_id='x',uptime=0,identity_reader=forbidden,stopper=forbidden)
        self.assertEqual(result['status'],'STOP')


if __name__=='__main__':unittest.main()
