"""Backfill allowlisted metadata from original cached deliveries. Never pay or infer."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from tools.continue_policy_live import PLAN,DIRECTORY,LiveContinuation,publish_report
from tools.run_project import environment
from touchstone.leases import exclusive
from touchstone.ledger import Ledger
from touchstone.metal import MetalQuote
from touchstone.payments import MetalEngineRail


def main():
    environment();plan=json.loads(PLAN.read_text());terms=plan['terms']
    runner=LiveContinuation(terms['effective_comparison_plan'],DIRECTORY,terms)
    with exclusive(DIRECTORY/'owner.sqlite'),exclusive(runner.wallet_owner):
        ledger=Ledger(DIRECTORY/'ledger.sqlite');state=json.loads((DIRECTORY/'journal.json').read_text())
        if not state['complete'] or len(state['rows'])!=64 or not ledger.audit()['valid']:
            raise ValueError('Only a completed, auditable live run may be projected')
        rail=MetalEngineRail(runner.plan['scope'],list(runner.plan['origins'].values()),client=runner.client(execute=False),
            expected_provider_ids=['local-gpu','hosted-premium'])
        restored=[]
        for attempt in ledger.attempts():
            if attempt['provider']!='local-gpu' or not attempt['receipt'] or attempt['provider_metadata']:
                continue
            original=rail.lookup(attempt['key'],MetalQuote(**json.loads(attempt['quote'])))
            metadata=original.get('provider_metadata') or {}
            if (original.get('state')!='PAID' or original['id']!=attempt['receipt']
                    or original['output']!=json.loads(attempt['output']) or metadata.get('provider_type')!='LOCAL_MODEL'):
                raise ValueError('Original paid receipt or output differs')
            keep={k:metadata[k] for k in ('provider_type','provider_model','latency_ms','chaos_mode') if k in metadata}
            if type(metadata.get('completion_tokens')) is int:keep['usage']={'output_tokens':metadata['completion_tokens']}
            ledger.record_paid(attempt['key'],{**original,'provider_metadata':keep})
            restored.append({'reservation_key':attempt['key'],'receipt_id':attempt['receipt'],
                'chaos_mode':keep.get('chaos_mode'),'output_changed':False,'cost_changed':False})
        report=runner.write_report(state,ledger,rail)
        publish_report(plan,report)
        proof={'label':'MEASURED_CACHED_DELIVERY_METADATA_RECONCILIATION','restored':restored,'audit':ledger.audit(),
            'reason':'Local source-selection/throughput fields exceeded the ledger metadata allowlist; retained core measurements restored from exact original cache',
            'financial_transactions':0,'inference_calls':0,'source_answers_changed':False,'charges_changed':False}
        (ROOT/'bench/results/m4-live-20261112/metadata-reconciliation.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'restored_local_receipts':len(restored),'quality_drop_receipts':sum(r['chaos_mode']=='quality-drop' for r in restored),
            'financial_transactions':0,'inference_calls':0,'audit':ledger.audit()}))


if __name__=='__main__':main()
