"""Read-only attestation of the bound injected outage; no signed payment or model call."""
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from touchstone.comparison import task_id,read_health
from touchstone.metal import task_resource_url
from touchstone.workload import Task


def main():
    folder=ROOT/'bench/results/m4-live-20261112'
    approved=json.loads((folder/'continuation-plan.json').read_text())
    p=approved['terms']['effective_comparison_plan']
    row=next(r for r in p['tasks'] if r['index']==p['outage_index'])
    task=Task(task_id(row,'always-cheapest'),'invoice_extraction',row['task']['source'])
    origin=p['origins']['local-gpu'];health=read_health(origin)
    status=None;headers={}
    try:
        with urllib.request.urlopen(task_resource_url(origin,task),timeout=10) as response:
            status=response.status;headers=dict(response.headers)
    except urllib.error.HTTPError as error:
        status=error.code;headers=error.headers
    proof={'label':'MEASURED_POSTRUN_READ_ONLY_INJECTED_OUTAGE_ATTESTATION','observed_at':time.time(),
        'approval_plan_sha256':approved['plan_sha256'],'schedule_sha256':p['schedule_sha256'],'task_id':task.id,
        'http_status':status,'fault':headers.get('X-Touchstone-Fault'),
        'response_schedule_sha256':headers.get('X-Touchstone-Scenario-SHA256'),
        'provider_id':health.get('provider_id'),'health_schedule_sha256':health.get('chaos_schedule_sha256'),
        'verification_passed':status==503 and headers.get('X-Touchstone-Fault')=='outage'
            and headers.get('X-Touchstone-Scenario-SHA256')==p['schedule_sha256']
            and health.get('provider_id')=='local-gpu' and health.get('chaos_schedule_sha256')==p['schedule_sha256'],
        'during_original_paid_trial':False,'financial_transactions':0,'inference_calls':0}
    (folder/'outage-attestation.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof))


if __name__=='__main__':main()
