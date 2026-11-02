"""Scan every blob in git history (and the working tree's tracked/untracked files)
for secret-shaped strings. Findings are REDACTED: only path, commit, rule and the
match length are printed, never the matched text.

    python tools/scan_secrets.py            # history + working tree, exit 1 on findings
    python tools/scan_secrets.py --json     # machine-readable summary

Heuristic, not a substitute for a dedicated scanner, but it needs no dependencies.
Known-public identifiers (transaction hashes, receipts) are not flagged unless they
sit next to a key-like label.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_BLOB = 2_000_000
PLACEHOLDER = re.compile(r"[<>{}\[\]]|your|example|placeholder|changeme|xxxx|\.\.\.|redacted|\$\{|\$env", re.I)
LABEL = r"(?:api[_-]?key|client[_-]?secret|secret|token|private[_-]?key|password|passwd|authorization|bearer)"

RULES = [
    ("pem-private-key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{30,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
    ("labelled-hex-key", re.compile(rf"(?i){LABEL}[\"']?[ \t]*[:=][ \t]*[\"']?(?:0x)?[0-9a-f]{{64}}\b")),
    ("labelled-long-secret", re.compile(rf"(?i){LABEL}[\"']?[ \t]*[:=][ \t]*[\"']?[A-Za-z0-9_\-+/=]{{24,}}")),
    ("url-embedded-credential", re.compile(r"https?://[^\s/:@\"']+:[^\s/@\"']{6,}@")),
    ("url-long-path-token", re.compile(r"https?://[^\s\"'<>]*/(?:v\d+/)?[A-Za-z0-9_\-]{32,}(?=[\s\"'<>?]|$)")),
    ("airwallex-env-assignment", re.compile(r"AIRWALLEX_(?:API_KEY|CLIENT_ID)[ \t]*[=:][ \t]*[\"']?[A-Za-z0-9_\-]{16,}")),
]
# Allow-list: identifiers that are public by design (tx hashes in evidence docs).
PATH_SKIP = re.compile(r"(?:^|/)(?:package-lock\.json|node_modules/)")


def git(*args, binary=False):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout
    return out if binary else out.decode("utf-8", "replace")


def scan_text(text):
    hits = []
    for name, rx in RULES:
        for match in rx.finditer(text):
            span = match.group(0)
            if name in ("labelled-long-secret", "airwallex-env-assignment", "url-long-path-token") and PLACEHOLDER.search(span):
                continue
            if name == "url-long-path-token" and re.match(r"https?://(?:127\.0\.0\.1|localhost)[:/]", span):
                continue  # loopback seller URL + public task digest
            if name == "url-long-path-token" and re.search(r"/(?:blob|tree|commit|raw|releases|docs|api)/", span):
                continue
            hits.append((name, len(span)))
    return hits


def history_blobs():
    """Yield (blob_sha, [paths], first_commit) for every blob reachable from any ref."""
    seen = {}
    for line in git("rev-list", "--objects", "--all").splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            seen.setdefault(parts[0], []).append(parts[1])
    check = subprocess.run(["git", "cat-file", "--batch-check"], cwd=ROOT, input="\n".join(seen).encode(),
                           capture_output=True, check=True).stdout.decode().splitlines()
    for row in check:
        sha, kind, size = row.split()
        if kind == "blob" and int(size) <= MAX_BLOB:
            yield sha, seen[sha]


def main():
    findings = []
    scanned = 0
    for sha, paths in history_blobs():
        path = paths[0]
        if PATH_SKIP.search(path):
            continue
        data = git("cat-file", "-p", sha, binary=True)
        if b"\0" in data[:4096]:
            continue
        scanned += 1
        for rule, length in scan_text(data.decode("utf-8", "replace")):
            commits = git("log", "--all", "--format=%h", "--", path).split()
            findings.append({"scope": "history", "path": path, "blob": sha[:10], "rule": rule,
                             "match_length": length, "commits": commits[:5]})
    # working tree (includes untracked, excludes ignored)
    tracked = git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    for rel in tracked:
        p = ROOT / rel
        if PATH_SKIP.search(rel) or not p.is_file() or p.stat().st_size > MAX_BLOB:
            continue
        data = p.read_bytes()
        if b"\0" in data[:4096]:
            continue
        scanned += 1
        for rule, length in scan_text(data.decode("utf-8", "replace")):
            findings.append({"scope": "working-tree", "path": rel, "rule": rule, "match_length": length})
    # sensitive paths that must never be committed
    sensitive = [p for p in set(git("log", "--all", "--name-only", "--pretty=format:").splitlines())
                 if re.search(r"(?:^|/)(?:data/|\.env(?!\.example)|.*wallet.*\.json$|local-config)", p)]
    summary = {"blobs_scanned": scanned, "findings": findings, "sensitive_paths_in_history": sorted(sensitive)}
    if "--json" in sys.argv:
        print(json.dumps(summary, indent=2))
    else:
        print(f"scanned {scanned} text blobs/files")
        for f in findings:
            print(f"  [{f['scope']}] {f['path']} rule={f['rule']} len={f['match_length']}")
        for p in summary["sensitive_paths_in_history"]:
            print(f"  [sensitive-path] {p}")
        print("FINDINGS" if findings or sensitive else "clean")
    return 1 if findings or sensitive else 0


if __name__ == "__main__":
    raise SystemExit(main())
