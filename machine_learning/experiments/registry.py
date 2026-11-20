"""Lightweight experiment registry: one JSON file per run.

Each record stores what is needed to reproduce and audit a result: data
checksum (from the raw-file manifest), code checksum (SHA-256 of the
machine_learning package sources) and git commit when available, package
versions, seed, full configuration, periods and metrics.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = Path(__file__).resolve().parent / "registry"
PACKAGES = ("numpy", "pandas", "scikit-learn", "scipy")


def data_checksum(manifest_path: Path) -> dict:
    files = json.loads(manifest_path.read_text())["files"]
    digest = hashlib.sha256("".join(sorted(f["sha256"] for f in files)).encode()).hexdigest()
    return {"sha256": digest, "fingerprint": digest[:10], "n_files": len(files),
            "files": [{"filename": f["filename"], "sha256": f["sha256"]} for f in files]}


def code_checksum() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "machine_learning").rglob("*.py")):
        h.update(p.relative_to(ROOT).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip() or None
    except Exception:
        return None


def environment() -> dict:
    versions = {}
    for p in PACKAGES:
        try:
            versions[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            versions[p] = None
    return {"python": platform.python_version(), "packages": versions}


def save(record: dict, kind: str) -> Path:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC)
    exp_id = f"{kind}-{stamp:%Y%m%d-%H%M%S}-{record['data']['fingerprint']}"
    record = {"experiment_id": exp_id, "kind": kind, "created_at": stamp.isoformat(),
              "code_sha256": code_checksum(), "git_commit": git_commit(), "environment": environment(),
              **record}
    path = REGISTRY_DIR / f"{exp_id}.json"
    path.write_text(json.dumps(record, indent=1, default=str))
    return path
