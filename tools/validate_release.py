"""Validate an exact committed source archive with fresh dependencies and isolated mock tests.

No local data, wallets or credential files are copied. Package installation is the only
external network activity; browser checks abort all non-loopback requests.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def clean_environment(node):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('AIRWALLEX_', 'METAL_', 'ANTHROPIC_', 'TOUCHSTONE_PROVIDER_', 'TOUCHSTONE_LIVE_', 'TOUCHSTONE_HOSTED_'))
           and k != 'AGENT_PRIVATE_KEY'}
    env['TOUCHSTONE_IGNORE_LOCAL_CONFIG'] = '1'
    env['PATH'] = str(Path(node).parent) + os.pathsep + env.get('PATH', '')
    return env


def extract_verified(archive, manifest, destination):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('Source archive hash differs')
    seen = set()
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            path = PurePosixPath(item.filename)
            if (not path.parts or path.parts[0] != 'touchstone' or path.is_absolute()
                    or '..' in path.parts or '\\' in item.filename or ':' in item.filename or item.is_dir()):
                raise ValueError('Unsafe archive member')
            name = str(PurePosixPath(*path.parts[1:]))
            payload = zipped.read(item)
            if name in seen or hashlib.sha256(payload).hexdigest() != manifest['source_sha256'].get(name):
                raise ValueError('Source member differs from its committed blob')
            seen.add(name)
            target = destination.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    if seen != set(manifest['source_sha256']):
        raise ValueError('Source archive is incomplete')
    return len(seen)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--working-tree', action='store_true', help='Validate edits to tracked files with an explicit per-file manifest; no commit is created')
    parser.add_argument('--include',action='append',default=[],help='Explicit public added file to scan and include; requires --working-tree')
    parser.add_argument('--browser', action='store_true', help='Requires existing Playwright/Chromium development tools')
    parser.add_argument('--frontend', action='store_true', help='Install the Bun lockfile and build the optional marketing page')
    parser.add_argument('--output', default='bench/results/validation/release.json')
    args = parser.parse_args()
    from tools.bundle import build
    from touchstone.metal import node_executable
    artifact = build(args.ref, working_tree=args.working_tree, extra_paths=args.include)
    manifest = json.loads((ROOT / 'dist/bundle-manifest.json').read_text(encoding='utf-8'))
    node = str(Path(node_executable()).resolve())
    npm = Path(node).parent / 'node_modules/npm/bin/npm-cli.js'
    if not npm.is_file():
        raise RuntimeError('This validation requires Node with its npm CLI')
    env = clean_environment(node)
    scratch = ROOT / 'tmp'
    scratch.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='release-validation-', dir=scratch))
    source = directory / 'source'
    count = extract_verified(ROOT / 'dist/touchstone-source.zip', manifest, source)
    logs = directory / 'logs'
    logs.mkdir()
    report = {'label': 'MEASURED', 'scope': ('TRACKED_WORKING_TREE' if args.working_tree else 'COMMITTED_SOURCE') + '_WITH_CONTROLLED_FINANCIAL_ADAPTERS',
        'commit': artifact['commit'], 'archive_sha256': artifact['sha256'], 'source_files_verified': count,
        'source_mode': artifact['source_mode'], 'changed_files': artifact['changed_files'],
        'working_tree_edits_included': args.working_tree, 'untracked_files_included': artifact['untracked_files_included'],
        'added_files': artifact['added_files'],
        'private_data_copied': False, 'credentials_forwarded': False, 'external_financial_transactions': 0,
        'node_modules_copied': False, 'tools_directory_symlinked': False,
        'platform': platform.platform(), 'python': platform.python_version(), 'stages': {},
        'logs_directory': str(logs.relative_to(ROOT)).replace('\\', '/')}

    def stage(name, command, cwd=source, timeout=600):
        path = logs / (name + '.log')
        print('Running ' + name, flush=True)
        with path.open('w', encoding='utf-8') as log:
            try:
                result = subprocess.run(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
        payload = path.read_bytes()
        report['stages'][name] = {'exit_code': code, 'log_sha256': hashlib.sha256(payload).hexdigest()}
        if code:
            raise RuntimeError(name + ' failed; inspect its local log')

    failure = None
    try:
        stage('npm-ci', [node, str(npm), 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], source / 'integrations/metal')
        stage('python-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        stage('node-tests', [node, '--test'], source / 'integrations/metal')
        for milestone in ('m1', 'm2', 'm3', 'm4', 'm5'):
            stage(milestone + '-controlled', [sys.executable, 'tools/prove_' + milestone + '.py'])
        if args.frontend:
            bun = shutil.which('bun')
            if not bun:
                raise RuntimeError('Bun is required to install the frontend lockfile')
            stage('bun-install-frozen', [bun, 'install', '--frozen-lockfile', '--ignore-scripts'], source / 'apps/web')
            stage('frontend-build', [bun, 'run', 'build'], source / 'apps/web')
        if args.browser:
            stage('procurement-evidence', [sys.executable, '-m', 'touchstone', 'procurement-evidence'])
            stage('dashboard-browser', [sys.executable, 'tools/check_dashboard.py'])
            stage('signed-mandates-browser', [sys.executable, 'tools/check_signed_mandates.py'])
            stage('motion-browser', [sys.executable, 'tools/check_dashboard_motion.py'])
            command = [sys.executable, 'tools/check_release_browser.py']
            if args.frontend:
                command.append('--include-landing')
            stage('release-browser', command)
            if args.frontend:
                stage('shared-site-browser', [sys.executable, 'tools/check_site_design.py'])
                stage('operator-workspace-browser', [sys.executable, 'tools/check_operator_workspace.py'])
        python_log = (logs / 'python-tests.log').read_text(encoding='utf-8')
        node_log = (logs / 'node-tests.log').read_text(encoding='utf-8')
        report['python_tests'] = int(re.search(r'Ran (\d+) tests', python_log).group(1))
        report['node_tests'] = int(re.search(r'# tests (\d+)', node_log).group(1))
        for name, relative in (('functional_browser', 'tmp/browser/validation.json'),
                               ('motion_browser', 'tmp/dashboard-redesign/review.json'),
                               ('release_browser', 'tmp/release-browser/review.json'),
                               ('shared_site_browser', 'tmp/site-design/report.json')):
            path = source / relative
            if path.exists():
                report[name] = json.loads(path.read_text(encoding='utf-8'))
    except (RuntimeError, OSError, ValueError) as error:
        failure = type(error).__name__
    report['passed'] = failure is None
    report['failure_type'] = failure
    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('label', 'commit', 'passed', 'failure_type', 'external_financial_transactions')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
