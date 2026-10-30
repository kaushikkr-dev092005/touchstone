"""Install portable Node 22 from nodejs.org, verifying its published SHA-256."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

root = Path(__file__).resolve().parent.parent / ".tools" / "node"
root.mkdir(parents=True, exist_ok=True)
with urllib.request.urlopen("https://nodejs.org/dist/index.json", timeout=30) as response:
    releases = json.load(response)
release = next(r for r in releases if r["version"].startswith("v22.") and "win-x64-zip" in r["files"])
version = release["version"]
filename = f"node-{version}-win-x64.zip"
base = f"https://nodejs.org/dist/{version}/"
with urllib.request.urlopen(base + "SHASUMS256.txt", timeout=30) as response:
    hashes = dict((line.split()[1], line.split()[0]) for line in response.read().decode().splitlines())
archive = root / filename
if not archive.exists():
    urllib.request.urlretrieve(base + filename, archive)
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
if digest != hashes[filename]:
    raise RuntimeError("Node archive checksum mismatch")
with zipfile.ZipFile(archive) as z:
    for member in z.infolist():
        target = (root / member.filename).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError("Unsafe archive path")
    z.extractall(root)
manifest = {"version": version, "archive_sha256": digest, "source": base + filename,
            "executable": str(root / f"node-{version}-win-x64" / "node.exe")}
(root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
