"""Portable Node launcher; no PowerShell policy or machine PATH changes needed."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from touchstone.config import load_local
args = sys.argv[1:] or ["inspect"]
if args[0] in {'deposit', 'withdraw', 'pay', 'recover'} and '--execute' not in args:
    raise SystemExit('Money movement requires --execute and written approval with a stated cap')
if args[0] not in {"test", "install"}:
    load_local()
manifest = ROOT / ".tools/node/manifest.json"
node = json.loads(manifest.read_text())["executable"] if manifest.exists() else shutil.which("node")
if not node:
    raise SystemExit("Install portable Node first: python tools/setup_node.py")
directory = ROOT / "integrations/metal"
if args[0] == "test":
    command = [node, "--test", *[str(p) for p in sorted(directory.glob("*.test.mjs"))]]
elif args[0] == "install":
    command = [node, str(Path(node).parent / "node_modules/npm/bin/npm-cli.js"), "ci", "--ignore-scripts", "--no-fund"]
elif args[0] == "wallet":
    command = [node, str(directory / "funding.mjs")]
elif args[0] == "provider":
    command = [node, str(directory / "provider.mjs")]
else:
    command = [node, str(directory / "cli.mjs"), *args]
child_env = os.environ.copy()
if args[0] == 'provider':
    for key in list(child_env):
        if key == 'AGENT_PRIVATE_KEY' or key.startswith('AIRWALLEX_'):
            child_env.pop(key)
    child_env['TOUCHSTONE_PYTHON'] = sys.executable
raise SystemExit(subprocess.call(command, cwd=directory, env=child_env))
