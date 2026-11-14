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
READ_CHECKS_COMPLETE = 'BLOCKED_CREDIT_ELIGIBILITY_AND_FINAL_APPROVAL_REQUIRED'
READ_ONLY = {('sts','get-caller-identity'), ('ec2','describe-regions'),
             ('ec2','describe-instance-type-offerings'), ('freetier','get-account-plan-state')}


def find_aws_cli():
    binary=shutil.which('aws')
    if binary:return binary
    if sys.platform=='win32':
        # Official per-user installs may not be visible to an already-open shell.
        for variable,subdirectory in [('LOCALAPPDATA','Programs/Amazon/AWSCLIV2'),
                ('ProgramFiles','Amazon/AWSCLIV2'),('ProgramFiles(x86)','Amazon/AWSCLIV2')]:
            base=os.environ.get(variable)
            if base:
                candidate=Path(base)/subdirectory/'aws.exe'
                if candidate.is_file():return str(candidate)
    return None


def profile_metadata(directory=None):
    directory = Path(directory) if directory else Path.home()/'.aws'
    paths = [Path(os.environ.get('AWS_CONFIG_FILE', directory/'config')),
             Path(os.environ.get('AWS_SHARED_CREDENTIALS_FILE', directory/'credentials'))]
    for path in paths:
        parser = configparser.RawConfigParser()
        try:
            parser.read(path, encoding='utf-8')
        except (OSError, configparser.Error):
            continue
        if not parser.has_section('default'):continue
        for name in ('login_session','sso_session','sso_start_url','role_arn','credential_process','aws_access_key_id'):
            value=parser.get('default',name,fallback='')
            if value:
                return {'configured':True,'credential_source':name.upper(),
                        'known_root_identity':name=='login_session' and value.endswith(':root')}
    return {'configured':False,'credential_source':'NOT_CONFIGURED','known_root_identity':False}


def default_configured(directory=None):
    return profile_metadata(directory)['configured']


def read_aws(service, operation, extra=(), runner=subprocess.run):
    if (service,operation) not in READ_ONLY:
        raise ValueError('AWS_OPERATION_NOT_READ_ONLY')
    binary = find_aws_cli()
    if not binary:raise RuntimeError('AWS_CLI_NOT_INSTALLED')
    # Never inherit another AWS account's environment credentials or endpoint overrides.
    env={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','AIRWALLEX_','METAL_','ANTHROPIC_')) and k!='AGENT_PRIVATE_KEY'}
    for name in ('AWS_CONFIG_FILE','AWS_SHARED_CREDENTIALS_FILE'):
        if name in os.environ:env[name]=os.environ[name]
    env.update(AWS_EC2_METADATA_DISABLED='true',AWS_PAGER='',AWS_MAX_ATTEMPTS='1',AWS_CLI_AUTO_PROMPT='off')
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
    metadata=profile_metadata() if configured is None else {'configured':configured,'credential_source':'CONTROLLED_TEST','known_root_identity':False}
    result={'status':'AWS_PROFILE_NOT_CONFIGURED','profile':'default','region':REGION,
            'credential_source':metadata['credential_source'],'session_valid':False,
            'aws_cli_available':bool(find_aws_cli()),
            'read_only_checks_passed':False,
            'identity_verified':False,'region_available':False,'instance_offered':False,'instance_type':instance_type,
            'promotional_credit_service_eligibility':'NOT_VERIFIED',
            'provisioning_authorized':False,'aws_resources_created':0,'financial_operations':0}
    if not metadata['configured']:return result
    if metadata['known_root_identity']:
        result['status']='AWS_ROOT_CREDENTIALS_FORBIDDEN';return result
    try:
        identity=reader('sts','get-caller-identity')
        arn=identity.get('Arn','')
        if isinstance(arn,str) and arn.endswith(':root'):
            result['status']='AWS_ROOT_CREDENTIALS_FORBIDDEN';return result
        result['session_valid']=True
        if identity.get('Account')!=expected_account:
            result['status']='AWS_ACCOUNT_MISMATCH';return result
        if (not isinstance(arn,str) or not re.fullmatch(r'arn:aws:(iam|sts)::'+expected_account+r':(user|assumed-role|federated-user)/[^\s]+',arn)):
            result['status']='AWS_IDENTITY_UNVERIFIED';return result
        result['identity_type']=arn.split(':',5)[5].split('/',1)[0].upper()
        result['identity_verified']=True
        regions=reader('ec2','describe-regions',('--region-names',REGION))
        result['region_available']=any(r.get('RegionName')==REGION and r.get('OptInStatus') in
            {'opt-in-not-required','opted-in'} for r in regions.get('Regions',[]))
        if not result['region_available']:
            result['status']='AWS_REGION_NOT_AVAILABLE';return result
        offers=reader('ec2','describe-instance-type-offerings',('--location-type','region','--filters','Name=instance-type,Values='+instance_type))
        result['instance_offered']=any(o.get('InstanceType')==instance_type and o.get('Location')==REGION
                                      for o in offers.get('InstanceTypeOfferings',[]))
        if not result['instance_offered']:
            result['status']='INSTANCE_TYPE_NOT_OFFERED';return result
        plan=reader('freetier','get-account-plan-state')
        if plan.get('accountId')!=expected_account:
            result['status']='AWS_ACCOUNT_MISMATCH';return result
        result['account_plan']={k:plan.get(k) for k in ('accountPlanType','accountPlanStatus','accountPlanRemainingCredits','accountPlanExpirationDate')}
        if plan.get('accountPlanType') not in {'FREE','PAID'}:
            result['status']='AWS_ACCOUNT_PLAN_UNVERIFIED';return result
        if plan.get('accountPlanStatus')!='ACTIVE':
            result['status']='AWS_ACCOUNT_PLAN_NOT_ACTIVE';return result
        if instance_type=='t4g.nano' and plan.get('accountPlanType')=='FREE':
            result['status']='FREE_PLAN_INSTANCE_NOT_ELIGIBLE';return result
        result['read_only_checks_passed']=True
        result['status']=READ_CHECKS_COMPLETE
    except (RuntimeError,OSError,ValueError,subprocess.TimeoutExpired) as error:
        result['status']=str(error) if type(error) is RuntimeError else 'AWS_READ_CHECK_FAILED'
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-account',required=True)
    parser.add_argument('--instance-type',choices=['t4g.micro','t4g.nano'],default='t4g.micro')
    parser.add_argument('--output',default='tmp/aws-preflight.json')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parent.parent
    output=(root/args.output).resolve()
    if not output.is_relative_to(root/'tmp'):raise ValueError('Reports must stay in ignored tmp/')
    result=inspect(args.expected_account,instance_type=args.instance_type)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    # A later billing/account/eligibility failure must not inherit earlier success.
    # Even exit 0 means read checks completed only, never approval to provision.
    return 0 if result['read_only_checks_passed'] and result['status']==READ_CHECKS_COMPLETE else 2


if __name__=='__main__':sys.exit(main())
