"""Fetch a pinned official llama.cpp build and publisher-hosted GGUF; verify hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent


def metadata(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Touchstone-builder"}), timeout=40) as r:
        return json.load(r)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, target, expected, size=None, parallel=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and digest(target) == expected:
        print("Verified cached " + target.name, flush=True)
        return
    partial = target.with_suffix(target.suffix + ".partial")
    print("Downloading " + target.name, flush=True)
    if parallel and size:
        parts = target.with_suffix(target.suffix + ".parts")
        parts.mkdir(exist_ok=True)
        width = 256 * 1024
        count = (size + width - 1) // width
        def piece(index):
            start, end = index * width, min(size, (index + 1) * width) - 1
            dest = parts / str(index)
            if dest.exists() and dest.stat().st_size == end - start + 1:
                return
            for attempt in range(4):
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "Touchstone-builder", "Range": f"bytes={start}-{end}"})
                    with urllib.request.urlopen(request, timeout=45) as response:
                        if response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {start}-{end}/"):
                            raise RuntimeError("Download server did not honor the requested byte range")
                        dest.write_bytes(response.read())
                    break
                except (OSError, TimeoutError):
                    if attempt == 3:
                        raise
                    time.sleep(1)
            if dest.stat().st_size != end - start + 1:
                raise RuntimeError("Incomplete download segment")
        with ThreadPoolExecutor(max_workers=16) as pool:
            pending = [pool.submit(piece, i) for i in range(count)]
            for completed, result in enumerate(as_completed(pending), 1):
                result.result()
                if completed % 20 == 0 or completed == count:
                    print(f"  {completed * 100 // count}% ({completed}/{count} segments)", flush=True)
        with partial.open("wb") as out:
            for index in range(count):
                out.write((parts / str(index)).read_bytes())
    else:
      with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Touchstone-builder"}), timeout=60) as r, partial.open("wb") as out:
        total, written, reported = int(r.headers.get("Content-Length", 0)), 0, -1
        while chunk := r.read(512 * 1024):
            out.write(chunk)
            written += len(chunk)
            progress = written * 10 // total if total else -1
            if progress > reported:
                print(f"  {progress * 10}%", flush=True)
                reported = progress
    if digest(partial) != expected:
        raise RuntimeError("Download checksum mismatch: " + target.name)
    partial.replace(target)


def setup(tier):
    build = "b12000"
    release = metadata(f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{build}")
    asset = next(a for a in release["assets"] if a["name"] == f"llama-{build}-bin-win-vulkan-x64.zip")
    runtime = ROOT / ".tools/llama" / build
    archive = runtime / asset["name"]
    download(asset["browser_download_url"], archive, asset["digest"].removeprefix("sha256:"), asset["size"], parallel=True)
    if not (runtime / "llama-server.exe").exists():
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if not (runtime / entry.filename).resolve().is_relative_to(runtime.resolve()):
                    raise ValueError("Unsafe runtime archive entry")
            z.extractall(runtime)
    size = "0.5B" if tier == "economy" else "1.5B"
    repository = f"Qwen/Qwen2.5-{size}-Instruct-GGUF"
    model_info = metadata("https://huggingface.co/api/models/" + repository + "?blobs=true")
    filename = f"qwen2.5-{size.lower()}-instruct-q4_k_m.gguf"
    sibling = next(s for s in model_info["siblings"] if s["rfilename"] == filename)
    sha = sibling["lfs"]["sha256"]
    revision = model_info["sha"]
    source = f"https://huggingface.co/{repository}/resolve/{revision}/{filename}"
    model = ROOT / ".tools/models" / filename
    download(source, model, sha)
    license_target = model.with_suffix(".LICENSE.txt")
    if not license_target.exists():
        with urllib.request.urlopen(f"https://huggingface.co/{repository}/resolve/{revision}/LICENSE", timeout=30) as r:
            license_target.write_bytes(r.read())
    manifest = {"tier": tier, "runtime_release": build, "backend": "Vulkan", "runtime_archive_sha256": asset["digest"].removeprefix("sha256:"),
                "executable": str(runtime / "llama-server.exe"), "model_path": str(model), "model": repository,
                "model_revision": revision, "model_sha256": sha, "quantization": "Q4_K_M",
                "model_source": source, "license": model_info.get("cardData", {}).get("license", "See saved LICENSE"),
                "context_tokens": 2048, "parallel_slots": 1}
    target = ROOT / ".tools/models" / f"{tier}-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Ready: " + str(target), flush=True)
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--tier", choices=["economy", "balanced"], default="economy")
    setup(p.parse_args().tier)
