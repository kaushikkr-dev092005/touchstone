import json
import contextlib
import hashlib
import io
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal

from tools.aws_preflight import inspect, read_aws, default_configured, find_aws_cli, main, READ_CHECKS_COMPLETE
from tools.aws_cost_review import estimate

ROOT=Path(__file__).resolve().parent.parent
ACCOUNT='123456789012'


class AwsPreflightTests(unittest.TestCase):
    def completed_reads(self, *, plan=None, offered=True, instance_type='t4g.micro'):
        responses=[{'Account':ACCOUNT},
            {'Regions':[{'RegionName':'ap-south-1','OptInStatus':'opt-in-not-required'}]},
            {'InstanceTypeOfferings':[{'InstanceType':instance_type,'Location':'ap-south-1'}] if offered else []},
            plan if plan is not None else {'accountId':ACCOUNT,'accountPlanType':'FREE','accountPlanStatus':'ACTIVE'}]
        with patch('tools.aws_preflight.read_aws',side_effect=responses) as reader:
            return inspect(ACCOUNT,configured=True,reader=reader,instance_type=instance_type), reader.call_count

    def cli_exit(self, result):
        (ROOT/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as directory:
            output=Path(directory)/'preflight.json'
            with patch('tools.aws_preflight.inspect',return_value=result), contextlib.redirect_stdout(io.StringIO()):
                code=main(['--expected-account',ACCOUNT,'--output',str(output)])
            self.assertEqual(json.loads(output.read_text()),result)
            return code

    def test_missing_cli_is_reported_without_aws_calls(self):
        with patch('tools.aws_preflight.find_aws_cli',return_value=None):
            result=inspect(ACCOUNT,configured=True)
        self.assertEqual(result['status'],'AWS_CLI_NOT_INSTALLED')
        self.assertFalse(result['read_only_checks_passed'])
        self.assertEqual(self.cli_exit(result),2)

    def test_cli_discovery_supports_existing_windows_per_user_install(self):
        with tempfile.TemporaryDirectory() as directory:
            binary=Path(directory)/'Programs/Amazon/AWSCLIV2/aws.exe'
            binary.parent.mkdir(parents=True);binary.touch()
            with patch('tools.aws_preflight.sys.platform','win32'), \
                    patch('tools.aws_preflight.shutil.which',return_value=None), \
                    patch.dict('os.environ',{'LOCALAPPDATA':directory},clear=True):
                self.assertEqual(find_aws_cli(),str(binary))

    def test_completed_reads_do_not_authorize_resources(self):
        result,calls=self.completed_reads()
        self.assertEqual(calls,4)
        self.assertTrue(result['read_only_checks_passed'])
        self.assertEqual(result['status'],READ_CHECKS_COMPLETE)
        self.assertEqual(self.cli_exit(result),0)
        self.assertFalse(result['provisioning_authorized'])
        self.assertEqual(result['aws_resources_created'],0)

    def test_late_account_mismatch_cannot_return_success(self):
        result,_=self.completed_reads(plan={'accountId':'999999999999'})
        self.assertTrue(result['identity_verified'] and result['region_available'] and result['instance_offered'])
        self.assertEqual(result['status'],'AWS_ACCOUNT_MISMATCH')
        self.assertFalse(result['read_only_checks_passed'])
        self.assertEqual(self.cli_exit(result),2)

    def test_unknown_or_inactive_account_plan_fails_closed(self):
        for plan_type,status,reason in [('UNKNOWN','ACTIVE','AWS_ACCOUNT_PLAN_UNVERIFIED'),
                ('FREE','NOT_STARTED','AWS_ACCOUNT_PLAN_NOT_ACTIVE'),('PAID','EXPIRED','AWS_ACCOUNT_PLAN_NOT_ACTIVE')]:
            with self.subTest(plan_type=plan_type,status=status):
                result,_=self.completed_reads(plan={'accountId':ACCOUNT,'accountPlanType':plan_type,'accountPlanStatus':status})
                self.assertEqual(result['status'],reason)
                self.assertFalse(result['read_only_checks_passed'])
                self.assertEqual(self.cli_exit(result),2)

    def test_unoffered_instance_stops_before_billing_check(self):
        result,calls=self.completed_reads(offered=False)
        self.assertEqual(calls,3)
        self.assertEqual(result['status'],'INSTANCE_TYPE_NOT_OFFERED')
        self.assertFalse(result['read_only_checks_passed'])
        self.assertEqual(self.cli_exit(result),2)

    def test_billing_permission_failure_cannot_return_success(self):
        answers=[{'Account':ACCOUNT},
            {'Regions':[{'RegionName':'ap-south-1','OptInStatus':'opt-in-not-required'}]},
            {'InstanceTypeOfferings':[{'InstanceType':'t4g.micro','Location':'ap-south-1'}]},RuntimeError('ACCESSDENIED')]
        with patch('tools.aws_preflight.read_aws',side_effect=answers) as reader:
            result=inspect(ACCOUNT,configured=True,reader=reader)
        self.assertEqual(result['status'],'ACCESSDENIED')
        self.assertEqual(self.cli_exit(result),2)

    def test_missing_default_never_uses_another_account(self):
        def unexpected(*args):self.fail('No AWS call permitted without the configured default profile')
        result=inspect(ACCOUNT,configured=False,reader=unexpected)
        self.assertEqual(result['status'],'AWS_PROFILE_NOT_CONFIGURED')
        self.assertEqual(result['aws_resources_created'],0)

    def test_region_only_profile_is_not_authentication(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{},clear=True):
            path=Path(directory)/'config';path.write_text('[default]\nregion=ap-south-1\n')
            self.assertFalse(default_configured(directory))
            path.write_text('[default]\nsso_session=existing-user-session\nregion=ap-south-1\n')
            self.assertTrue(default_configured(directory))
            path.write_text('[default]\nlogin_session=arn:aws:iam::123456789012:user/fixture\nregion=ap-south-1\n')
            self.assertTrue(default_configured(directory))

    def test_account_mismatch_stops_all_further_checks(self):
        calls=[]
        def reader(*args):calls.append(args);return {'Account':'999999999999'}
        self.assertEqual(inspect(ACCOUNT,configured=True,reader=reader)['status'],'AWS_ACCOUNT_MISMATCH')
        self.assertEqual(calls,[('sts','get-caller-identity')])

    def test_actual_credit_balance_does_not_authorize_provisioning(self):
        def reader(service,operation,*args):
            if service=='sts':return {'Account':ACCOUNT}
            if operation=='describe-regions':return {'Regions':[{'RegionName':'ap-south-1','OptInStatus':'opt-in-not-required'}]}
            if operation=='describe-instance-type-offerings':return {'InstanceTypeOfferings':[{'InstanceType':'t4g.micro','Location':'ap-south-1'}]}
            return {'accountId':ACCOUNT,'accountPlanType':'FREE','accountPlanStatus':'ACTIVE',
                    'accountPlanRemainingCredits':{'amount':100,'unit':'USD'}}
        result=inspect(ACCOUNT,configured=True,reader=reader)
        self.assertTrue(result['identity_verified'] and result['region_available'] and result['instance_offered'])
        self.assertFalse(result['provisioning_authorized'])
        self.assertEqual(result['promotional_credit_service_eligibility'],'NOT_VERIFIED')

    def test_no_financial_write_or_billed_cost_explorer_query(self):
        for service,operation in [('ec2','run-instances'),('cloudformation','deploy'),
                ('budgets','create-budget'),('freetier','upgrade-account-plan'),('ce','get-cost-and-usage')]:
            with self.assertRaisesRegex(ValueError,'NOT_READ_ONLY'):read_aws(service,operation)

    def test_free_plan_cannot_silently_select_nano(self):
        def reader(service,operation,*args):
            if service=='sts':return {'Account':ACCOUNT}
            if operation=='describe-regions':return {'Regions':[{'RegionName':'ap-south-1','OptInStatus':'opt-in-not-required'}]}
            if operation=='describe-instance-type-offerings':return {'InstanceTypeOfferings':[{'InstanceType':'t4g.nano','Location':'ap-south-1'}]}
            return {'accountId':ACCOUNT,'accountPlanType':'FREE','accountPlanStatus':'ACTIVE'}
        result=inspect(ACCOUNT,configured=True,reader=reader,instance_type='t4g.nano')
        self.assertEqual(result['status'],'FREE_PLAN_INSTANCE_NOT_ELIGIBLE')
        self.assertFalse(result['provisioning_authorized'])
        self.assertFalse(result['read_only_checks_passed'])
        self.assertEqual(self.cli_exit(result),2)

    def test_billing_endpoint_does_not_change_deployment_region(self):
        seen=[]
        def runner(command,**kwargs):seen.extend(command);return subprocess.CompletedProcess(command,0,'{}','')
        with patch('tools.aws_preflight.find_aws_cli',return_value='aws'):
            read_aws('freetier','get-account-plan-state',runner=runner)
        self.assertEqual(seen[seen.index('--region')+1],'us-east-1')

    def test_credentials_and_endpoint_overrides_are_not_forwarded(self):
        observed={}
        def runner(command,**kwargs):
            observed.update(command=command,env=kwargs['env'])
            return subprocess.CompletedProcess(command,0,'{"Account":"123456789012"}','')
        with patch('tools.aws_preflight.find_aws_cli',return_value='aws'), patch.dict('os.environ',{
            'AWS_ACCESS_KEY_ID':'fixture-only','AWS_SECRET_ACCESS_KEY':'fixture-only',
            'AWS_ENDPOINT_URL':'https://example.invalid','AGENT_PRIVATE_KEY':'fixture-only',
            'AIRWALLEX_API_KEY':'fixture-only','ANTHROPIC_API_KEY':'fixture-only'}):
            read_aws('sts','get-caller-identity',runner=runner)
        for name in ('AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_ENDPOINT_URL','AGENT_PRIVATE_KEY','AIRWALLEX_API_KEY','ANTHROPIC_API_KEY'):
            self.assertNotIn(name,observed['env'])
        self.assertIn('default',observed['command']);self.assertIn('ap-south-1',observed['command'])
        self.assertEqual(observed['env']['AWS_CLI_AUTO_PROMPT'],'off')

    def test_permission_errors_are_redacted(self):
        def runner(command,**kwargs):return subprocess.CompletedProcess(command,1,'','AccessDenied fixture-only-credential-detail')
        with patch('tools.aws_preflight.find_aws_cli',return_value='aws'):
            with self.assertRaisesRegex(RuntimeError,'^ACCESSDENIED$'):read_aws('sts','get-caller-identity',runner=runner)


class AwsInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template=json.loads((ROOT/'deploy/aws/cloudformation.json').read_text())
        cls.resources=cls.template['Resources']

    def test_guard_findings_are_bound_to_the_reviewed_template(self):
        report=json.loads((ROOT/'deploy/aws/guard-review.json').read_text())
        self.assertEqual(report['template_hash_normalization'],'CRLF_TO_LF_ONLY')
        normalized=(ROOT/report['template']).read_bytes().replace(b'\r\n',b'\n')
        self.assertEqual(report['template_sha256'],hashlib.sha256(normalized).hexdigest())
        self.assertEqual(sum(report['outcomes'].values()),report['rule_files'])
        self.assertEqual(len(report['failed_rules']),report['outcomes']['FAIL'])
        self.assertEqual(report['status'],'FAIL')
        self.assertNotEqual(report['guard_exit_code'],0)
        self.assertEqual(report['aws_resources_created'],0)
        self.assertEqual(report['suppressed_rules'],[])
        self.assertEqual({r['rule'] for r in report['failed_rules']},{
            'EC2_INSTANCE_DETAILED_MONITORING_ENABLED','EC2_SECURITY_GROUP_EGRESS_OPEN_TO_WORLD_RULE',
            'EC2_SECURITY_GROUP_INGRESS_OPEN_TO_WORLD_RULE','NO_UNRESTRICTED_ROUTE_TO_IGW',
            'SECURITY_GROUP_INGRESS_CIDR_NON_32_RULE'})
        self.assertEqual(report['baseline']['source_revision'],'eaaba69bbf6d9035c52aebb187f50eecbaf5db06')

    def test_actionable_guard_fixes_preserve_controls(self):
        self.assertTrue(self.resources['Instance']['Properties']['EbsOptimized'])
        group=self.resources['SecurityGroup']['Properties']
        for rule in group['SecurityGroupIngress']+group['SecurityGroupEgress']:
            self.assertTrue(rule['Description'])
        key=self.template['Parameters']['EbsKmsKeyArn']
        self.assertNotIn('Default',key)
        self.assertIsNotNone(re.fullmatch(key['AllowedPattern'],'arn:aws:kms:ap-south-1:123456789012:key/1234abcd-1234-abcd-1234-123456789abc'))
        for arn in ['alias/aws/ebs','arn:aws:kms:us-east-1:123456789012:key/1234abcd-1234-abcd-1234-123456789abc']:
            self.assertIsNone(re.fullmatch(key['AllowedPattern'],arn))
        self.assertEqual(self.resources['DataVolume']['Properties']['KmsKeyId'],{'Ref':'EbsKmsKeyArn'})
        self.assertEqual(self.resources['Instance']['Properties']['BlockDeviceMappings'][0]['Ebs']['KmsKeyId'],{'Ref':'EbsKmsKeyArn'})
        self.assertFalse(any(resource['Type']=='AWS::KMS::Key' for resource in self.resources.values()))
        self.assertEqual(self.template['Metadata']['AWSToolsMetrics']['AWSAgentToolkit'],'aws-cloudformation@3')

    def test_no_expensive_managed_service_or_financial_resource(self):
        forbidden={'AWS::EC2::NatGateway','AWS::ECS::Cluster','AWS::EKS::Cluster',
            'AWS::RDS::DBInstance','AWS::ElasticLoadBalancingV2::LoadBalancer','AWS::CloudFront::Distribution','AWS::SecretsManager::Secret'}
        self.assertFalse({r['Type'] for r in self.resources.values()} & forbidden)
        instance=self.resources['Instance']['Properties']
        self.assertEqual(instance['InstanceType'],{'Ref':'InstanceType'})
        self.assertEqual(self.template['Parameters']['InstanceType']['Default'],'t4g.micro')
        self.assertEqual(instance['CreditSpecification']['CPUCredits'],'standard')
        self.assertNotIn('KeyName',instance)

    def test_network_and_metadata_boundaries(self):
        ingress=self.resources['SecurityGroup']['Properties']['SecurityGroupIngress']
        self.assertEqual({r['FromPort'] for r in ingress},{80,443})
        self.assertTrue(all(r['FromPort']==r['ToPort'] for r in ingress))
        metadata=self.resources['Instance']['Properties']['MetadataOptions']
        self.assertEqual(metadata['HttpTokens'],'required');self.assertEqual(metadata['HttpPutResponseHopLimit'],1)
        self.assertFalse(self.resources['Subnet']['Properties']['MapPublicIpOnLaunch'])
        self.assertEqual(sum(r['Type']=='AWS::EC2::EIP' for r in self.resources.values()),1)

    def test_persistent_encrypted_volume_survives_stack_removal(self):
        volume=self.resources['DataVolume']
        self.assertTrue(volume['Properties']['Encrypted'])
        self.assertEqual(volume['DeletionPolicy'],'Retain');self.assertEqual(volume['UpdateReplacePolicy'],'Retain')
        self.assertTrue(self.resources['Instance']['Properties']['BlockDeviceMappings'][0]['Ebs']['Encrypted'])

    def test_usage_alerts_do_not_hide_spend_with_credits(self):
        budget=self.resources['UsageBudget']['Properties']
        self.assertEqual(budget['Budget']['BudgetLimit'],{'Amount':10,'Unit':'USD'})
        self.assertFalse(budget['Budget']['CostTypes']['IncludeCredit'])
        self.assertEqual([x['Notification']['Threshold'] for x in budget['NotificationsWithSubscribers']],[50,80,100])

    def test_cost_plan_is_conservative_and_not_approved(self):
        plan=json.loads((ROOT/'deploy/aws/plan.json').read_text());r=plan['pricing'];D=Decimal
        fixed=(D(r['ec2_usd_per_hour'])+D(r['ipv4_usd_per_hour']))*r['month_hours']+D(r['storage_usd_per_gb_month'])*(plan['root_gp3_gib']+plan['retained_data_gp3_gib'])
        total=fixed*(1+D(r['tax_planning_reserve_fraction']))+D(r['other_usage_planning_reserve_usd'])
        self.assertEqual(total,D(r['all_in_estimate_usd']));self.assertGreater(total,D('10'))
        self.assertFalse(r['within_approved_ceiling'])
        self.assertLessEqual(D(plan['conditional_alternative']['planning_total_usd']),D('10'))
        self.assertFalse(plan['final_provisioning_approval']);self.assertFalse(plan['promotional_credit_eligibility_verified'])
        self.assertFalse(plan['budget_is_hard_cap']);self.assertEqual(plan['aws_resources_created'],0)
        self.assertIsNone(plan['approved_budget_satisfied'])
        self.assertFalse(plan['out_of_pocket_target_verified'])
        self.assertIsNone(plan['selected_alternative'])
        self.assertFalse(plan['image_build_completed'])
        self.assertFalse(plan['image_publication_authorized'])


class AwsCostReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.pricing=json.loads((ROOT/'deploy/aws/pricing.json').read_text())

    def test_verified_rate_is_mumbai_gp3_not_an_unverified_allowance(self):
        row=self.pricing['gp3']
        self.assertEqual(row['location'],'Asia Pacific (Mumbai)')
        self.assertEqual(row['usage_type'],'APS3-EBS:VolumeUsage.gp3')
        self.assertEqual(row['unit'],'GB-Mo')
        plan=json.loads((ROOT/'deploy/aws/plan.json').read_text())
        self.assertEqual(estimate(self.pricing,'t4g.micro')['planning_total_usd'],plan['pricing']['all_in_estimate_usd'])
        self.assertEqual(self.pricing['planning']['encrypted_storage_gib'],plan['root_gp3_gib']+plan['retained_data_gp3_gib'])

    def test_stopping_does_not_remove_allocated_ip_or_persistent_storage_cost(self):
        full=estimate(self.pricing,'t4g.micro');stopped=estimate(self.pricing,'t4g.micro',compute_hours=0)
        self.assertEqual(stopped['ipv4_usd'],full['ipv4_usd'])
        self.assertEqual(stopped['storage_usd'],full['storage_usd'])
        self.assertEqual(Decimal(stopped['compute_usd']),0)
        self.assertGreater(Decimal(stopped['fixed_subtotal_usd']),0)

    def test_unknown_account_costs_and_credits_cannot_authorize_candidate(self):
        result=estimate(self.pricing,'t4g.nano')
        self.assertTrue(result['fits_ceiling_before_other_account_usage'])
        self.assertIsNone(result['account_gross_estimate_fits_ceiling'])
        self.assertEqual(result['credit_discount_assumed_usd'],'0.00')
        self.assertFalse(result['out_of_pocket_target_verified'])
        self.assertFalse(result['provisioning_authorized'])

    def test_existing_account_costs_can_make_cheaper_option_exceed_cap(self):
        result=estimate(self.pricing,'t4g.nano',other_account_projected_gross_usd='1')
        self.assertFalse(result['account_gross_estimate_fits_ceiling'])
        self.assertGreater(Decimal(result['projected_account_gross_usd']),Decimal('10'))
        self.assertFalse(result['provisioning_authorized'])

    def test_invalid_cost_inputs_are_rejected(self):
        for value in ['NaN','Infinity','-1',True,'745']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                estimate(self.pricing,'t4g.micro',compute_hours=value)


if __name__=='__main__':unittest.main()
