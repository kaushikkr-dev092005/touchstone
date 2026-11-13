"""Independent ephemeral humans for existing controlled financial regression rails.

Only installed by test setUp; never imported by runtime. Does NOT replace or mock
verification: actual viem signatures pass the production ledger boundary.
"""
import json
import os
from pathlib import Path
import secrets
import threading
from unittest.mock import patch

from test_procurement_approval import EphemeralSigner
from touchstone.ledger import Ledger


def signed_fixtures(case, directory):
    directory=Path(directory).resolve()
    signer=EphemeralSigner();case.addCleanup(signer.close)
    path=directory/'test-approvers.json'
    cfg={'environment':'LOCAL_TEST_REGRESSION','chain_id':63825,'salt':'0x'+secrets.token_hex(32),
         'signers':[signer.addresses[0]],'agent_addresses':[signer.addresses[1]],'ledger_paths':[],'api_credit_max':0}
    path.write_text(json.dumps(cfg))
    env=patch.dict(os.environ,{'TOUCHSTONE_APPROVAL_CONFIG':str(path),'TOUCHSTONE_IGNORE_LOCAL_CONFIG':'1'})
    env.start();case.addCleanup(env.stop)
    reserve, authorize = Ledger.reserve, Ledger.assert_can_pay
    lock=threading.Lock()
    def register(ledger):
        actual=Path(ledger.path).resolve()
        if not actual.is_relative_to(directory): raise AssertionError('Test signer may only trust this temporary test directory')
        with lock:
            if str(actual) in cfg['ledger_paths'] and json.loads(path.read_text())['salt']==cfg['salt']:
                return
            if str(actual) not in cfg['ledger_paths']: cfg['ledger_paths'].append(str(actual))
            staged=path.with_suffix('.new');staged.write_text(json.dumps(cfg));staged.replace(path)
    def reserved(ledger,*args,**kwargs):
        key=reserve(ledger,*args,**kwargs);register(ledger);return key
    def authorized(ledger,key,*args,**kwargs):
        if ledger.approval_required(key):
            register(ledger)
            challenge=ledger.prepare_approval(key)
            if challenge['state']=='PENDING_APPROVAL':ledger.approvals.submit(challenge['id'],signer.sign(challenge))
        return authorize(ledger,key,*args,**kwargs)
    for name,func in [('reserve',reserved),('assert_can_pay',authorized)]:
        p=patch.object(Ledger,name,func);p.start();case.addCleanup(p.stop)
