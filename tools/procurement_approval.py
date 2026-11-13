"""Local operator registry/challenge management. Never signs or dispatches money."""
import argparse
import json
from pathlib import Path
import secrets
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.ledger import Ledger
from touchstone.procurement_approval import config_path, read_config, strict_json, ApprovalError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    setup=sub.add_parser('configure')
    setup.add_argument('--signer',action='append',required=True,help='Independent human EOA address; never a key')
    setup.add_argument('--agent-address',action='append',required=True)
    setup.add_argument('--ledger',action='append',required=True)
    setup.add_argument('--environment',default='LOCAL_TEST')
    setup.add_argument('--chain-id',type=int,default=31337)
    setup.add_argument('--api-credit-max-micros',type=int,default=0)
    for name in ('prepare','list','submit','revoke'):
        cmd=sub.add_parser(name);cmd.add_argument('--ledger',required=True)
        if name=='prepare':cmd.add_argument('--purchase-key',required=True)
        if name in ('submit','revoke'):cmd.add_argument('--id',required=True)
    args=parser.parse_args()
    if args.command=='configure':
        path=config_path()
        if path.exists():raise ApprovalError('REGISTRY_ALREADY_EXISTS')
        cfg={'environment':args.environment,'chain_id':args.chain_id,'salt':'0x'+secrets.token_hex(32),
             'signers':args.signer,'agent_addresses':args.agent_address,
             'ledger_paths':[str(Path(p).resolve()) for p in args.ledger],'api_credit_max':args.api_credit_max_micros}
        path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with path.open('x',encoding='utf-8') as out:json.dump(cfg,out,indent=2)
        path.chmod(0o600)
        try:read_config()
        except Exception:
            path.unlink();raise
        result={'status':'CONFIGURED','registry':str(path),'domain_salt':cfg['salt'],'financial_operations':0}
    else:
        ledger=Ledger(args.ledger)
        if args.command=='prepare':result=ledger.prepare_approval(args.purchase_key)
        elif args.command=='list':result=ledger.approvals.list()
        elif args.command=='revoke':result=ledger.approvals.revoke(args.id)
        else:
            # Public signature only on stdin; no signing key is ever requested.
            payload=strict_json(sys.stdin.read(4097))
            if set(payload)!={'signature'}:raise ApprovalError('MALFORMED_APPROVAL')
            result=ledger.approvals.submit(args.id,payload['signature'])
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,ApprovalError) as error:
        print(json.dumps({'code':getattr(error,'code','INVALID_REQUEST')}));raise SystemExit(1)
