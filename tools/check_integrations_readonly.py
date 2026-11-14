"""Explicit private-operator read check. GETs and authentication only; no payer key."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def load_read_credentials():
    allowed={'AIRWALLEX_CLIENT_ID','AIRWALLEX_API_KEY','AIRWALLEX_ACCOUNT_ID','METAL_RPC_URL'}
    for name in list(os.environ):
        if (name.startswith(('AIRWALLEX_','ANTHROPIC_','METAL_')) or name=='AGENT_PRIVATE_KEY') and name not in allowed:
            os.environ.pop(name)
    if os.name=='nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as key:
            for name in allowed:
                try:value=winreg.QueryValueEx(key,name)[0]
                except FileNotFoundError:continue
                if isinstance(value,str) and value:os.environ.setdefault(name,value)
    path=ROOT/'data/local-config.json'
    if path.is_file():
        values=json.loads(path.read_text(encoding='utf-8'))
        for name in allowed:
            if isinstance(values.get(name),str) and values[name]:os.environ.setdefault(name,values[name])
    os.environ['TOUCHSTONE_IGNORE_LOCAL_CONFIG']='1'


def inspect():
    from touchstone.treasury import AirwallexSandbox,AirwallexHTTPError
    from touchstone.card_rail import CardRail
    from touchstone.holds import OperationJournal
    from touchstone.rpc import inspect_rpc
    class ReadOnlyAirwallex(AirwallexSandbox):
        def _request(self,path,method='GET',headers=None,body=None):
            if method!='GET' and (method,path)!=('POST','/api/v1/authentication/login'):
                raise ValueError('WRITE_FORBIDDEN')
            return super()._request(path,method,headers,body)
    result={'observed_at':datetime.now(timezone.utc).isoformat(), 'scope':'READ_ONLY_INTEGRATION_CHECK',
        'financial_operations':0, 'model_calls':0, 'payer_key_loaded':False,
        'visa':{'status':'BLOCKED_EXTERNAL_APPROVAL','approval_verified':False}}
    try:
        client=ReadOnlyAirwallex()
        result['airwallex']=client.smoke()
        with tempfile.TemporaryDirectory(prefix='issuing-read-') as folder:
            raw=CardRail(client,OperationJournal(Path(folder)/'journal.sqlite')).doctor(diagnose=True)
        result['issuing']={k:raw[k] for k in ('issuing_read','issuing_write_verified','cards_sample','read_probes') if k in raw}
        try:
            merchant=client.request('GET','/api/v1/pa/agentic_commerce/config')
            result['merchant']={'configuration_read':isinstance(merchant,dict) and bool(merchant),
                                'new_payment_verified':False}
        except AirwallexHTTPError as error:
            result['merchant']={'configuration_read':False,'http_status':error.status,'code':error.code}
        saved=json.loads((ROOT/'bench/results/m1/current-hosted-card-proof.json').read_text(encoding='utf-8'))
        matches=saved.get('account_fingerprint')==hashlib.sha256(os.environ.get('AIRWALLEX_ACCOUNT_ID','').encode()).hexdigest()
        if matches and saved.get('result',{}).get('complete'):
            identity=saved['result']['intent']['id']
            import re
            if not re.fullmatch(r'int_[A-Za-z0-9_-]+',identity):raise ValueError('INVALID_SAVED_ID')
            raw=client.request('GET','/api/v1/pa/payment_intents/'+identity)
            result['historical_capture']={'account_matches':True,
                **{k:raw.get(k) for k in ('status','amount','currency','captured_amount')},'current_active_hold':False}
    except AirwallexHTTPError as error:
        result['airwallex_error']={'http_status':error.status,'code':error.code}
    except (ValueError,KeyError,RuntimeError,OSError):
        result['airwallex_error']={'status':'BLOCKED_READINESS_UNAVAILABLE'}
    try:result['metal_rpc']=inspect_rpc()
    except (RuntimeError,ValueError):result['metal_rpc']={'connected':False,'status':'BLOCKED_RPC_UNAVAILABLE'}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/operator/readonly-integrations.json')
    args=parser.parse_args()
    destination=Path(args.output).resolve()
    if not (destination.is_relative_to((ROOT/'data').resolve()) or destination.is_relative_to((ROOT/'tmp').resolve())):
        raise ValueError('Write fresh observations only under ignored data/ or tmp/; never replace historical evidence')
    load_read_credentials()
    result=inspect()
    destination.parent.mkdir(parents=True,exist_ok=True)
    pending=destination.with_suffix('.pending')
    pending.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');pending.replace(destination)
    destination.chmod(0o600)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
