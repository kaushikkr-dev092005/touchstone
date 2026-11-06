"""Sandbox issuing doctor or explicitly authorized capped card create; no card details."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from touchstone.card_rail import CardRail
from touchstone.holds import OperationJournal,micro_usd
from touchstone.treasury import AirwallexSandbox


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['doctor','issue','reconcile'])
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--scope');parser.add_argument('--cardholder-id');parser.add_argument('--created-by')
    parser.add_argument('--cap');parser.add_argument('--currency',choices=['USD','EUR','SGD'],default='USD')
    parser.add_argument('--expires-at');parser.add_argument('--output')
    args=parser.parse_args()
    if args.action=='issue' and (not args.execute or not all([args.scope,args.cardholder_id,args.created_by,args.cap,args.expires_at])):
        parser.error('Issuing requires --execute, immutable terms and separate written cap approval')
    if args.action=='reconcile' and not all([args.scope,args.cardholder_id,args.created_by,args.cap,args.expires_at]):
        parser.error('Read-only reconciliation requires the original immutable terms')
    try:
        from tools.run_project import environment
        environment()
        rail=CardRail(AirwallexSandbox(),OperationJournal('data/issuing.sqlite'))
        if args.action=='doctor':result=rail.doctor()
        elif args.action=='reconcile':result=rail.reconcile(args.scope,args.cardholder_id,args.created_by,micro_usd(args.cap),args.currency,args.expires_at)
        else:result=rail.issue(args.scope,args.cardholder_id,args.created_by,micro_usd(args.cap),args.currency,args.expires_at,execute=args.execute)
    except Exception as error:
        result={'label':'BLOCKED','error_type':type(error).__name__,'reason':'Issuing setup or read-back failed; preserve any unknown operation',
                'operation':args.action,'cards_created_unverified':args.action=='issue'}
    if args.output:
        path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2));return 0 if result['label']!='BLOCKED' else 2


if __name__=='__main__':raise SystemExit(main())
