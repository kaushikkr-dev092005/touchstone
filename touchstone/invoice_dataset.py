"""Synthetic invoice corpus. Labels are for offline scoring only."""
import hashlib
import json
from pathlib import Path
import random

from .invoice_extraction import FIELDS
from .workload import Task

DATASET_VERSION = 'invoice-exceptions-180-v1'
CALIBRATION = tuple(range(8))
HOLDOUT = tuple(range(8, 12))


def build(seed=20261103):
    records, truth = [], {}
    for template in range(12):
        for number in range(15):
            rng = random.Random(seed + template*100 + number)
            identity = f'IX-{template:02}-{number:03}-{seed}'
            supplier, po = f'Vendor {template:02} Supply', f'PO-{template:02}-{number:03}'
            scenario = ('clean', 'ocr_noise', 'missing_field', 'duplicate_reference', 'conflicting_po')[number % 5]
            qty, price, qty2, price2 = rng.randint(1,9), rng.randint(100,9000), rng.randint(1,6), rng.randint(80,7000)
            subtotal, tax = qty*price+qty2*price2, rng.randint(0,800)
            money = lambda cents: f'USD {cents//100}.{cents%100:02}'
            values = dict(zip(FIELDS, [identity, supplier, po if scenario!='conflicting_po' else po+'-OTHER',
                                       'USD', money(subtotal), money(tax), money(subtotal+tax)]))
            missing = FIELDS[(template+number)%len(FIELDS)] if scenario=='missing_field' else None
            labels = ['Invoice ID','Supplier','Purchase order','Currency','Subtotal','Tax','Total due']
            alternatives = ['Document reference','Issued by','Procurement reference','Settlement currency','Net goods','Sales tax','Amount payable']
            header, positions = [], {}
            cursor = 0
            def add(text):
                nonlocal cursor
                start = cursor
                header.append(text);cursor += len(text)+1
                return start
            add(f'Invoice receiving record / layout {template:02}')
            if scenario == 'ocr_noise':
                add('Scanned c0py — receiv1ng n0tes; page 1 of 1   [OCR]')
            order = list(range(7))
            if template >= 2:
                rng.shuffle(order)
            for index in order:
                name = FIELDS[index]
                if name == missing:
                    continue
                value = values[name]
                if template in (0,1):
                    line = f'{labels[index]}: {value}'
                elif template in (2,3):
                    line = f'{alternatives[index]} => {value}'
                elif template in (4,5):
                    line = f'{value}  [{alternatives[index]}]'
                elif template in (6,7):
                    line = f'| {alternatives[index]} | {value} |'
                elif template in (8,9):
                    line = f'{alternatives[index].upper()}\t{value}'
                else:
                    line = f'{alternatives[index]} ... {{{value}}}'
                start = add(line)+line.index(value)
                positions[name] = {'value': value, 'start': start, 'end': start+len(value)}
            items = []
            for index, (quantity, unit) in enumerate(((qty,price),(qty2,price2)), 1):
                q,u,a = str(quantity),money(unit),money(quantity*unit)
                prefix = f'ITEM-{index:02}'
                if template in (0,1):
                    line = f'{prefix} | quantity={q} | unit={u} | amount={a}'
                    tokens = (('quantity='+q,q),('unit='+u,u),('amount='+a,a))
                elif template % 2:
                    line = f'{prefix}  extension {a}; {q} units @ {u}'
                    tokens = ((q+' units',q),('@ '+u,u),('extension '+a,a))
                else:
                    line = f'{prefix}  {u} each / {q} pcs / extended {a}'
                    tokens = ((q+' pcs',q),(u+' each',u),('extended '+a,a))
                start = add(line)
                item = {'line': {'value': line,'start':start,'end':start+len(line)}}
                for name,(anchor,value) in zip(('quantity','unit_price_cents','line_total_cents'),tokens):
                    at=start+line.index(anchor)+anchor.index(value)
                    item[name]={'value':value,'start':at,'end':at+len(value)}
                items.append(item)
            add('Receiving copy only. Do not initiate a payment.')
            if scenario == 'conflicting_po':
                add(f'Prior email cites {po}; invoice reference above conflicts. Operator review required.')
            text='\n'.join(header)
            total=subtotal+tax
            payments=[]
            if scenario=='duplicate_reference':
                p={'payment_id':f'PAY-{identity}','invoice_id':identity,'purchase_order_id':po,
                   'supplier_name':supplier,'currency':'USD','amount_cents':total,'status':'in_progress'}
                payments=[p,{**p,'status':'settled'}]
            source={'text':text,'purchase_order':{'purchase_order_id':po,'supplier_name':supplier,
                    'currency':'USD','authorized_cents':total*4},'payments':payments}
            task=Task(identity,'invoice_extraction',source)
            partition='calibration' if template in CALIBRATION else 'holdout'
            fingerprint=hashlib.sha256(json.dumps(task.source,sort_keys=True).encode()).hexdigest()
            records.append({'template_id':f'layout-{template:02}','partition':partition,'scenario':scenario,
                            'source_sha256':fingerprint,'task':task.public()})
            truth[identity]={'output':{'fields':{name:positions.get(name) for name in FIELDS},'items':items},
                             'missing_fields':[missing] if missing else [],'scenario':scenario}
    return records,truth


def save(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    records,truth=build()
    public=directory/'sources.jsonl';offline=directory/'offline-truth.json'
    public.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in records),encoding='utf-8')
    offline.write_text(json.dumps(truth,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest={'label':'SIMULATED','dataset_version':DATASET_VERSION,'sources':len(records),
        'unique_sources':len({r['source_sha256'] for r in records}),
        'partition_counts':{p:sum(r['partition']==p for r in records) for p in ('calibration','holdout')},
        'templates':{'calibration':[f'layout-{i:02}' for i in CALIBRATION],
                     'holdout':[f'layout-{i:02}' for i in HOLDOUT]},
        'sources_sha256':hashlib.sha256(public.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'offline_truth_sha256':hashlib.sha256(offline.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
        'provenance':'Known generated truth; synthetic, not independently human-labelled or representative vendor data',
        'offline_truth_never_sent_to_models':True}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest
