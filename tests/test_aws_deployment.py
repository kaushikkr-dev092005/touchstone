import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal

from tools.aws_preflight import inspect, read_aws, default_configured

ROOT=Path(__file__).resolve().parent.parent
ACCOUNT='123456789012'


class AwsPreflightTests(unittest.TestCase):
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

    def test_billing_endpoint_does_not_change_deployment_region(self):
        seen=[]
        def runner(command,**kwargs):seen.extend(command);return subprocess.CompletedProcess(command,0,'{}','')
        with patch('tools.aws_preflight.shutil.which',return_value='aws'):
            read_aws('freetier','get-account-plan-state',runner=runner)
        self.assertEqual(seen[seen.index('--region')+1],'us-east-1')

    def test_credentials_and_endpoint_overrides_are_not_forwarded(self):
        observed={}
        def runner(command,**kwargs):
            observed.update(command=command,env=kwargs['env'])
            return subprocess.CompletedProcess(command,0,'{"Account":"123456789012"}','')
        with patch('tools.aws_preflight.shutil.which',return_value='aws'), patch.dict('os.environ',{
            'AWS_ACCESS_KEY_ID':'fixture-only','AWS_SECRET_ACCESS_KEY':'fixture-only',
            'AWS_ENDPOINT_URL':'https://example.invalid','AGENT_PRIVATE_KEY':'fixture-only',
            'AIRWALLEX_API_KEY':'fixture-only','ANTHROPIC_API_KEY':'fixture-only'}):
            read_aws('sts','get-caller-identity',runner=runner)
        for name in ('AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_ENDPOINT_URL','AGENT_PRIVATE_KEY','AIRWALLEX_API_KEY','ANTHROPIC_API_KEY'):
            self.assertNotIn(name,observed['env'])
        self.assertIn('default',observed['command']);self.assertIn('ap-south-1',observed['command'])

    def test_permission_errors_are_redacted(self):
        def runner(command,**kwargs):return subprocess.CompletedProcess(command,1,'','AccessDenied fixture-only-credential-detail')
        with patch('tools.aws_preflight.shutil.which',return_value='aws'):
            with self.assertRaisesRegex(RuntimeError,'^ACCESSDENIED$'):read_aws('sts','get-caller-identity',runner=runner)


class AwsInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template=json.loads((ROOT/'deploy/aws/cloudformation.json').read_text())
        cls.resources=cls.template['Resources']

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
        fixed=(D(r['ec2_usd_per_hour'])+D(r['ipv4_usd_per_hour']))*r['month_hours']+D(r['storage_planning_allowance_usd_per_gib_month'])*(plan['root_gp3_gib']+plan['retained_data_gp3_gib'])
        total=fixed*(1+D(r['tax_planning_reserve_fraction']))+D(r['other_usage_planning_reserve_usd'])
        self.assertEqual(total,D(r['all_in_estimate_usd']));self.assertGreater(total,D('10'))
        self.assertFalse(r['within_approved_ceiling'])
        self.assertLessEqual(D(plan['conditional_alternative']['planning_total_usd']),D('10'))
        self.assertFalse(plan['final_provisioning_approval']);self.assertFalse(plan['promotional_credit_eligibility_verified'])
        self.assertFalse(plan['budget_is_hard_cap']);self.assertEqual(plan['aws_resources_created'],0)


if __name__=='__main__':unittest.main()
