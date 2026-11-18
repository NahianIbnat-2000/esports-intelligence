"""Step 1: acquire source files and preserve them unchanged.

Oracle's Elixir publishes yearly CSV files through a Google Drive folder
linked from https://oracleselixir.com/tools/downloads. Google Drive download
links are not stable for scripted access, so the supported route is:

  1. Download the yearly CSV files manually from the page above.
  2. Run:  python -m pipelines.oracle_elixir.run --import path/to/file.csv ...

`--url` is also supported for a direct file URL you have verified.

Files are copied into data/raw/oracles_elixir/ and recorded in
manifest.json with their SHA-256 hash, original location and collection time.
An existing raw file is never overwritten: a file with the same name but
different content is stored under a new name.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pipelines.oracle_elixir.config import RAW_DIR, ensure_dirs

MANIFEST = RAW_DIR / "manifest.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"files": []}


def _save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=2))


def _register(dest: Path, original_location: str) -> dict:
    m = load_manifest()
    digest = sha256_of(dest)
    for entry in m["files"]:
        if entry["sha256"] == digest:
            return entry
    entry = {"filename": dest.name, "sha256": digest, "size_bytes": dest.stat().st_size,
             "original_location": original_location,
             "collected_at": datetime.now(UTC).isoformat()}
    m["files"].append(entry)
    _save_manifest(m)
    return entry


def import_local_file(src: str | Path) -> dict:
    """Copy a manually downloaded file into the raw directory (no changes)."""
    ensure_dirs()
    src = Path(src).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(src)
    digest = sha256_of(src)
    for entry in load_manifest()["files"]:
        if entry["sha256"] == digest and (RAW_DIR / entry["filename"]).exists():
            return entry  # already preserved
    if src.parent == RAW_DIR.resolve():
        # The file was placed directly in the raw folder (e.g. to save disk
        # space): register it where it is, without making a second copy.
        return _register(src, original_location=f"placed in raw folder: {src.name}")
    dest = RAW_DIR / src.name
    if dest.exists():
        dest = RAW_DIR / f"{src.stem}__{digest[:8]}{src.suffix}"
    shutil.copy2(src, dest)
    return _register(dest, original_location=f"local import: {src.name}")


def download_url(url: str, filename: str, timeout: float = 120.0) -> dict:
    """Download a verified direct file URL into the raw directory."""
    ensure_dirs()
    tmp = RAW_DIR / f".{filename}.part"
    with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    digest = sha256_of(tmp)
    for entry in load_manifest()["files"]:
        if entry["sha256"] == digest:
            tmp.unlink()
            return entry
    dest = RAW_DIR / filename
    if dest.exists():
        dest = RAW_DIR / f"{Path(filename).stem}__{digest[:8]}{Path(filename).suffix}"
    tmp.rename(dest)
    return _register(dest, original_location=url)


def registered_files() -> list[dict]:
    """Manifest entries whose files are present on disk."""
    return [e for e in load_manifest()["files"] if (RAW_DIR / e["filename"]).exists()]
