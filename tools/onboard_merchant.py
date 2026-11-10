"""Execute only the approved configuration plan, or read its journal/status."""
import argparse
import json
from pathlib import Path
import sys
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from touchstone.holds import OperationJournal, OutcomeUnknown
from touchstone.merchant_onboarding import SCOPE, binding_terms, execute, fingerprint, read_config, verify_config
from touchstone.treasury import AirwallexSandbox, AirwallexHTTPError
from tools.run_project import environment
from tools.run_issuing_proof import save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['execute','status'])
    parser.add_argument('--approval')
    args = parser.parse_args()
    environment()
    client = AirwallexSandbox()
    directory = ROOT/'bench/results/completion-20261110'
    saved = json.loads((directory/'merchant-onboarding-plan.json').read_text(encoding='utf-8'))
    journal = OperationJournal(ROOT/'data/merchant-service/onboarding.sqlite')
    if args.action == 'execute':
        config = json.loads((ROOT/'data/merchant-service/config.json').read_text(encoding='utf-8'))
        try:
            report = execute(client,journal,saved,config,args.approval)
        except OutcomeUnknown:
            report = {'label':'MEASURED_ATTEMPT','phase':'UNKNOWN_STOPPED_NO_RETRY',
                'plan_sha256':saved['plan_sha256'],'errors':journal.errors(SCOPE),
                'financial_transactions':0,'model_calls':0,'new_cards':0,'visa_approved':False}
            save(directory/'merchant-onboarding.json',report)
            print(json.dumps(report,indent=2));return 1
        save(directory/'merchant-onboarding.json',report)
    else:
        bound=journal.get(SCOPE,'binding')
        config=json.loads((ROOT/'data/merchant-service/config.json').read_text(encoding='utf-8'))
        if bound and bound['digest'] != fingerprint(binding_terms(client,saved['plan'],config)):
            raise ValueError('Current account or configuration differs from the original journal')
        raw = read_config(client)
        report = {'label':'MEASURED_READ_ONLY','configuration':verify_config(raw,saved['plan'],client) if raw else None,
                  'journal_states':{action:(journal.get(SCOPE,action) or {}).get('state') for action in ('onboard','catalog')},
                  'errors':journal.errors(SCOPE),'business_writes':0,'financial_transactions':0,'model_calls':0}
        save(directory/'merchant-status.json',report)
    print(json.dumps(report,indent=2));return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except AirwallexHTTPError as error:
        print(json.dumps({'status':'STOPPED','http_status':error.status,'code':error.code,'automatic_retry':False}))
        raise SystemExit(1) from None
    except (ValueError, RuntimeError, OSError) as error:
        print(json.dumps({'status':'STOPPED','failure_type':type(error).__name__,
            'reason':'Preflight or binding check failed; no automatic retry or changed scope',
            'financial_transactions':0,'model_calls':0}))
        raise SystemExit(1) from None
