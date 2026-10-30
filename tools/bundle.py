"""Build a reviewable source archive, excluding ignored data and configured secrets."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.config import LOCAL_CONFIG, FUNDING_WALLET


def main():
    paths = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'], cwd=ROOT).decode().split('\0')
    paths = sorted(set(p for p in paths if p and (ROOT / p).is_file()))
    sensitive = []
    if LOCAL_CONFIG.exists():
        config = json.loads(LOCAL_CONFIG.read_text(encoding='utf-8'))
        for key in ('AIRWALLEX_API_KEY','AIRWALLEX_CLIENT_ID','AIRWALLEX_ACCOUNT_ID','AGENT_PRIVATE_KEY','METAL_RPC_URL'):
            value = config.get(key)
            if value:
                sensitive.append(value.encode())
    if FUNDING_WALLET.exists():
        key = json.loads(FUNDING_WALLET.read_text(encoding='utf-8'))['private_key']
        sensitive.extend([key.encode(), key.removeprefix('0x').encode()])
    for filename in paths:
        payload = (ROOT / filename).read_bytes()
        if any(secret in payload for secret in sensitive):
            raise RuntimeError('Configured secret found in a candidate source file; archive not created')
        if filename.startswith(('data/','.tools/','tmp/','dist/')) or '/node_modules/' in filename:
            raise RuntimeError('Private/generated content was included; archive not created')
    target = ROOT / 'dist/touchstone-source.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for filename in paths:
            archive.write(ROOT / filename, 'touchstone/' + filename)
    report = {'archive':target.name,'source_files':len(paths),'bytes':target.stat().st_size,
              'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
              'configured_secret_scan':'passed','private_runtime_data_included':False,
              'published':False,'submitted':False}
    (target.parent / 'bundle-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
