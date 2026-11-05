"""One explicitly approved testnet funding proof; fixed scope and caps, no purchases.

Requires the separately recorded written approval and --execute.
"""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.config import load_local
from touchstone.metal import MetalRail,task_resource_url
from touchstone.metal_batch import MetalBatch
from touchstone.rpc import inspect_rpc
from touchstone.workload import generate
from touchstone.leases import exclusive

parser=argparse.ArgumentParser()
parser.add_argument('--execute',action='store_true',required=True)
args=parser.parse_args()


def require(condition):
    if not condition:
        raise ValueError('Approved testnet funding precondition failed; no retry authorized')


scope='m2-live-single-20261105'
report={'label':'BLOCKED','scope':scope,'deposit_cap_usdz':'0.02',
    'native_fee_cap_wei':'1000000000000000','deposits_requested':0,'purchases_sent':0,'automatic_retries':0}
try:
    load_local()
    require(inspect_rpc()['chain_id']==63825)
    with urllib.request.urlopen('http://127.0.0.1:8092/health',timeout=5) as response:
        health=json.load(response)
    require(health['inference_ready'] is True and health['chain']==63825 and health['provider_id']=='local-gpu')
    batch=MetalBatch('data/metal-batch',funding_lock=Path('data/metal/funding-owner.sqlite'))
    _,terms,wallets=batch._read(scope)
    require(terms['jobs']==1 and terms['steps']==1 and terms['budget']==20000 and terms['cap']==10000)
    wallet=wallets[0]
    client=MetalRail(wallet['wallet'],terms['origin'],10000,20000,execute=True)
    funding=client.invoke('funding-status')
    require(funding['chain_id']==63825 and funding['address'].lower()=='0x9d57e5465346f8f2cff4fdc1a741c138fb9c68b4')
    require(int(funding['usdz_balance_base_units'])>=20000000000000000)
    require(int(funding['native_balance_base_units'])>=1000000000000000)
    task=generate(42,1)[0][0]
    quoted=client.quote(task_resource_url(terms['origin'],task))
    require(quoted.provider=='local-gpu' and quoted.price<=10000)
    with exclusive(batch.directory/(scope+'.owner.sqlite')):
        balance=client.balance()
        require(not balance.get('pending_invoice') and not balance.get('historical_payments'))
        if int(balance['spendable_base_units'])<20000000000000000:
            require(wallet['phase']=='UNFUNDED')
            batch._state(wallet,'DEPOSIT_DISPATCHING',balance['account'])
            report['deposits_requested']=1
            report['deposit']=client.invoke('deposit',dollars='0.02',native_gas_cap_wei=report['native_fee_cap_wei'])
    funded=batch.fund(scope,execute=True)
    report.update(label='MEASURED',funded=funded['funded'],wallets=funded['wallets'],audit=funded['audit'])
except Exception as error:
    report.update(failure_type=type(error).__name__,outcome='UNKNOWN_IF_DISPATCHED' if report['deposits_requested'] else 'NOT_DISPATCHED')
Path('bench/results/m2/live-capped-funding.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
