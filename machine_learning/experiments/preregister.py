"""Freeze the models for the prospective 2027 test (docs/PREREGISTRATION_2027.md).

Fits the exploratory `skill_exp` model of the mechanism study on the published
training + validation games (C chosen on validation, as everywhere else) and
saves it with its feature list, Elo and player-Elo settings and checksums of
every frozen artifact, so the later evaluation cannot change them.

Usage: python -m machine_learning.experiments.preregister [--processed DIR] [--raw DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import joblib
import pandas as pd

from machine_learning.experiments import harness as H
from machine_learning.experiments.lineups import lineup_table
from machine_learning.experiments.mechanisms import EXP, SKILL, build_setting
from machine_learning.experiments.player_history import lineup_groups
from machine_learning.feature_engineering.features import FEATURES

OUT = H.ROOT / "research" / "preregistration_2027"
FROZEN = ["logreg.joblib", "elo_logit.joblib", "logreg_player.joblib", "evaluation.json",
          "evaluation_logreg_player.json"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(processed: Path, raw: Path) -> dict:
    matches = pd.read_parquet(processed / "matches.parquet")
    pr = pd.read_parquet(processed / "player_rows.parquet")
    s = H.settings()[0]
    df = build_setting(s, matches, lineup_groups(pr), lineup_table(pr[["source_game_id", "team_key", "player_key",
                                                                       "match_date"]]), {}).reset_index(drop=True)
    tr, va, te = H.split_masks(df, s)
    feats = FEATURES + SKILL + EXP
    r = H.fit_select(df, feats, tr, va, te)
    trva = tr | va
    model = H.fit_lr(df.loc[trva, feats], df.loc[trva, "blue_won"], r["C"])
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "skill_exp.joblib"
    joblib.dump(model, path)
    spec = {"model": "skill_exp", "features": feats, "C": r["C"], "fit_games": int(trva.sum()),
            "elo": dict(zip(("k", "carryover_shrink", "k_league"), s.elo)),
            "player_elo": dict(zip(("k", "carryover_shrink", "k_league"), s.player_elo)),
            "feature_code": ["machine_learning/experiments/player_history.py",
                             "machine_learning/experiments/player_elo.py",
                             "machine_learning/experiments/mechanisms.py (build_setting)"],
            "main_test_brier_for_reference": float(((model.predict_proba(df.loc[te, feats])[:, 1]
                                                     - df.loc[te, "blue_won"]) ** 2).mean()),
            "data": H.data_record(raw)["fingerprint"],
            "frozen_sha256": {"research/preregistration_2027/skill_exp.joblib": sha(path),
                              **{f"{H.ARTIFACT_EVAL.parent.relative_to(H.ROOT).as_posix()}/{f}":
                                 sha(H.ARTIFACT_EVAL.parent / f) for f in FROZEN}}}
    (OUT / "frozen_models.json").write_text(json.dumps(spec, indent=1))
    return spec


def main() -> int:
    ap = argparse.ArgumentParser()
    d = Path(os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--processed", type=Path, default=d / "processed" / "oracles_elixir")
    ap.add_argument("--raw", type=Path, default=d / "raw" / "oracles_elixir")
    a = ap.parse_args()
    spec = run(a.processed, a.raw)
    print(json.dumps({k: spec[k] for k in ("C", "fit_games", "main_test_brier_for_reference")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
