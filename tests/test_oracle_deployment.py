import configparser
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.oracle_preflight import capacity, inspect, read_oci

ROOT = Path(__file__).resolve().parent.parent


class OraclePreflightTests(unittest.TestCase):
    def settings(self):
        return dict(profile='TOUCHSTONE', region='ap-mumbai-1', tenancy_ocid='test-tenancy',
                    compartment_ocid='test-tenancy', image_ocid='test-image')

    def config(self, directory, tenancy='test-tenancy', token=True):
        path = Path(directory) / 'config'
        path.write_text('[TOUCHSTONE]\ntenancy='+tenancy+'\n'+('security_token_file=test-token\n' if token else ''))
        return path

    def reader(self, command, args):
        values = {
            ('iam', 'tenancy', 'get'): {'id':'test-tenancy'},
            ('iam', 'region-subscription', 'list'): [{'is-home-region':True,'region-name':'ap-mumbai-1','status':'READY'}],
            ('iam', 'availability-domain', 'list'): [{'name':'test-ad'}],
            ('compute', 'image', 'get'): {'operating-system':'Canonical Ubuntu','operating-system-version':'24.04'},
            ('compute', 'shape', 'list'): [{'shape':'VM.Standard.A1.Flex'}],
        }
        return values.get(command, [])

    def test_proposed_two_twelve_fifty_fits_without_claiming_billing(self):
        r=capacity(0,0,0)
        self.assertTrue(r['fits_published_allocation'])
        self.assertEqual(r['projected_ocpu_hours'],'1488')
        self.assertEqual(r['projected_memory_gb_hours'],'8928')
        self.assertFalse(r['always_free_eligibility_verified'])
        self.assertFalse(r['actual_month_to_date_usage_verified'])

    def test_any_existing_a1_allocation_blocks_full_size(self):
        self.assertFalse(capacity(1,6,0)['fits_published_allocation'])
        self.assertFalse(capacity(0,0,151)['fits_published_allocation'])

    def test_invalid_capacity_does_not_become_zero(self):
        for value in (True,-1,'NaN','Infinity',None):
            with self.subTest(value=value), self.assertRaises((ValueError,TypeError)):
                capacity(value,0,0)

    def test_writes_and_transactions_never_invoke_cli(self):
        for command in [('compute','instance','launch'),('bv','volume','create'),('iam','policy','create')]:
            with patch('subprocess.run') as run, self.assertRaises(ValueError):
                read_oci(command,[],cli='oci',profile='TOUCHSTONE',region='ap-mumbai-1',config_file='unused')
            run.assert_not_called()

    def test_missing_profile_and_mismatch_make_no_reads(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('tools.oracle_preflight.find_cli',return_value='oci'):
                with patch('tools.oracle_preflight.read_oci') as read:
                    self.assertEqual(inspect(self.settings(),config_file=Path(d)/'absent')['status'],'OCI_PROFILE_NOT_CONFIGURED')
                    self.assertEqual(inspect(self.settings(),config_file=self.config(d,'other'))['status'],'OCI_TENANCY_MISMATCH')
                read.assert_not_called()

    def test_long_lived_key_profile_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            r=inspect(self.settings(),config_file=self.config(d,token=False),reader=self.reader)
            self.assertEqual(r['status'],'OCI_TEMPORARY_SESSION_REQUIRED')

    def test_complete_reads_still_do_not_authorize_provisioning(self):
        with tempfile.TemporaryDirectory() as d:
            r=inspect(self.settings(),config_file=self.config(d),reader=self.reader)
        self.assertTrue(r['read_only_checks_passed'])
        self.assertFalse(r['provisioning_authorized'])
        self.assertFalse(r['billing_verified'])
        self.assertNotIn('test-tenancy',json.dumps(r))
        self.assertEqual(r['resources_created'],0)

    def test_wrong_home_region_and_image_fail_closed(self):
        for changed, value in [(('iam','region-subscription','list'),[]),(('compute','image','get'),{'operating-system':'Paid Marketplace'})]:
            def reader(command,args):return value if command==changed else self.reader(command,args)
            with tempfile.TemporaryDirectory() as d:
                r=inspect(self.settings(),config_file=self.config(d),reader=reader)
            self.assertFalse(r['read_only_checks_passed'])

    def test_partial_inventory_error_cannot_report_free(self):
        def reader(command,args):
            if command==('bv','volume','list'):raise RuntimeError('private diagnostic not exposed')
            return self.reader(command,args)
        with tempfile.TemporaryDirectory() as d:
            r=inspect(self.settings(),config_file=self.config(d),reader=reader)
        self.assertFalse(r['read_only_checks_passed'])
        self.assertEqual(r['status'],'OCI_READ_FAILED_OR_INCOMPLETE_INVENTORY')
        self.assertNotIn('private diagnostic',json.dumps(r))


class OracleRuntimeTests(unittest.TestCase):
    def test_no_aws_deployment_configuration_remains(self):
        self.assertFalse((ROOT/'deploy/aws').exists() and list((ROOT/'deploy/aws').glob('*')))
        self.assertFalse((ROOT/'.github/workflows/aws-image.yml').exists())

    def test_runtime_preserves_hardening_and_tunnel_default(self):
        compose=(ROOT/'deploy/operator/compose.yaml').read_text()
        self.assertIn('profiles: [https]',compose)
        self.assertIn('user: "10001:10001"',compose)
        self.assertIn('user: "10002:10002"',compose)
        self.assertEqual(compose.count('cap_drop: [ALL]'),2)
        self.assertNotIn('8089:8089',compose)
        self.assertIn('127.0.0.1:8089:8089',(ROOT/'deploy/operator/compose.tunnel.yaml').read_text())

    def test_bootstrap_never_starts_financial_or_application_service(self):
        script=(ROOT/'deploy/oracle/bootstrap.sh.tftpl').read_text()
        self.assertIn('VERSION_ID == 24.04',script)
        self.assertIn('https://download.docker.com/linux/ubuntu',script)
        self.assertIn('ufw default deny incoming',script)
        self.assertIn('PermitRootLogin no',script)
        self.assertNotIn('systemctl start touchstone',script)
        self.assertNotIn('ufw disable',script)

    def test_runtime_install_never_formats_or_replaces_existing_credentials(self):
        script=(ROOT/'deploy/oracle/install-runtime.sh').read_text()
        self.assertNotIn('mkfs',script)
        self.assertIn('EXISTING_RUNTIME_REQUIRES_REVIEWED_UPDATE',script)
        self.assertIn('IMAGE_REVISION_MISMATCH',script)
        self.assertIn('--pull never --no-build',script)
        self.assertNotIn('systemctl start touchstone',script)


if __name__=='__main__':unittest.main()
