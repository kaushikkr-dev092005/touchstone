"""Reproduce the three-job short-float story under both simulated billing policies."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from touchstone.ledger import Ledger
from touchstone.engine import Engine
from touchstone.payments import MockRail


def main():
    reports=[]
    for policy in ('CUSTOMER_PAYS','MERCHANT_ABSORBS'):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ledger=Ledger(root/'ledger.sqlite');engine=Engine(ledger,MockRail(root/'rail.sqlite'))
            run=engine.create_demo(failed_call_policy=policy)
            engine.run(run)
            for job in ledger.jobs(run):ledger.settle_job(job['id'])
            snapshot=engine.snapshot(run)
            if not snapshot['audit']['valid'] or not snapshot['reconciliation']['matched']:raise ValueError('M5 reconciliation failed')
            reports.append({'label':'SIMULATED','policy':policy,'hold_total_micro_usd':2500000,
                'initial_float_micro_usd':1500000,'financials':snapshot['financials']['by_run'][0],
                'reconciliation':snapshot['reconciliation'],'audit':snapshot['audit'],
                'invariants':{'budget_and_float_limits':'ENFORCED_BY_LEDGER','all_jobs_closed':all(j['status']=='COMPLETED' for j in snapshot['jobs'])}})
    report={'label':'SIMULATED','implementation_execution':'MEASURED','runs':reports,'external_transactions':0,
            'credit_acknowledgements_netted_against_cash':False,'fiat_token_bridge':False}
    path=Path('bench/results/m5/financial-story.json');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'label':'SIMULATED','audit_heads':[r['audit']['head'] for r in reports],
                      'customer_captured_micro_usd':[r['financials']['customer_captured_micro_usd'] for r in reports],
                      'external_transactions':0},indent=2))


if __name__=='__main__':main()
