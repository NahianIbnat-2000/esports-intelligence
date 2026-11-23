"""Write research/release_manifest.json: one record linking the data, model
artifacts, experiment records, paper and website data of a research release.

Checked files (SHA-256 verified by verify_claims and by the test suite):
  artifacts           model artifacts of the published model version
  experiment_records  every JSON record in machine_learning/experiments/registry
  publications        case-study PDF and LaTeX source, claims registry, the
                      experiment summary the website reads
Recorded only (not checked, they change with every edit): git commit at
generation time, code checksum, environment.

Usage: python -m machine_learning.experiments.manifest [--release NAME] [--paper-version TEXT]
Regenerate after changing any checked file, then commit the manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from machine_learning.experiments import registry

ROOT = Path(__file__).resolve().parents[2]
VERSION_DIR = "machine_learning/models/artifacts/1.0.0+c8b6f8e19c"
PUBLICATIONS = ["docs/case-study/Esports_Intelligence_Case_Study_Nahian_Ibnat.pdf",
                "docs/case-study/Esports_Intelligence_Case_Study.tex",
                "research/claims.json",
                "frontend/public/experiments/walk-forward.json"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def entry(p: Path) -> dict:
    return {"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size}


def build(release: str, paper_version: str) -> dict:
    ev = json.loads((ROOT / VERSION_DIR / "evaluation.json").read_text())
    records = sorted(registry.REGISTRY_DIR.glob("*.json"))
    wf = json.loads(next(r for r in reversed(records) if r.name.startswith("walk-forward")).read_text())
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    return {
        "release": release,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit_at_generation": registry.git_commit(),
        "data": {"source": "Oracle's Elixir match data CSVs (downloaded manually; not redistributed)",
                 "fingerprint": wf["data"]["fingerprint"], "sha256_of_file_hashes": wf["data"]["sha256"],
                 "files": wf["data"]["files"]},
        "model_version": ev["version"],
        "evaluation_periods": {k: ev["split"][k] for k in ("train", "validation", "test")},
        "artifacts": [entry(p) for p in sorted((ROOT / VERSION_DIR).iterdir()) if p.is_file()]
        + [entry(p) for p in sorted((ROOT / "research" / "preregistration_2027").glob("*"))
           if p.is_file() and p.name != "result.json"],
        "experiment_records": [{**entry(p), "kind": json.loads(p.read_text()).get("kind")} for p in records],
        "publications": [entry(ROOT / p) for p in PUBLICATIONS if (ROOT / p).exists()],
        "paper_version": paper_version,
        "website": {"frontend_package_version": pkg.get("version"),
                    "live": "https://esports-intelligence.vercel.app",
                    "article": "https://nahianibnat-2000.github.io/esports-intelligence/"},
        "code_sha256": registry.code_checksum(),
        "requirements_sha256": sha(ROOT / "requirements.txt"),
        "environment_at_generation": registry.environment(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", default="research-2026-11-23")
    ap.add_argument("--paper-version", default="case study, 17 pages, revised 23 November 2026")
    a = ap.parse_args(argv)
    out = ROOT / "research" / "release_manifest.json"
    out.write_text(json.dumps(build(a.release, a.paper_version), indent=1))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
