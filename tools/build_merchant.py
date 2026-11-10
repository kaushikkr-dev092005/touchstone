"""Package the dependency-free sandbox Worker from one exact Git commit."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent


def build(commit='HEAD', output='dist/merchant-site.tar.gz', unpack_directory=None):
    sha = subprocess.check_output(['git', 'rev-parse', '--verify', commit+'^{commit}'], cwd=ROOT, text=True).strip()
    files = {
        '.openai/hosting.json': '.openai/hosting.json',
        'dist/server/index.js': 'apps/merchant/worker.mjs',
        'dist/server/product-image.mjs': 'apps/merchant/product-image.mjs',
    }
    contents = {target: subprocess.check_output(['git', 'show', sha+':'+source], cwd=ROOT)
                for target, source in files.items()}
    config = json.loads(contents['.openai/hosting.json'])
    if not config.get('project_id') or config.get('d1') != 'DB' or config.get('r2') is not None:
        raise ValueError('Expected the existing Sites project and only a DB binding')
    if unpack_directory is not None:
        destination=(ROOT/unpack_directory).resolve()
        for name,body in contents.items():
            target=destination/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(body)
        return {'source_commit':sha,'project_id':config['project_id'],
                'worker_directory':str(destination),'secrets_packaged':False}
    path = ROOT/output
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, 'w:gz') as archive:
        for target, body in contents.items():
            info = tarfile.TarInfo(target)
            info.size, info.mode = len(body), 0o644
            archive.addfile(info, io.BytesIO(body))
    report = {'source_commit': sha, 'project_id': config['project_id'],
              'archive': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'files': {name: hashlib.sha256(body).hexdigest() for name, body in contents.items()},
              'secrets_packaged': False}
    path.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', default='HEAD')
    parser.add_argument('--output', default='dist/merchant-site.tar.gz')
    parser.add_argument('--unpack-directory',help='Emit only the committed Worker/manifest tree for Sites packaging')
    args = parser.parse_args()
    print(json.dumps(build(args.commit, args.output, args.unpack_directory), indent=2))
