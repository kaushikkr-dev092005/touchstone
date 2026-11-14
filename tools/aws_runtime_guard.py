"""Root-owned EC2 operating-window guard. No AWS SDK, payment keys or start API.

The conservative allocation counts stopped/unknown gaps as billable. It is not
an AWS billing meter or a guarantee against host failure or unrelated charges.
Only --enforce on the approved Linux host can request an OS poweroff.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import urllib.request


class GuardError(ValueError):pass


def epoch(value):
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',value):
        raise GuardError('INVALID_RUNTIME_POLICY')
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except ValueError:raise GuardError('INVALID_RUNTIME_POLICY') from None


def validate(policy):
    fields={'version','approval_reference','account_id','region','instance_type','month_utc',
            'window_started_at_utc','window_ends_at_utc','prior_consumed_seconds','maximum_compute_seconds','stop_margin_seconds'}
    if type(policy) is not dict or set(policy)!=fields:raise GuardError('INVALID_RUNTIME_POLICY')
    if (type(policy['version']) is not int or policy['version']!=1 or
        any(type(policy[k]) is not str for k in ['approval_reference','account_id','region','instance_type','month_utc']) or
        not re.fullmatch(r'[a-f0-9]{64}',policy['approval_reference']) or
        not re.fullmatch(r'\d{12}',policy['account_id']) or policy['region']!='ap-south-1' or
        policy['instance_type'] not in {'t4g.micro','t4g.nano'} or
        not re.fullmatch(r'\d{4}-\d{2}',policy['month_utc'])):raise GuardError('INVALID_RUNTIME_POLICY')
    prior,limit,margin=(policy[k] for k in ['prior_consumed_seconds','maximum_compute_seconds','stop_margin_seconds'])
    ceiling={'t4g.micro':360*3600,'t4g.nano':744*3600}[policy['instance_type']]
    if any(type(v) is not int for v in [prior,limit,margin]) or not 0<=prior<limit<=ceiling or not 300<=margin<=3600:
        raise GuardError('INVALID_RUNTIME_LIMIT')
    start,end=epoch(policy['window_started_at_utc']),epoch(policy['window_ends_at_utc'])
    if (end<=start or end-start+prior+margin>limit or
        any(datetime.fromtimestamp(v,timezone.utc).strftime('%Y-%m')!=policy['month_utc'] for v in [start,end])):
        raise GuardError('RUNTIME_WINDOW_EXCEEDS_APPROVAL')
    return start,end


def evaluate(policy,state_path,*,now,boot_id,uptime):
    start,end=validate(policy)
    if not all(math.isfinite(v) and v>=0 for v in [now,uptime]) or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}',boot_id):
        raise GuardError('RUNTIME_CLOCK_INVALID')
    fingerprint=hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    db=sqlite3.connect(state_path,timeout=5)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS runtime_state(id INTEGER PRIMARY KEY CHECK(id=1),policy_digest TEXT NOT NULL,utc REAL NOT NULL,boot_id TEXT NOT NULL,uptime REAL NOT NULL,observed REAL NOT NULL,charged INTEGER NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT policy_digest,utc,boot_id,uptime,observed,charged FROM runtime_state WHERE id=1').fetchone()
        if old and old[0]!=fingerprint:raise GuardError('RUNTIME_POLICY_CHANGED')
        if old and now<old[1]-2:raise GuardError('RUNTIME_CLOCK_ROLLBACK')
        if old and boot_id==old[2] and uptime<old[3]:raise GuardError('RUNTIME_CLOCK_INVALID')
        delta=uptime-old[3] if old and boot_id==old[2] else uptime
        logical=max(now,old[1]+delta if old and boot_id==old[2] else now)
        observed=(old[4] if old else 0)+delta
        charged=max(old[5] if old else 0,policy['prior_consumed_seconds']+math.ceil(max(0,logical-start)),
                    policy['prior_consumed_seconds']+math.ceil(observed))
        reason='WITHIN_APPROVED_WINDOW'
        if datetime.fromtimestamp(logical,timezone.utc).strftime('%Y-%m')!=policy['month_utc']:reason='MONTH_NOT_AUTHORIZED'
        elif logical<start:reason='WINDOW_NOT_STARTED'
        elif logical>=end or charged+policy['stop_margin_seconds']>=policy['maximum_compute_seconds']:reason='RUNTIME_WINDOW_EXHAUSTED'
        db.execute('INSERT INTO runtime_state VALUES(1,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET utc=excluded.utc,boot_id=excluded.boot_id,uptime=excluded.uptime,observed=excluded.observed,charged=excluded.charged',
                   (fingerprint,logical,boot_id,uptime,observed,charged))
        db.commit()
        return {'status':'PASS' if reason=='WITHIN_APPROVED_WINDOW' else 'STOP','reason':reason,
                'conservative_allocated_seconds':charged,'observed_host_seconds':math.ceil(observed),
                'maximum_compute_seconds':policy['maximum_compute_seconds'],'policy_digest':fingerprint,
                'billing_meter':False,'financial_dispatch_enabled':False}
    finally:db.close()


def host_identity():
    # Local IMDSv2 only; never reads role credentials or prints the token/document.
    base='http://169.254.169.254/latest/'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request=urllib.request.Request(base+'api/token',method='PUT',headers={'X-aws-ec2-metadata-token-ttl-seconds':'60'})
    with opener.open(request,timeout=2) as response:token=response.read(2048).decode()
    request=urllib.request.Request(base+'dynamic/instance-identity/document',headers={'X-aws-ec2-metadata-token':token})
    with opener.open(request,timeout=2) as response:return json.loads(response.read(16384))


def run(policy_path,state_path,*,now=None,boot_id=None,uptime=None,enforce=False,
        identity_reader=host_identity,stopper=None):
    if enforce and (os.name!='posix' or os.geteuid()!=0 or not hasattr(time,'CLOCK_BOOTTIME')):
        raise GuardError('APPROVED_LINUX_ROOT_HOST_REQUIRED')
    try:
        path=Path(policy_path)
        if enforce:
            stat=path.stat()
            if path.is_symlink() or stat.st_uid!=0 or stat.st_mode&0o077:raise GuardError('RUNTIME_POLICY_PERMISSIONS')
            parent=Path(state_path).parent
            if parent.resolve()!=Path('/var/lib/touchstone-runtime-guard'):raise GuardError('RUNTIME_STATE_LOCATION')
            parent.mkdir(mode=0o700,exist_ok=True)
            if parent.stat().st_uid!=0 or parent.stat().st_mode&0o077:raise GuardError('RUNTIME_STATE_PERMISSIONS')
        policy=json.loads(path.read_text(encoding='utf-8'));validate(policy)
        if enforce:
            actual=identity_reader()
            if any(actual.get(k)!=policy[p] for k,p in [('accountId','account_id'),('region','region'),('instanceType','instance_type')]):
                raise GuardError('RUNTIME_HOST_IDENTITY_MISMATCH')
        now=time.time() if now is None else now
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip() if boot_id is None else boot_id
        uptime=time.clock_gettime(time.CLOCK_BOOTTIME) if uptime is None else uptime
        result=evaluate(policy,state_path,now=now,boot_id=boot_id,uptime=uptime)
    except GuardError as error:result={'status':'STOP','reason':str(error)}
    except Exception:result={'status':'STOP','reason':'RUNTIME_STATE_OR_POLICY_UNAVAILABLE'}
    if enforce and result['status']!='PASS':
        (stopper or (lambda:subprocess.run(['/usr/bin/systemctl','--no-block','poweroff'],check=True,timeout=10)))()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy',required=True);parser.add_argument('--state',required=True)
    parser.add_argument('--enforce',action='store_true')
    args=parser.parse_args()
    result=run(args.policy,args.state,enforce=args.enforce)
    if not args.enforce or result['status']!='PASS':print(json.dumps(result))
    return 0 if result['status']=='PASS' else 2


if __name__=='__main__':raise SystemExit(main())
