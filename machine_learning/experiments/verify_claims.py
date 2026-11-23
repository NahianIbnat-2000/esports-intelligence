"""Check that published numbers match the artifacts that produced them.

Reads research/claims.json. For each claim, looks up the value in its source
artifact (JSON path with optional [key=value] selectors), formats it, and
checks that the formatted text appears in every listed file. LaTeX minus
signs ($-$, \\textminus) and Unicode minus are normalised before matching.

Also verifies research/release_manifest.json if present: every listed repo
file must still have the recorded SHA-256.

Usage:  python -m machine_learning.experiments.verify_claims [--quiet]
Exit code 1 when any claim or checksum fails.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ROOT / "research" / "claims.json"
MANIFEST = ROOT / "research" / "release_manifest.json"


def lookup(obj, path: str):
    for part in re.findall(r"[^.\[\]]+(?:\[[^\]]+\])?", path):
        m = re.match(r"([^\[]+)(?:\[([^\]]+)\])?$", part)
        key, sel = m.group(1), m.group(2)
        obj = obj[key]
        if sel:
            conds = dict(c.split("=", 1) for c in sel.split(","))
            obj = next(x for x in obj if all(str(x.get(k)) == v for k, v in conds.items()))
    return obj


def normalise(text: str) -> str:
    text = text.replace("$-$", "-").replace("\\textminus{}", "-").replace("\\textminus", "-").replace("−", "-")
    return text.replace("{,}", ",")


def render(claim: dict, value) -> str:
    fmt = claim["format"]
    vals = value if isinstance(value, list) else [value]
    vals = [v * claim.get("scale", 1) for v in vals]
    if not claim.get("keep_sign"):
        vals = [abs(v) for v in vals]
    return fmt.format(*vals)


def check_claims(root: Path = ROOT) -> list[dict]:
    spec = json.loads((root / "research" / "claims.json").read_text())
    sources = {k: json.loads((root / v).read_text()) for k, v in spec["sources"].items()}
    files = spec.get("files", {})
    texts: dict[str, str] = {}
    out = []
    for c in spec["claims"]:
        if "sum" in c:
            value = sum(lookup(sources[s], p) for s, p in c["sum"])
        else:
            value = lookup(sources[c["ref"][0]], c["ref"][1])
        expected = render(c, value)
        missing = []
        for f in c["in"]:
            path = files.get(f, f)
            if path not in texts:
                texts[path] = normalise((root / path).read_text(encoding="utf-8"))
            if expected not in texts[path]:
                missing.append(path)
        out.append({"id": c["id"], "expected": expected, "ok": not missing, "missing_in": missing})
    return out


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_manifest(root: Path = ROOT) -> list[dict]:
    p = root / "research" / "release_manifest.json"
    if not p.exists():
        return []
    m = json.loads(p.read_text())
    out = []
    for group in ("artifacts", "experiment_records", "publications", "code"):
        for f in m.get(group, []):
            actual = sha256(root / f["path"]) if (root / f["path"]).exists() else None
            out.append({"path": f["path"], "ok": actual == f["sha256"], "actual": actual})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    claims = check_claims()
    manifest = check_manifest()
    bad = [c for c in claims if not c["ok"]] + [m for m in manifest if not m["ok"]]
    if not a.quiet:
        for c in claims:
            print(f"{'ok  ' if c['ok'] else 'FAIL'} {c['id']:24s} {c['expected']:22s} "
                  + ("" if c["ok"] else "missing in " + ", ".join(c["missing_in"])))
        for m in manifest:
            if not m["ok"]:
                print(f"FAIL checksum {m['path']}")
        print(f"{len(claims) - sum(not c['ok'] for c in claims)}/{len(claims)} claims ok; "
              f"{len(manifest) - sum(not m['ok'] for m in manifest)}/{len(manifest)} manifest checksums ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
