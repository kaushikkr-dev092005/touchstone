"""Live-only entrypoint with unsigned fresh-context waiting; no demo or simulated rail."""
import argparse
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from tools.continue_policy_live import PLAN,run


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--approval')
    args=parser.parse_args()
    module='--import='+(ROOT/'integrations/metal/fresh-context.mjs').as_uri()
    os.environ['NODE_OPTIONS']=(os.environ.get('NODE_OPTIONS','')+' '+module).strip()
    report=run(json.loads(PLAN.read_text()),args.execute,args.approval)
    print(json.dumps({'complete':report['complete'],'outcomes':len(report['rows']),
        'pending_attempts':report['pending_attempts'],'actual_paid_receipts':sum(bool(c.get('receipt_id')) for c in report['calls'].values()),
        'mode':report['mode'],'financial_scope':'ORIGINAL_APPROVED_CONTINUATION_ONLY'}))
