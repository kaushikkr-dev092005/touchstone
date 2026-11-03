"""M3 corpus, offline scoring, and explicitly selected model profiles."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['build','report','profile-local','profile-paid'])
    parser.add_argument('--directory',default='bench/results/m3')
    parser.add_argument('--tier',choices=['economy','balanced'],default='economy')
    parser.add_argument('--partition',choices=['calibration','holdout'],default='calibration')
    parser.add_argument('--max-calls',type=int,default=120)
    parser.add_argument('--output')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--wallet-scope')
    parser.add_argument('--reference-scope')
    parser.add_argument('--budget-usdz')
    parser.add_argument('--reference-budget-usdz',default='0')
    parser.add_argument('--price-cap-usdz')
    parser.add_argument('--provider-origin',default='http://127.0.0.1:8093')
    args=parser.parse_args()
    try:
        if not 1<=args.max_calls<=180:raise ValueError('Use 1-180 calls')
        if args.action=='profile-paid' and not args.execute:
            raise ValueError('Paid profiling requires --execute and specific written approval for calls and aggregate USDZ cap')
        from touchstone.invoice_study import report
        from touchstone.invoice_profile import local,paid
        if args.action in {'build','report'}:
            result=report(args.directory)
            print(json.dumps({'label':result['label'],'sources':result['dataset']['sources'],
                'baseline':result['baseline'],'qualification_status':result['qualification_status'],
                'models_measured':result['models_measured']},indent=2))
        elif args.action=='profile-local':
            output=args.output or str(Path(args.directory)/'profiles'/f'{args.tier}.json')
            result=local(args.tier,args.partition,args.max_calls,output)
            print(json.dumps({'label':'MEASURED','tier':args.tier,'calls':len(result['rows']),'output':output}))
        else:
            from touchstone.holds import micro_usd
            result=paid(args.wallet_scope,args.provider_origin,micro_usd(args.budget_usdz),
                micro_usd(args.price_cap_usdz),args.max_calls,args.output or str(Path(args.directory)/'profiles/hosted-premium.json'),
                execute=True,reference_scope=args.reference_scope,reference_budget=micro_usd(args.reference_budget_usdz),partition=args.partition)
            print(json.dumps({'label':result['label'],'calls':len(result['rows']),'stop_reason':result['stop_reason']}))
        return 0
    except Exception as error:
        # Never echo SDK, URL, credential or raw provider errors.
        print(json.dumps({'label':'BLOCKED','action':args.action,'failure_type':type(error).__name__}),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
