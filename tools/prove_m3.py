"""Controlled M3 accounting evidence. No network, credentials or real wallets."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_m3 import PremiumFactory
from touchstone.invoice_profile import paid
from touchstone.metal import PaymentPending


def main():
    health={'inference_ready':True,'chain':63825,'provider_id':'hosted-premium',
            'upstream_funding':'PARTNER_CREDITS_OPERATOR_DECLARED','provider_model':'MOCK-premium'}
    with tempfile.TemporaryDirectory() as directory, patch('socket.create_connection',side_effect=AssertionError('No network')):
        root=Path(directory);factory=PremiumFactory(root/'remote')
        result=paid('primary','http://127.0.0.1:8093',100000,10000,2,root/'profile.json',
            execute=True,reference_scope='reference',reference_budget=50000,
            client_factory=factory,health=health,directory=root/'state')
        assert result['confirmed_provider_spend_including_failed_calls_micro_usd']==20000
        assert result['verification_cost_micro_usd']==2000
        class LostResponse(PremiumFactory):
            def __call__(self,*args):
                client=super().__call__(*args);original=client.pay
                def lose(*params):
                    original(*params)
                    raise PaymentPending('Controlled lost response')
                client.pay=lose
                return client
        losing=LostResponse(root/'lost-remote')
        kwargs=dict(execute=True,client_factory=losing,health=health,directory=root/'lost-state')
        unknown=paid('unknown','http://127.0.0.1:8093',50000,10000,1,root/'unknown.json',**kwargs)
        refused=False
        try:paid('unknown','http://127.0.0.1:8093',50000,10000,1,root/'unknown.json',**kwargs)
        except PaymentPending:refused=True
        assert refused and sum(e[0]=='pay' for e in losing.events)==1
        evidence={'label':'MOCK','live_payments_sent':0,'real_wallets_accessed':False,
            'reference_accounting':result,
            'uncertain_purchase':{'label':'MOCK','remote_payments':1,
                'retained_pending_attempts':unknown['pending_attempts'],'automatic_retry_refused':refused,
                'audit':unknown['audit']}}
    target=ROOT/'bench/results/m3/controlled-proof.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'label':'MOCK','live_payments_sent':0,'audit':result['audit'],'output':str(target)}))


if __name__=='__main__':main()
