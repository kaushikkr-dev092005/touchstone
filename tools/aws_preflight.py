"""Read-only AWS default-profile checks. Never provisions or invokes Cost Explorer."""
import argparse
import configparser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

REGION = 'ap-south-1'
READ_ONLY = {('sts','get-caller-identity'), ('ec2','describe-regions'),
             ('ec2','describe-instance-type-offerings'), ('freetier','get-account-plan-state')}


def default_configured(directory=None):
    directory = Path(directory) if directory else Path.home()/'.aws'
    paths = [Path(os.environ.get('AWS_CONFIG_FILE', directory/'config')),
             Path(os.environ.get('AWS_SHARED_CREDENTIALS_FILE', directory/'credentials'))]
    for path in paths:
        parser = configparser.RawConfigParser()
        try:
            parser.read(path, encoding='utf-8')
        except (OSError, configparser.Error):
            continue
        if parser.has_section('default') and any(parser.get('default',name,fallback='') for name in
                ('aws_access_key_id','sso_session','sso_start_url','login_session','credential_process','role_arn')):
            return True
    return False


def read_aws(service, operation, extra=(), runner=subprocess.run):
    if (service,operation) not in READ_ONLY:
        raise ValueError('AWS_OPERATION_NOT_READ_ONLY')
    binary = shutil.which('aws')
    if not binary:raise RuntimeError('AWS_CLI_NOT_INSTALLED')
    # Never inherit another AWS account's environment credentials or endpoint overrides.
    env={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','AIRWALLEX_','METAL_','ANTHROPIC_')) and k!='AGENT_PRIVATE_KEY'}
    for name in ('AWS_CONFIG_FILE','AWS_SHARED_CREDENTIALS_FILE'):
        if name in os.environ:env[name]=os.environ[name]
    env.update(AWS_EC2_METADATA_DISABLED='true',AWS_PAGER='',AWS_MAX_ATTEMPTS='1')
    endpoint_region='us-east-1' if service=='freetier' else REGION
    command=[binary,'--profile','default','--region',endpoint_region,'--no-cli-pager','--output','json',
             '--cli-connect-timeout','5','--cli-read-timeout','15',service,operation,*extra]
    response=runner(command,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=25)
    if response.returncode:
        # SDK errors can contain credential/provider details: expose a reason code only.
        reason='AWS_READ_CHECK_FAILED'
        for value in ('AccessDenied','UnauthorizedOperation','ExpiredToken','InvalidClientTokenId','SSO'):
            if value in response.stderr:reason=value.upper()
        raise RuntimeError(reason)
    return json.loads(response.stdout)


def inspect(expected_account, *, configured=None, reader=read_aws, instance_type='t4g.micro'):
    if not re.fullmatch(r'[0-9]{12}',expected_account):raise ValueError('EXPECTED_ACCOUNT_REQUIRED')
    if instance_type not in {'t4g.micro','t4g.nano'}:raise ValueError('UNREVIEWED_INSTANCE_TYPE')
    result={'status':'AWS_PROFILE_NOT_CONFIGURED','profile':'default','region':REGION,
            'aws_cli_available':bool(shutil.which('aws')),
            'identity_verified':False,'region_available':False,'instance_offered':False,'instance_type':instance_type,
            'promotional_credit_service_eligibility':'NOT_VERIFIED',
            'provisioning_authorized':False,'aws_resources_created':0,'financial_operations':0}
    if not (default_configured() if configured is None else configured):return result
    try:
        identity=reader('sts','get-caller-identity')
        if identity.get('Account')!=expected_account:
            result['status']='AWS_ACCOUNT_MISMATCH';return result
        result['identity_verified']=True
        regions=reader('ec2','describe-regions',('--region-names',REGION))
        result['region_available']=any(r.get('RegionName')==REGION and r.get('OptInStatus') in
            {'opt-in-not-required','opted-in'} for r in regions.get('Regions',[]))
        if not result['region_available']:
            result['status']='AWS_REGION_NOT_AVAILABLE';return result
        offers=reader('ec2','describe-instance-type-offerings',('--location-type','region','--filters','Name=instance-type,Values='+instance_type))
        result['instance_offered']=any(o.get('InstanceType')==instance_type and o.get('Location')==REGION
                                      for o in offers.get('InstanceTypeOfferings',[]))
        plan=reader('freetier','get-account-plan-state')
        if plan.get('accountId')!=expected_account:
            result['status']='AWS_ACCOUNT_MISMATCH';return result
        result['account_plan']={k:plan.get(k) for k in ('accountPlanType','accountPlanStatus','accountPlanRemainingCredits','accountPlanExpirationDate')}
        if instance_type=='t4g.nano' and plan.get('accountPlanType')=='FREE':
            result['status']='FREE_PLAN_INSTANCE_NOT_ELIGIBLE';return result
        result['status']='BLOCKED_CREDIT_ELIGIBILITY_AND_FINAL_APPROVAL_REQUIRED' if result['instance_offered'] else 'INSTANCE_TYPE_NOT_OFFERED'
    except (RuntimeError,OSError,ValueError,subprocess.TimeoutExpired) as error:
        result['status']=str(error) if type(error) is RuntimeError else 'AWS_READ_CHECK_FAILED'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-account',required=True)
    parser.add_argument('--instance-type',choices=['t4g.micro','t4g.nano'],default='t4g.micro')
    parser.add_argument('--output',default='tmp/aws-preflight.json')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    output=(root/args.output).resolve()
    if not output.is_relative_to(root/'tmp'):raise ValueError('Reports must stay in ignored tmp/')
    result=inspect(args.expected_account,instance_type=args.instance_type)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if result['identity_verified'] and result['region_available'] and result['instance_offered'] else 2


if __name__=='__main__':sys.exit(main())
