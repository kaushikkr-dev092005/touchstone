import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from tools import run_project as runner
from tools import configure_metal_rpc as rpc_setup
from tools import run_local


class RuntimeTests(unittest.TestCase):
    def test_service_environments_keep_secrets_in_their_own_process(self):
        env = {'AIRWALLEX_API_KEY': 'PRIVATE_BANK', 'AGENT_PRIVATE_KEY': 'PRIVATE_WALLET',
               'ANTHROPIC_API_KEY': 'PRIVATE_HOSTED', 'METAL_RPC_URL': 'PRIVATE_RPC'}
        for service in ('model', 'local_seller', 'premium'):
            child = runner.child_environment(env, service)
            self.assertNotIn('AGENT_PRIVATE_KEY', child)
            self.assertNotIn('AIRWALLEX_API_KEY', child)
            self.assertEqual('ANTHROPIC_API_KEY' in child, service == 'premium')
            if service == 'model':
                self.assertNotIn('METAL_RPC_URL', child)

    def test_existing_healthy_service_is_preserved(self):
        with patch.object(runner, 'health', return_value={'ok': True}), patch.object(runner, 'launch') as start:
            report = runner.ensure(8080, '/health', lambda r: r.get('ok'), ['unused'], {}, True)
        self.assertEqual(report['status'], 'RUNNING')
        self.assertTrue(report['existing_service_kept'])
        start.assert_not_called()

    def test_occupied_port_does_not_replace_unrelated_service(self):
        with patch.object(runner, 'health', return_value={}), patch.object(runner, 'occupied', return_value=True), \
             patch.object(runner, 'launch') as start:
            result = runner.ensure(8080, '/health', bool, ['unused'], {}, True)
        self.assertEqual(result['label'], 'BLOCKED')
        start.assert_not_called()

    def test_status_never_launches_processes(self):
        with patch.object(runner, 'health', return_value={}), patch.object(runner, 'occupied', return_value=False), \
             patch.object(runner, 'launch') as start:
            result = runner.ensure(8080, '/health', bool, ['unused'], {}, False)
        self.assertEqual(result['status'], 'STOPPED')
        start.assert_not_called()

    def test_failed_process_is_reported_without_captured_output(self):
        child = Mock(pid=123, returncode=2)
        child.poll.return_value = 2
        with patch.object(runner, 'health', return_value={}), patch.object(runner, 'occupied', return_value=False), \
             patch.object(runner, 'launch', return_value=child):
            result = runner.ensure(8080, '/health', bool, ['unused'], {}, True)
        self.assertEqual(result['status'], 'START_FAILED')


class GpuGuardTests(unittest.TestCase):
    def test_startup_and_runtime_limits_and_missing_sensor_fail_closed(self):
        observation={'label':'MEASURED','temperature_c':64,'thermal_throttling_active':False}
        self.assertIsNone(run_local.stop_reason(observation,starting=True))
        observation['temperature_c']=65
        self.assertEqual(run_local.stop_reason(observation,starting=True),'GPU_TEMPERATURE_LIMIT')
        self.assertIsNone(run_local.stop_reason(observation))
        observation['temperature_c']=75
        self.assertEqual(run_local.stop_reason(observation),'GPU_TEMPERATURE_LIMIT')
        observation.update(temperature_c=50,thermal_throttling_active=True)
        self.assertEqual(run_local.stop_reason(observation),'GPU_THERMAL_THROTTLING')
        for temperature in (None,float('nan'),-1,'50'):
            observation.update(temperature_c=temperature,thermal_throttling_active=False)
            self.assertEqual(run_local.stop_reason(observation),'GPU_TEMPERATURE_UNAVAILABLE')

    def test_overheat_stops_only_owned_child_without_restart(self):
        child=Mock(returncode=None)
        child.poll.return_value=None
        child.terminate.side_effect=lambda:setattr(child.poll,'return_value',2)
        readings=iter([{'label':'MEASURED','temperature_c':60},
                       {'label':'MEASURED','temperature_c':75}])
        events=[];sleep=Mock()
        self.assertEqual(run_local.supervise(child,observe=lambda:next(readings),sleep=sleep,record=events.append),2)
        child.terminate.assert_called_once();child.kill.assert_not_called()
        sleep.assert_called_once_with(5)
        self.assertEqual(events[-1]['reason'],'GPU_TEMPERATURE_LIMIT')
        self.assertEqual(events[-1]['peak_temperature_c'],75)
        self.assertFalse(events[-1]['automatic_restart'])

    def test_lost_temperature_stops_child_immediately(self):
        child=Mock();child.poll.return_value=None
        child.terminate.side_effect=lambda:setattr(child.poll,'return_value',2)
        sleep=Mock()
        self.assertEqual(run_local.supervise(child,observe=lambda:{'label':'BLOCKED'},sleep=sleep),2)
        child.terminate.assert_called_once();sleep.assert_not_called()


class RpcSetupTests(unittest.TestCase):
    def test_wrong_host_is_refused_before_probe_or_save(self):
        with patch.object(rpc_setup, 'inspect_rpc') as probe, patch.object(rpc_setup, 'save_rpc') as save:
            with self.assertRaises(ValueError):
                rpc_setup.check('https://example.invalid/private')
        probe.assert_not_called()
        save.assert_not_called()

    def test_rpc_failure_never_saves_configuration(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(rpc_setup, 'inspect_rpc', side_effect=RuntimeError), \
             patch.object(rpc_setup, 'save_rpc') as save:
            with self.assertRaises(RuntimeError):
                rpc_setup.check('https://rpc-testnet.metalntwx.com/PRIVATE_FIXTURE')
        save.assert_not_called()

    def test_verified_rpc_saves_no_endpoint_in_public_report(self):
        result = {'connected': True, 'chain_id': 63825, 'transactions_sent': 0}
        with patch.dict(os.environ, {}, clear=True), patch.object(rpc_setup, 'inspect_rpc', return_value=result), \
             patch.object(rpc_setup, 'save_rpc') as save, patch.object(rpc_setup, 'save_status'):
            report = rpc_setup.check('https://rpc-testnet.metalntwx.com/PRIVATE_FIXTURE')
        save.assert_called_once()
        self.assertNotIn('PRIVATE_FIXTURE', str(report))
        self.assertFalse(report['wallet_generated'])
        self.assertFalse(report['money_moved'])


if __name__ == '__main__':
    unittest.main()
