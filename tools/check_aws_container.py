"""Isolated local ARM64 container acceptance. No AWS, public TLS or financial calls."""
import argparse
import http.client
import json
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.operator_auth import make_config


def docker(*args,**kwargs):
    return subprocess.run(['docker',*args],check=True,capture_output=True,text=True,**kwargs).stdout.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',required=True)
    args=parser.parse_args()
    if not re.fullmatch('[a-f0-9]{40}',args.revision):raise ValueError('EXACT_LOCAL_IMAGE_REVISION_REQUIRED')
    image='touchstone-aws-local:'+args.revision
    info=json.loads(docker('image','inspect',image))[0]
    if info['Architecture']!='arm64' or info['Config']['Labels'].get('org.opencontainers.image.revision')!=args.revision:
        raise ValueError('IMAGE_IDENTITY_MISMATCH')
    name='touchstone-qa-'+secrets.token_hex(6);volume=name+'-data';network=name+'-isolated'
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}';password=secrets.token_urlsafe(32)
    cookie='';csrf=''

    def request(path,body=None,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        values={'Host':f'127.0.0.1:{port}','Origin':origin,'Cookie':cookie,'X-Touchstone-CSRF':csrf}
        if body is not None:values['Content-Type']='application/json'
        values.update(headers or {})
        connection.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,values)
        response=connection.getresponse();payload=response.read();status=response.status;result_headers=dict(response.getheaders())
        connection.close()
        return status,payload,result_headers

    def ready():
        for _ in range(80):
            try:
                status,raw,_=request('/healthz')
                if status==200:
                    health=json.loads(raw)
                    assert health['revision']==args.revision and health['financial_dispatch_enabled'] is False
                    return
            except OSError:pass
            time.sleep(.25)
        raise RuntimeError('LOCAL_CONTAINER_HEALTH_TIMEOUT')

    try:
        docker('volume','create',volume);docker('network','create','--internal',network)
        # Initialize a disposable password hash, never a payer or cloud identity.
        docker('run','--rm','-i','--network','none','--mount',f'type=volume,source={volume},target=/var/lib/touchstone',image,
            'python','-c',"from pathlib import Path; import sys; p=Path('/var/lib/touchstone/operator-config.json'); p.write_text(sys.stdin.read()); p.chmod(0o600)",
            input=json.dumps(make_config(origin,'operator',password)))
        docker('run','--detach','--name',name,'--network',network,'--publish',f'127.0.0.1:{port}:8089',
            '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--pids-limit','96',
            '--tmpfs','/tmp:size=32m,mode=1777','--mount',f'type=volume,source={volume},target=/var/lib/touchstone',image)
        ready()
        assert docker('exec',name,'node','--version').startswith('v22.')
        for page in ('/','/dashboard','/ledger','/control-room'):assert request(page)[0]==200,page
        assert request('/operator-api/jobs')[0]==401
        assert request('/operator-api/login',{'username':'operator','password':'incorrect'})[0]==401
        status,raw,headers=request('/operator-api/login',{'username':'operator','password':password});assert status==200
        cookie=headers['Set-Cookie'].split(';')[0];csrf=json.loads(raw)['csrf']
        task={'kind':'arithmetic','source':{'amounts_cents':[1250,900],'discount_cents':150},
            'policy':'tools-only','budget_micro_usdz':0,'max_call_micro_usdz':0}
        assert request('/operator-api/jobs',task,{'X-Touchstone-CSRF':'wrong'})[0]==403
        status,raw,_=request('/operator-api/jobs',task,{'Idempotency-Key':'container-arithmetic'});assert status==201,raw
        job=json.loads(raw)
        status,raw,_=request('/operator-api/jobs/'+job['id']+'/start',{});assert status==200
        assert json.loads(raw)['output']=={'total_cents':2000}
        # Genuine persisted events, not a frontend timer.
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
        connection.request('GET','/operator-api/events',headers={'Host':f'127.0.0.1:{port}','Cookie':cookie,'Last-Event-ID':'1'})
        response=connection.getresponse();assert response.status==200
        lines=[response.readline().decode() for _ in range(4)];connection.close()
        assert any('JOB_CREATED' in line for line in lines)
        docker('restart','--time','35',name);ready()
        status,raw,_=request('/operator-api/jobs');assert status==200
        state=json.loads(raw);assert len(state['jobs'])==1 and state['jobs'][0]['output']=={'total_cents':2000} and state['audit']['valid']
        transactions=json.loads(request('/operator-api/transactions')[1])
        assert transactions['currencies']=={'USD':0,'USDZ':0,'prepaid_credit_USD':0,'native_fees':'NONE'}
        assert request('/operator-api/pay',{'approved':True})[0]==404
        for _ in range(3):assert request('/operator-api/login',{'username':'operator','password':'incorrect'})[0]==401
        assert request('/operator-api/login',{'username':'operator','password':password})[0]==429
        report={'status':'PASS','scope':'LOCAL_ARM64_CONTAINER_NO_EXTERNAL_NETWORK','source_revision':args.revision,
            'architecture':'arm64','node_runtime':True,'frontend_routes':True,'authentication_and_throttle':True,
            'arithmetic_output':2000,'sse':True,'container_restart_persistence':True,'audit_valid':True,
            'financial_dispatch_enabled':False,'aws_deployed':False,'public_tls_tested':False}
        path=ROOT/'tmp/aws-container-verification.json';path.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        # Only disposable local test objects with an unpredictable unique prefix.
        for command in [('rm','--force',name),('network','rm',network),('volume','rm',volume)]:
            subprocess.run(['docker',*command],capture_output=True,check=False)


if __name__=='__main__':main()
