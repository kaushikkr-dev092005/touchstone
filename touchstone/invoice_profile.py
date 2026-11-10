"""Explicit invoice profiling. Local servers must already be running.

Paid calls use the existing x402 seller and ledger. No funding/withdrawal or
replacement purchase is attempted. Labels are read only by offline scoring.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

from .config import ROOT
from .invoice_dataset import DATASET_VERSION, build
from .invoice_extraction import VERSION, verify
from .invoice_study import code_hashes
from .ledger import Ledger, PolicyError
from .leases import exclusive
from .metal import MetalRail, PaymentPending
from .payments import MetalEngineRail
from .treasury import NoRedirect
from .verifier import VERIFY_COST
from .workload import Task


def hardware():
    result=subprocess.run(['nvidia-smi','--query-gpu=memory.total,memory.used',
        '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10)
    if result.returncode:
        raise RuntimeError('GPU telemetry unavailable; no headroom claim can be made')
    total,used=[int(x.strip()) for x in result.stdout.strip().splitlines()[0].split(',')]
    if used>total*.8:
        raise RuntimeError('GPU usage exceeds 80%; stop before further inference')
    return {'total_vram_mib':total,'used_vram_mib':used,'headroom_at_least_20_percent':True}


def raw_profile(tier,model_id,rows,**extra):
    return {'label':'MEASURED','tier':tier,'model_id':model_id,'dataset_version':DATASET_VERSION,
            'verifier_version':VERSION,'code_sha256':code_hashes(),'rows':rows,**extra}


def corpus_records(corpus):
    if corpus:
        from .invoice_corpus import load
        manifest,records,_=load(corpus,include_truth=False)
        return records,{'dataset_version':manifest['dataset_version'],'corpus_sources_sha256':manifest['sources_sha256']}
    return build()[0],{'dataset_version':DATASET_VERSION,'corpus_sources_sha256':None}


def local(tier,partition,max_calls,output,*,corpus=None):
    if tier not in {'economy','balanced'}:
        raise ValueError('Only the installed 0.5B and 1.5B tiers are profiled; 3B needs a separate fit proof')
    manifest=json.loads((ROOT/'.tools/models'/f'{tier}-manifest.json').read_text(encoding='utf-8'))
    # An operator starts llama.cpp. This command cannot launch or replace it.
    url=os.environ.get('LOCAL_INFERENCE_URL','http://127.0.0.1:8080/v1/chat/completions')
    from urllib.parse import urlparse
    parsed=urlparse(url)
    if parsed.scheme!='http' or parsed.hostname not in {'127.0.0.1','localhost','::1'} or parsed.username or parsed.password:
        raise ValueError('Local model must be an unauthenticated loopback server')
    origin=f'{parsed.scheme}://{parsed.netloc}'
    opener=urllib.request.build_opener(NoRedirect())
    with opener.open(origin+'/health',timeout=3) as response:
        if response.status!=200:raise RuntimeError('Local model is not ready')
    with opener.open(origin+'/props',timeout=3) as response:
        props=json.load(response)
    if not isinstance(props.get('model_path'),str) or Path(props['model_path']).resolve()!=Path(manifest['model_path']).resolve():
        raise RuntimeError('Running model identity cannot be matched to the requested manifest')
    actual=hashlib.sha256(Path(manifest['model_path']).read_bytes()).hexdigest()
    if actual!=manifest['model_sha256']:
        raise RuntimeError('Model file hash differs from the installed manifest')
    from .providers import local_inference
    records,corpus_binding=corpus_records(corpus);rows=[];samples=[hardware()];provenance=code_hashes()
    if Path(output).exists():
        previous=json.loads(Path(output).read_text(encoding='utf-8'))
        if (previous.get('label')!='MEASURED' or previous.get('code_sha256')!=provenance
                or previous.get('model_sha256')!=actual or previous.get('tier')!=tier
                or any(previous.get(key)!=value for key,value in corpus_binding.items())):
            raise ValueError('Existing profile has different provenance; preserve it and use a fresh output')
        rows=previous['rows']
        samples=previous.get('hardware_samples',[])+samples
    def snapshot(**extra):
        return raw_profile(tier,manifest['model'],rows,partitions=sorted({r['partition'] for r in records
            if r['task']['id'] in {row['task_id'] for row in rows}}),model_sha256=actual,
            code_sha256=provenance,runtime_archive_sha256=manifest.get('runtime_archive_sha256'),
            hardware_samples=samples,decoding='temperature-0-json-schema',
            financial_cost_label='LOCAL_UNPRICED',payments_sent=0,**corpus_binding,**extra)
    seen={row['task_id'] for row in rows}
    for record in [r for r in records if r['partition']==partition and r['task']['id'] not in seen][:max_calls]:
        task=Task(**record['task']);started=time.perf_counter()
        try:
            trace={}
            response,latency=local_inference(task,usage=trace)
            row={'task_id':task.id,'output':response,'latency_ms':latency,'provider_cost_micro_usd':0}
            if 'source_span_selection' in trace:
                row['source_span_selection']=trace['source_span_selection']
        except Exception as error:
            row={'task_id':task.id,'output':None,'latency_ms':round((time.perf_counter()-started)*1000),
                 'provider_cost_micro_usd':0,'failure_type':type(error).__name__}
        rows.append(row)
        # Retain the completed call even if telemetry fails immediately afterwards.
        save(output,snapshot(stop_reason='POST_CALL_HARDWARE_CHECK_PENDING'))
        try:
            samples.append(hardware())
        except (RuntimeError,OSError,ValueError,subprocess.SubprocessError) as error:
            save(output,snapshot(stop_reason=type(error).__name__))
            raise
        save(output,snapshot(stop_reason=None))
    return snapshot(stop_reason=None)


def save(path,report):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',prefix=path.stem+'.',suffix='.pending',
                                     dir=path.parent,delete=False) as file:
        pending=Path(file.name)
        file.write(json.dumps(report,indent=2)+'\n')
    try:
        for retry in range(8):
            try:
                os.replace(pending,path)
                break
            except PermissionError:
                if retry==7:raise
                time.sleep(.02*2**retry)
    finally:
        try:pending.unlink(missing_ok=True)
        except OSError:pass


def paid(scope,origin,budget,cap,max_calls,output,execute=False,reference_scope=None,reference_budget=0,
         partition='calibration',client_factory=MetalRail,health=None,directory=None,corpus=None,
         before_purchase=None,after_purchase=None):
    if not execute:
        raise ValueError('Paid profiling requires --execute and written approval for its aggregate cap and call count')
    if not isinstance(scope,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,36}',scope) or reference_scope==scope:
        raise ValueError('Valid distinct primary/reference wallet scopes required')
    if reference_scope and not re.fullmatch(r'[A-Za-z0-9_-]{1,36}',reference_scope):
        raise ValueError('Invalid reference wallet scope')
    if (any(type(n) is not int for n in (budget,cap,max_calls,reference_budget))
            or budget<=0 or cap<=0 or not 1<=max_calls<=180 or not 0<=reference_budget<budget
            or bool(reference_scope)!=bool(reference_budget) or cap+VERIFY_COST>budget-reference_budget):
        raise ValueError('Caps must include check costs and reference allocation within the aggregate budget')
    directory=Path(directory or ROOT/'data/invoice-profiles');directory.mkdir(parents=True,exist_ok=True)
    records,corpus_binding=corpus_records(corpus)
    records=[r for r in records if r['partition']==partition][:max_calls]
    tasks=[Task(**r['task']) for r in records]
    ref_tasks=[Task('REF-'+t.id,t.kind,t.source) for t in tasks]
    terms={'scope':scope,'origin':origin,'budget':budget,'cap':cap,'max_calls':max_calls,
           'reference_scope':reference_scope,'reference_budget':reference_budget,'partition':partition,
           **corpus_binding,'code_sha256':code_hashes()}
    evidence_label='MEASURED' if client_factory is MetalRail else 'MOCK'
    # Readiness never invokes a provider inference request.
    if client_factory is MetalRail:
        from urllib.parse import urlparse
        parsed=urlparse(origin)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/') or not (parsed.scheme=='https' or parsed.scheme=='http' and parsed.hostname in {'127.0.0.1','localhost','::1'}):
            raise ValueError('Use an approved provider origin')
        with urllib.request.build_opener(NoRedirect()).open(origin.rstrip('/')+'/health',timeout=5) as response:
            health=json.load(response)
    if not isinstance(health,dict) or not (health.get('inference_ready') is True and health.get('chain')==63825
        and health.get('provider_id')=='hosted-premium' and health.get('upstream_funding')=='PARTNER_CREDITS_OPERATOR_DECLARED'):
        raise RuntimeError('Premium seller/partner-credit readiness is unverified; no purchase sent')
    model_id=health.get('provider_model','operator-configured-premium')
    if client_factory is MetalRail and (not isinstance(model_id,str) or not model_id or model_id=='operator-configured-premium'):
        raise RuntimeError('Seller must identify its configured premium model before profiling')
    output_owner=hashlib.sha256(str(Path(output).resolve()).encode()).hexdigest()[:20]
    with exclusive(directory/('output-'+output_owner+'.owner.sqlite')), exclusive(directory/(scope+'.owner.sqlite')):
        binding=directory/(scope+'.json');ledger=Ledger(directory/'ledger.sqlite')
        bound=json.loads(binding.read_text(encoding='utf-8')) if binding.exists() else None
        if bound and bound['terms']!=terms:raise ValueError('Scope is already bound to a different study/cap')
        previous=json.loads(Path(output).read_text(encoding='utf-8')) if Path(output).exists() else None
        if previous:
            expected={'label':evidence_label,'tier':'hosted-premium','model_id':model_id,
                      **corpus_binding,'verifier_version':VERSION,'code_sha256':terms['code_sha256']}
            if any(previous.get(k)!=v for k,v in expected.items()):
                raise ValueError('Existing profile has different provenance; use a fresh output')
            ids={row['task_id'] for row in previous['rows']}
            if len(ids)!=len(previous['rows']):raise ValueError('Duplicate source IDs in existing profile')
            current_run=bound['run_id'] if bound else None
            if any(row['task_id'] in {t.id for t in tasks} and row.get('run_id')!=current_run for row in previous['rows']):
                raise ValueError('Source already measured by another scope; no repeated purchase authorized')
        old_jobs=ledger.jobs(bound['run_id']) if bound else []
        if any(a['state'] in {'RESERVED','DISPATCHING','PAID'} for j in old_jobs for a in ledger.attempts(j['id'])):
            raise PaymentPending('An original invoice is unresolved; profile cannot retry it automatically')
        specs=[];rails=[]
        for wallet,allocation,job_tasks in [(scope,budget-reference_budget,tasks)]+([(reference_scope,reference_budget,ref_tasks)] if reference_scope else []):
            if client_factory is MetalRail:
                if not (ROOT/'data/metal'/wallet/'wallet.sqlite').is_file():
                    raise RuntimeError('Existing funded clearing wallet required; profiling never deposits or generates a replacement')
                client=MetalRail(wallet,origin,cap,allocation,execute=True)
            else:client=client_factory(wallet,origin,cap,allocation)
            balance=client.balance()
            already=old_jobs[len(rails)]['rail_spent'] if old_jobs else 0
            if int(balance['spendable_base_units'])<(allocation-already)*10**12:
                raise RuntimeError('Insufficient confirmed clearing float; no deposit or purchase attempted')
            rails.append(MetalEngineRail(wallet,origin,cap,allocation,client=client,expected_provider_ids=['hosted-premium']))
            specs.append(dict(seed=0,policy='real-premium',hold=allocation,allocation=allocation,
                              price_cap=cap,tasks=[t.public() for t in job_tasks]))
        if binding.exists():
            bound=json.loads(binding.read_text(encoding='utf-8'))
            if bound['terms']!=terms:raise ValueError('Scope is already bound to a different study/cap')
            run=bound['run_id']
        else:
            run=ledger.create_run(specs,budget,float_mode='TESTNET');save(binding,{'terms':terms,'run_id':run})
        jobs=ledger.jobs(run);rows=[];stop=None
        retained=[r for r in (previous or {}).get('rows',[]) if r.get('run_id')!=run]
        prior_runs=[r for r in (previous or {}).get('runs',[]) if r['run_id']!=run]
        def snapshot():
            attempts=[a for j in jobs for a in ledger.attempts(j['id'])]
            current={'run_id':run,'scope':scope,'partition':partition,'stop_reason':stop,
                'pending_attempts':sum(a['state'] in {'RESERVED','DISPATCHING','PAID'} for a in attempts),
                'confirmed_provider_spend_including_failed_calls_micro_usd':sum(a['price'] for a in attempts if a['receipt']),
                'verification_cost_micro_usd':sum(a['verify_cost'] for a in attempts if a['passed'] is not None),
                'audit':ledger.audit()}
            runs=prior_runs+[current]
            return raw_profile('hosted-premium',model_id,retained+rows,label=evidence_label,
                code_sha256=terms['code_sha256'],run_id=run,runs=runs,**corpus_binding,
                upstream_funding='PARTNER_CREDITS_OPERATOR_DECLARED',upstream_dollar_cost='UNMEASURED',
                verification_cost_label='SIMULATED',latency_source='PROVIDER_REPORTED_INFERENCE_ONLY',
                stop_reason=next((r['stop_reason'] for r in runs if r.get('stop_reason')),None),audit=ledger.audit(),
                **{k:sum(r[k] for r in runs) for k in ('pending_attempts',
                   'confirmed_provider_spend_including_failed_calls_micro_usd','verification_cost_micro_usd')})
        def purchase(index,task):
            job,rail=jobs[index],rails[index]
            prior=next((a for a in ledger.attempts(job['id']) if a['step_id']==task.id),None)
            if prior:
                if prior['state'] in {'RESERVED','DISPATCHING','PAID'}:
                    raise PaymentPending('Original purchase unresolved; no retry or replacement sent')
                return prior
            if sum(len(ledger.attempts(j['id'])) for j in jobs)>=max_calls:
                raise PolicyError('Aggregate call-count cap exhausted, including reference passes')
            with ledger.worker(job['id']) as owner:
                offers=rail.quote_for_task(task)
                if len(offers)!=1:raise RuntimeError('A valid premium quote is required')
                offer=offers[0]
                if before_purchase:before_purchase(task,offer)
                key=ledger.reserve(job['id'],task,0,offer,VERIFY_COST,expected_version=job['mandate_version'])
                ledger.assert_can_pay(key,owner)
                receipt=rail.pay(key,offer)
                ledger.record_paid(key,receipt);ledger.finish_attempt(key,receipt['output'],verify(task,receipt['output']))
                if after_purchase:after_purchase(task,offer,receipt)
            return next(a for a in ledger.attempts(job['id']) if a['key']==key)
        for index,task in enumerate(tasks):
            row=None
            try:
                primary=purchase(0,task)
                metadata=json.loads(primary['provider_metadata']) if primary.get('provider_metadata') else {}
                row={'task_id':task.id,'output':json.loads(primary['output']), 'receipt':primary['receipt'],
                     'run_id':run,'provider_metadata':metadata,
                     'reservation_key':primary['key'],'provider_cost_micro_usd':primary['price'],
                     'verification_cost_micro_usd':primary['verify_cost'],'latency_ms':metadata.get('latency_ms')}
                if client_factory is MetalRail and (metadata.get('provider_model')!=model_id
                    or metadata.get('provider_type')!='ANTHROPIC_API'
                    or metadata.get('funding_source')!='PARTNER_CREDITS_OPERATOR_DECLARED'):
                    raise RuntimeError('Delivered model/funding metadata does not match the study; charge retained')
                if reference_scope and verify(task,row['output'])['decision']=='review':
                    reference=purchase(1,ref_tasks[index]);row.update(reference_output=json.loads(reference['output']),
                        reference_receipt=reference['receipt'],reference_cost_micro_usd=reference['price'],
                        reference_provider_metadata=json.loads(reference['provider_metadata']) if reference.get('provider_metadata') else {},
                        verification_cost_micro_usd=primary['verify_cost']+reference['verify_cost'])
                    if client_factory is MetalRail and row['reference_provider_metadata'].get('provider_model')!=model_id:
                        raise RuntimeError('Reference model identity changed; charge retained and study stopped')
                rows.append(row)
            except Exception as error:
                # Preserve accounting even for an unexpected transport/decoder failure.
                # No fallback call, automatic recovery or replacement is dispatched.
                if row is not None:rows.append({**row,'reference_or_followup_failed':True})
                stop=type(error).__name__;break
            save(output,snapshot())
        result=snapshot()
        save(output,result);return result
