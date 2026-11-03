"""Offline invoice scoring and procurement preview. No hidden truth in checks."""
import hashlib
import json
from pathlib import Path
import statistics
import time

from .eligibility import screen, source_key
from .invoice_dataset import DATASET_VERSION, build, save
from .invoice_extraction import VERSION, deterministic, duplicate_reference, verify
from .workload import Task

CODE = ('invoice_dataset.py','invoice_extraction.py','invoice_study.py','invoice_profile.py',
        'providers.py','local_tools.py','eligibility.py','verifier.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def code_hashes():
    root=Path(__file__).parent
    return {name:hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in CODE}


def assess(task, primary, reference=None, reference_cost=0):
    """Optional independent extraction; both calls remain charged on disagreement."""
    verdict=verify(task,primary)
    if reference is None:
        return {**verdict,'reference_cost_micro_usd':0,'reference_used':False}
    if type(reference_cost) is not int or reference_cost<=0:
        raise ValueError('Reference inference needs a separately recorded positive charge')
    second=verify(task,reference)
    agree=primary==reference and verdict['passed'] and second['passed']
    return {**verdict,'passed':bool(agree),'score':float(agree),
        'decision':verdict.get('decision') if agree else 'review',
        'reason':verdict['reason'] if agree else 'Independent extraction disagrees or failed checks; human review required',
        'reference_used':True,'reference_cost_micro_usd':reference_cost,
        'payment_authorized':False}


def score(records,truth,rows):
    """Only this offline scorer reads labels. Unknown/duplicate row IDs fail closed."""
    expected={r['task']['id']:r for r in records}
    seen=set();out=[]
    for row in rows:
        identity=row.get('task_id')
        if identity not in expected or identity in seen:
            raise ValueError('Response IDs must match unique corpus sources')
        seen.add(identity);record=expected[identity];task=Task(**record['task'])
        response=row.get('output')
        correct=response==truth[identity]['output']
        reference=row.get('reference_output')
        refcost=row.get('reference_cost_micro_usd',0)
        verdict=assess(task,response,reference,refcost)
        if row.get('reference_or_followup_failed'):
            verdict={**verdict,'passed':False,'decision':'review'}
            correct=False
        for field in ('provider_cost_micro_usd','reference_cost_micro_usd','verification_cost_micro_usd','latency_ms'):
            value=row.get(field,0)
            if field=='latency_ms' and value is None:continue
            if type(value) is not int or value<0:
                raise ValueError('Costs and latencies must be nonnegative integers')
        if reference is not None:
            correct=correct and reference==truth[identity]['output']
        out.append({**row,'partition':record['partition'],'template_id':record['template_id'],
            'source_key':source_key(task),'strict_correct':correct,'verifier_passed':verdict['passed'],
            'decision':verdict['decision'],'false_accept':verdict['passed'] and not correct,
            'tool_resolved':deterministic(task) is not None,
            'adds_value_over_tool':correct and verdict['passed'] and deterministic(task) is None,
            'reference_cost_micro_usd':refcost})
    return out


def metrics(rows):
    lat=sorted(r['latency_ms'] for r in rows if type(r.get('latency_ms')) is int)
    accepted=sum(r['verifier_passed'] for r in rows)
    return {'sources_scored':len(rows),'strict_correct':sum(r['strict_correct'] for r in rows),
        'accepted':accepted,'false_accepts':sum(r['false_accept'] for r in rows),
        'false_accept_rate_among_accepted':sum(r['false_accept'] for r in rows)/accepted if accepted else None,
        'refusals_or_review':sum(not r['verifier_passed'] or r['decision']=='review' for r in rows),
        'provider_cost_micro_usd':sum(r.get('provider_cost_micro_usd',0) for r in rows),
        'reference_cost_micro_usd':sum(r.get('reference_cost_micro_usd',0) for r in rows),
        'verification_cost_micro_usd':sum(r.get('verification_cost_micro_usd',0) for r in rows),
        'latency_samples':len(lat),
        'latency_p50_ms':statistics.median(lat) if lat else None,
        'latency_p95_ms':lat[max(0,(__import__('math').ceil(len(lat)*.95)-1))] if lat else None,
        'correct_beyond_tools':sum(r['adds_value_over_tool'] for r in rows)}


def evaluate_profile(records,truth,raw):
    if (raw.get('label')!='MEASURED' or raw.get('dataset_version')!=DATASET_VERSION
            or raw.get('code_sha256')!=code_hashes() or raw.get('verifier_version')!=VERSION):
        raise ValueError('Profile must be measured and match current corpus/checker provenance')
    rows=score(records,truth,raw['rows'])
    calibration=[r for r in rows if r['partition']=='calibration']
    holdout=[r for r in rows if r['partition']=='holdout']
    gate=screen([(r['source_key'],r['strict_correct']) for r in calibration])
    complete=len(calibration)==sum(r['partition']=='calibration' for r in records)
    heldout_complete=len(holdout)==sum(r['partition']=='holdout' for r in records)
    heldout_pass=heldout_complete and sum(r['strict_correct'] for r in holdout)>=.95*len(holdout) and not any(r['false_accept'] for r in holdout)
    return {'label':'MEASURED','model_id':raw['model_id'],'tier':raw['tier'],
        'calibration':metrics(calibration),'holdout':metrics(holdout),'screen':gate,
        'calibration_complete':complete,'heldout_complete':heldout_complete,'heldout_validation_passed':heldout_pass,
        'eligible':complete and gate['passes_statistical_screen'] and heldout_pass and not raw.get('stop_reason') and not raw.get('pending_attempts',0),
        'live_purchase_authorized':False,'source_profile_sha256':hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()}


def showcase(qualified=None):
    from .local_tools import solve
    known=solve(Task('known-total','arithmetic',{'amounts_cents':[1250,775],'discount_cents':25}))
    return {'label':'SIMULATED','payments_sent':0,'live_purchase_authorized':False,'tasks':[
        {'task':'Calculate a known invoice total','decision':'LOCAL_TOOL','label':'MEASURED',
         'reason':'Bounded integer calculation: 1250 + 775 - 25 = 2000 cents','result_cents':known['total_cents']},
        {'task':'Extract an unfamiliar invoice','decision':'QUALIFIED_MODEL_AVAILABLE' if qualified else 'REVIEW_REQUIRED',
         'label':'MEASURED' if qualified else 'BLOCKED',
         'reason':f"Offline-qualified model: {qualified['model_id']}; a separate spend mandate is still required" if qualified else 'No current invoice-extraction model has passed the complete measured qualification screen'},
        {'task':'Resolve an ambiguous duplicate payment','decision':'HUMAN_REVIEW','label':'SIMULATED',
         'reason':'Conflicting records share a payment reference; no purchase or payment is authorized'}]}


def report(directory,profile_dir=None):
    directory=Path(directory);manifest=save(directory/'dataset');records,truth=build()
    rows=[]
    for record in records:
        task=Task(**record['task']);started=time.perf_counter();output=deterministic(task)
        rows.append({'task_id':task.id,'output':output,'latency_ms':max(0,round((time.perf_counter()-started)*1000)),
                     'provider_cost_micro_usd':0})
    baseline=score(records,truth,rows)
    profiles=[];rejected=[];profile_hashes={}
    for path in sorted(Path(profile_dir or directory/'profiles').glob('*.json')):
        try:
            profiles.append(evaluate_profile(records,truth,json.loads(path.read_text(encoding='utf-8'))))
            profile_hashes[path.name]=digest(path)
        except (ValueError,KeyError,TypeError,OSError):rejected.append({'file':path.name,'label':'BLOCKED','reason':'Profile provenance/schema invalid or stale'})
    qualified=next((p for p in profiles if p['eligible']),None)
    result={'label':'MEASURED','dataset':manifest,'code_sha256':code_hashes(),
        'baseline':{'label':'MEASURED','financial_cost_label':'SIMULATED','metrics':metrics(baseline),
            'coverage':sum(r['output'] is not None for r in baseline)/len(records),
            'note':'Synthetic sources; CPU/review costs unpriced, no model calls or payments'},
        'profiles':profiles,'profile_files_sha256':profile_hashes,'rejected_profiles':rejected,'showcase':showcase(qualified),
        'qualification_status':'OFFLINE_MODEL_AVAILABLE' if qualified else 'BLOCKED_NO_ELIGIBLE_MODEL',
        'threshold_changed':False,'models_measured':len(profiles),
        'hosted_funding_source':'PARTNER_CREDITS_UNVERIFIED_UNTIL_CONFIGURED',
        'live_purchase_authorized':False}
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'baseline-raw.json').write_text(json.dumps(baseline,indent=2)+'\n',encoding='utf-8')
    (directory/'report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def dashboard(directory):
    try:
        result=json.loads((Path(directory)/'report.json').read_text(encoding='utf-8'))
        if result['code_sha256']!=code_hashes():
            raise ValueError('Stale study')
        if digest(Path(directory)/'dataset/sources.jsonl')!=result['dataset']['sources_sha256']:
            raise ValueError('Corpus changed')
        for name,expected_digest in result['profile_files_sha256'].items():
            if Path(name).name!=name or digest(Path(directory)/'profiles'/name)!=expected_digest:
                raise ValueError('Profile changed')
        return {k:result[k] for k in ('label','baseline','profiles','showcase','qualification_status','models_measured')}
    except (OSError,ValueError,KeyError,TypeError):
        return {'label':'BLOCKED','qualification_status':'MISSING_OR_STALE','showcase':showcase(),
                'profiles':[],'models_measured':0}
