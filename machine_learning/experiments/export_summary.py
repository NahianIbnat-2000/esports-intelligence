"""Export a compact, public summary of a registry record for the website.

Usage: python -m machine_learning.experiments.export_summary [record.json]
Writes frontend/public/experiments/walk-forward.json (latest walk-forward record
by default). Only aggregate metrics are exported; no game-level data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from machine_learning.experiments.registry import REGISTRY_DIR, ROOT

OUT = ROOT / "frontend" / "public" / "experiments" / "walk-forward.json"


def r(x, n=6):
    return None if x is None else round(float(x), n)


def summary(rec: dict) -> dict:
    keep = ("n", "brier", "log_loss", "accuracy", "roc_auc", "ece")
    return {
        "experiment_id": rec["experiment_id"], "created_at": rec["created_at"],
        "data_fingerprint": rec["data"]["fingerprint"], "code_sha256": rec["code_sha256"][:12],
        "git_commit": rec.get("git_commit"), "environment": rec["environment"],
        "design": {k: rec["design"][k] for k in ("test_years", "split_rule", "eligibility", "selection_metric",
                                                  "bootstrap", "lineup_note", "patch_early_days")},
        "features": rec["design"]["features"],
        "windows": [{
            "test_year": w["test_year"], "periods": w["periods"], "chosen": w["chosen"],
            "metrics": {m: {k: r(v.get(k)) if k != "n" else v.get(k) for k in keep} for m, v in w["metrics"].items()},
            "comparisons": [{"model": c["model"], "reference": c["reference"], "question": c["question"],
                             "difference": r(c["difference"], 6), "ci95_low": r(c["ci95_low"], 6),
                             "ci95_high": r(c["ci95_high"], 6)} for c in w["comparisons_brier"]],
        } for w in rec["windows"]],
        "pooled": {
            "n": rec["pooled"]["n"],
            "metrics": {m: {k: r(v.get(k)) if k != "n" else v.get(k) for k in keep}
                        for m, v in rec["pooled"]["metrics"].items()},
            "comparisons": [{"model": c["model"], "reference": c["reference"], "question": c["question"],
                             **{f"{met}_{k}": r(c[met][k], 6) for met in ("brier", "log_loss")
                                for k in ("difference", "ci95_low", "ci95_high")},
                             "windows_better": c["windows_better"], "windows_ci_below_zero": c["windows_ci_below_zero"],
                             "window_sd": r(c["window_sd"], 6)} for c in rec["pooled"]["comparisons"]],
        },
        "patch_analysis": [{"group": p["group"], "n": p["n"], "elo_cal_brier": r(p["elo_cal"]["brier"]),
                            "all_brier": r(p["all"]["brier"]),
                            "difference": r(p["all_vs_elo_cal_brier"]["difference"], 6),
                            "ci95_low": r(p["all_vs_elo_cal_brier"]["ci95_low"], 6),
                            "ci95_high": r(p["all_vs_elo_cal_brier"]["ci95_high"], 6)} for p in rec["patch_analysis"]],
    }


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(REGISTRY_DIR.glob("walk-forward-*.json"))[-1]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary(json.loads(path.read_text())), indent=1))
    print(OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
