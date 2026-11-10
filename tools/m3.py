"""M3 corpus, offline scoring, and explicitly selected model profiles."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['build','report','freeze-holdout','rescore-saved','profile-local','profile-paid'])
    parser.add_argument('--directory',default='bench/results/m3')
    parser.add_argument('--tier',choices=['economy','balanced'],default='economy')
    parser.add_argument('--partition',choices=['calibration','holdout'],default='calibration')
    parser.add_argument('--max-calls',type=int,default=120)
    parser.add_argument('--output')
    parser.add_argument('--input',help='Existing profile for explicit historical rescoring; never creates new model evidence')
    parser.add_argument('--corpus',help='Frozen corpus directory; profilers read only public sources, not offline truth')
    parser.add_argument('--seed',type=int,default=202611101)
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
        if args.action=='rescore-saved':
            import hashlib
            from touchstone.invoice_dataset import build
            from touchstone.invoice_study import score,metrics,code_hashes
            from touchstone.invoice_extraction import VERSION
            if not args.input:raise ValueError('--input is required for historical rescoring')
            payload=Path(args.input).read_bytes();raw=json.loads(payload)
            if args.corpus:
                from touchstone.invoice_corpus import load
                _,records,truth=load(args.corpus,include_truth=True)
            else:records,truth=build()
            rows=score(records,truth,raw['rows'])
            result={'label':'MEASURED','scope':'HISTORICAL_OUTPUT_RESCORING_NOT_NEW_MODEL_CALLS',
                'model_id':raw['model_id'],'input_sha256':hashlib.sha256(payload).hexdigest(),
                'verifier_version':VERSION,'code_sha256':code_hashes(),
                'profile_provenance_current':raw.get('code_sha256')==code_hashes(),
                'calibration':metrics([r for r in rows if r['partition']=='calibration']),
                'holdout':metrics([r for r in rows if r['partition']=='holdout']),
                'new_model_calls':0,'payments_sent':0,'qualifies_model':False}
            if args.output:
                target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(result,indent=2))
        elif args.action=='freeze-holdout':
            from touchstone.invoice_corpus import freeze
            result=freeze(args.corpus or str(Path(args.directory)/'dataset-v2'),args.seed)
            print(json.dumps(result,indent=2))
        elif args.action in {'build','report'}:
            result=report(args.directory,corpus=args.corpus)
            print(json.dumps({'label':result['label'],'sources':result['dataset']['sources'],
                'baseline':result['baseline'],'qualification_status':result['qualification_status'],
                'models_measured':result['models_measured']},indent=2))
        elif args.action=='profile-local':
            output=args.output or str(Path(args.directory)/'profiles'/f'{args.tier}.json')
            result=local(args.tier,args.partition,args.max_calls,output,corpus=args.corpus)
            print(json.dumps({'label':'MEASURED','tier':args.tier,'calls':len(result['rows']),'output':output}))
        else:
            from touchstone.holds import micro_usd
            result=paid(args.wallet_scope,args.provider_origin,micro_usd(args.budget_usdz),
                micro_usd(args.price_cap_usdz),args.max_calls,args.output or str(Path(args.directory)/'profiles/hosted-premium.json'),
                execute=True,reference_scope=args.reference_scope,reference_budget=micro_usd(args.reference_budget_usdz),partition=args.partition,corpus=args.corpus)
            print(json.dumps({'label':result['label'],'calls':len(result['rows']),'stop_reason':result['stop_reason']}))
        return 0
    except Exception as error:
        # Never echo SDK, URL, credential or raw provider errors.
        print(json.dumps({'label':'BLOCKED','action':args.action,'failure_type':type(error).__name__}),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
