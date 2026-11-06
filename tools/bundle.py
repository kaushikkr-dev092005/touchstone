"""Package an explicit committed tree; private working-tree edits are never included."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.scan_secrets import PUBLIC_EVIDENCE, scan_text


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,stderr=subprocess.PIPE)


def safe_path(name):
    path=PurePosixPath(name)
    return (not path.is_absolute() and '..' not in path.parts and not name.startswith(('data/','.tools/','tmp/','dist/','.git/'))
            and 'node_modules' not in path.parts and not any(part.startswith('.env') and part!='.env.example' for part in path.parts)
            and (name in PUBLIC_EVIDENCE or not re.search(r'(?:^|/)[^/]*wallet[^/]*\.json$',name,re.I)))


def inspect_payload(name,payload,secrets):
    if not safe_path(name):raise ValueError('Private/generated path cannot be bundled')
    if any(value in payload for value in secrets):raise ValueError('Configured secret found; bundle refused')
    if b'\x00' not in payload[:4096] and scan_text(payload.decode('utf-8','replace')):
        raise ValueError('Secret-shaped value found; bundle refused')


def build(ref='HEAD'):
    commit=git('rev-parse','--verify','--end-of-options',ref+'^{commit}').decode().strip()
    if not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}',commit):raise ValueError('A committed Git object is required')
    rows=git('ls-tree','-r','-z',commit).decode().split('\0')
    names={'AIRWALLEX_API_KEY','AIRWALLEX_CLIENT_ID','AGENT_PRIVATE_KEY','METAL_RPC_URL','ANTHROPIC_API_KEY'}
    secrets=[v.encode() for k,v in os.environ.items() if k in names and len(v)>12]
    contents=[];hashes={}
    for row in rows:
        if not row:continue
        meta,name=row.split('\t',1);mode,kind,oid=meta.split()
        if kind!='blob' or mode not in {'100644','100755'}:raise ValueError('Unsupported archive entry')
        payload=git('cat-file','blob',oid)
        inspect_payload(name,payload,secrets)
        contents.append((name,payload));hashes[name]=hashlib.sha256(payload).hexdigest()
    target=ROOT/'dist/touchstone-source.zip';target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix('.pending')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,payload in contents:archive.writestr('touchstone/'+name,payload)
    temporary.replace(target)
    report={'label':'MEASURED','archive':target.name,'commit':commit,'source_files':len(contents),
            'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
            'source_sha256':hashes,'secret_shape_scan':'passed','configured_environment_secret_scan':'passed',
            'private_runtime_data_included':False,'working_tree_edits_included':False,'published':False,'submitted':False}
    (target.parent/'bundle-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return {k:v for k,v in report.items() if k!='source_sha256'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ref',default='HEAD');args=parser.parse_args()
    try:print(json.dumps(build(args.ref),indent=2));return 0
    except (ValueError,OSError,subprocess.SubprocessError):
        print(json.dumps({'label':'BLOCKED','reason':'Committed source bundle failed validation; no secrets disclosed'}));return 1


if __name__ == '__main__':
    raise SystemExit(main())
