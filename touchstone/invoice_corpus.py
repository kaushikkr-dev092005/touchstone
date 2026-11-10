"""Freeze a prospective synthetic holdout; public sources and offline truth stay separate."""
import copy
import hashlib
import json
from pathlib import Path
import time

from .invoice_dataset import build
from .invoice_extraction import FIELDS,supported
from .workload import Task

LABELS=('Invoice ID','Supplier','Purchase order','Currency','Subtotal','Tax','Total due')
FAMILIES=('equals-record','value-parenthesis','arrow-record','wrapped-value')


def digest(data):return hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()


def freeze(directory,seed):
    """Write once, before any model result. Authored by the implementer, not independently blind."""
    directory=Path(directory)
    if (directory/'manifest.json').exists():
        manifest,_,_=load(directory,include_truth=True)
        if manifest.get('holdout_seed')!=seed:raise ValueError('Frozen corpus cannot change seed')
        return manifest
    if directory.exists() and any(directory.iterdir()):raise ValueError('Use an empty corpus directory')
    calibration,old_truth=build()
    records=[copy.deepcopy(r) for r in calibration if r['partition']=='calibration']
    truth={r['task']['id']:copy.deepcopy(old_truth[r['task']['id']]) for r in records}
    for family,style in enumerate(FAMILIES):
        base,base_truth=build(seed+family*1000)
        for number,record in enumerate(base[:15]):
            old=base_truth[record['task']['id']]['output'];lines=[];cursor=0
            fields={};items=[]
            def add(line):
                nonlocal cursor
                start=cursor;lines.append(line);cursor+=len(line)+1;return start
            def header(label,value):
                if family==0:line=f'{label} = {value}'
                elif family==1:line=f'{value} ({label})'
                elif family==2:line=f'{label} → {value}'
                else:
                    add(label);line='    '+value
                begin=add(line)+line.index(value)
                return {'value':value,'start':begin,'end':begin+len(value)}
            add('Accounts payable receiving copy / prospective evaluation')
            if record['scenario']=='ocr_noise':add('Scanned c0py — receiv1ng n0tes [OCR]')
            for role,label in zip(FIELDS,LABELS):
                fields[role]=header(label,old['fields'][role]['value']) if old['fields'][role] else None
            scenario=record['scenario']
            if number==14:
                header('Invoice ID',f'AMBIG-{seed}-{family}-{number}')
                fields['invoice_id']=None;scenario='ambiguous_header'
            for old_item in old['items']:
                line=old_item['line']['value'];start=add(line)
                item={'line':{'value':line,'start':start,'end':start+len(line)}}
                for role in ('quantity','unit_price_cents','line_total_cents'):
                    span=old_item[role];begin=start+span['start']-old_item['line']['start']
                    item[role]={'value':span['value'],'start':begin,'end':begin+len(span['value'])}
                items.append(item)
            add('Receiving copy only. Do not initiate a payment.')
            source={**copy.deepcopy(record['task']['source']),'text':'\n'.join(lines)}
            identity=f'H2-{seed}-{family}-{number:02}'
            task=Task(identity,'invoice_extraction',source)
            fingerprint=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
            records.append({'template_id':'prospective-'+style,'partition':'holdout','scenario':scenario,
                'source_sha256':fingerprint,'task':task.public()})
            truth[identity]={'output':{'fields':fields,'items':items},'scenario':scenario,
                'missing_fields':[name for name,value in fields.items() if value is None]}
    sources=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records).encode()
    labels=(json.dumps(truth,ensure_ascii=False,indent=2)+'\n').encode()
    manifest={'label':'SIMULATED','dataset_version':f'invoice-prospective-v2-{seed}',
        'holdout_seed':seed,'sources':180,'unique_sources':len({r['source_sha256'] for r in records}),
        'partition_counts':{'calibration':120,'holdout':60},
        'templates':{p:sorted({r['template_id'] for r in records if r['partition']==p}) for p in ('calibration','holdout')},
        'sources_sha256':digest(sources),'offline_truth_sha256':digest(labels),
        'frozen_at':time.time(),'model_calls_at_freeze':0,'offline_truth_never_sent_to_models':True,
        'provenance':'Synthetic implementer-authored holdout; new layout families; no model outputs used to tune it. Not independent vendor data.',
        'qualification_thresholds_changed':False}
    directory.mkdir(parents=True,exist_ok=True)
    for name,payload in [('sources.jsonl',sources),('offline-truth.json',labels),
        ('manifest.json',(json.dumps(manifest,indent=2)+'\n').encode())]:
        with (directory/name).open('xb') as stream:stream.write(payload)
    return manifest


def load(directory,include_truth=False):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    payload=(directory/'sources.jsonl').read_bytes()
    if len(payload)>2000000 or digest(payload)!=manifest['sources_sha256']:raise ValueError('Frozen sources changed')
    records=[json.loads(line) for line in payload.decode('utf-8').splitlines()]
    ids=[r['task']['id'] for r in records]
    if (len(records)!=manifest['sources'] or len(set(ids))!=len(ids)
            or any(not supported(Task(**r['task'])) for r in records)
            or {p:sum(r['partition']==p for r in records) for p in ('calibration','holdout')}!=manifest['partition_counts']):
        raise ValueError('Frozen corpus schema or partitions changed')
    for record in records:
        actual=hashlib.sha256(json.dumps(record['task']['source'],sort_keys=True).encode()).hexdigest()
        if record['source_sha256']!=actual:raise ValueError('Source fingerprint changed')
    truth=None
    if include_truth:
        labels=(directory/'offline-truth.json').read_bytes()
        if len(labels)>2000000 or digest(labels)!=manifest['offline_truth_sha256']:raise ValueError('Frozen truth changed')
        truth=json.loads(labels)
        if set(truth)!=set(ids):raise ValueError('Frozen truth IDs changed')
    return manifest,records,truth
