"""Prospective (pre-registered) evaluation on games played after the data cutoff.
Plan: docs/PREREGISTRATION_2027.md. Written and frozen before any of those games existed.

Steps:
1. Verify the SHA-256 of every frozen artifact (research/preregistration_2027/frozen_models.json).
   Stop if any file changed.
2. Replay Elo (published settings) and player Elo over ALL games in the new processed data;
   ratings update as games are played, as in the published design. Model coefficients stay frozen.
3. Evaluation games: match_date > CUTOFF and <= --end, both teams with at least 5 earlier games.
4. Score: Brier, log loss, accuracy per model; paired series-bootstrap differences (2,000 draws,
   seed 0) for the pre-registered comparisons; tournament clusters as a sensitivity check.

Usage: python -m machine_learning.experiments.prospective --processed DIR --raw DIR [--end YYYY-MM-DD]
       [--cutoff ISO] (only change --cutoff for a software dry run on old data; such a run is NOT a result)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from machine_learning.data_preparation.splits import SplitConfig
from machine_learning.elo.elo import expected_score
from machine_learning.experiments import harness as H
from machine_learning.experiments.lineups import add_roster_diffs, lineup_table, roster_features
from machine_learning.experiments.mechanisms import build_setting
from machine_learning.experiments.player_history import lineup_groups
from machine_learning.feature_engineering.features import FEATURES

PRE = H.ROOT / "research" / "preregistration_2027"
CUTOFF = "2026-11-17T19:42:11+00:00"         # last game in the data used for the study
MIN_GAMES_PRIMARY = 3000
COMPARISONS = [("logreg_player", "logreg", "P1"), ("logreg", "elo_logit", "P2"),
               ("skill_exp", "logreg_player", "S1")]


def verify_frozen() -> dict:
    spec = json.loads((PRE / "frozen_models.json").read_text())
    bad = [p for p, h in spec["frozen_sha256"].items()
           if hashlib.sha256((H.ROOT / p).read_bytes()).hexdigest() != h]
    if bad:
        raise RuntimeError(f"frozen artifacts changed, evaluation is not valid: {bad}")
    return spec


def run(processed: Path, raw: Path, cutoff: str, end: str | None) -> dict:
    spec = verify_frozen()
    art = H.ARTIFACT_EVAL.parent
    models = {k: joblib.load(art / f"{k}.joblib") for k in ("logreg", "elo_logit", "logreg_player")}
    models["skill_exp"] = joblib.load(PRE / "skill_exp.joblib")
    matches = pd.read_parquet(processed / "matches.parquet")
    pr = pd.read_parquet(processed / "player_rows.parquet")
    s = H.settings()[0]
    df = build_setting(s, matches, lineup_groups(pr),
                       lineup_table(pr[["source_game_id", "team_key", "player_key", "match_date"]]), {})
    df = add_roster_diffs(df, roster_features(lineup_table(pr[["source_game_id", "team_key", "player_key",
                                                               "match_date"]]))).reset_index(drop=True)
    t0 = pd.Timestamp(cutoff)
    mask = (df["match_date"] > t0) & (df["min_prior_games"] >= SplitConfig().min_prior_games)
    if end:
        mask &= df["match_date"] <= pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    t = df[mask].reset_index(drop=True)
    if t.empty:
        return {"status": "no eligible games after the cutoff", "cutoff": cutoff}
    P = {"elo": expected_score(t["blue_elo_pre"], t["red_elo_pre"]).to_numpy(),
         "elo_logit": models["elo_logit"].predict_proba(t[["elo_diff"]])[:, 1],
         "logreg": models["logreg"].predict_proba(t[FEATURES])[:, 1],
         "logreg_player": models["logreg_player"].predict_proba(t[FEATURES + ["player_exp_prev_diff"]])[:, 1],
         "skill_exp": models["skill_exp"].predict_proba(t[spec["features"]])[:, 1]}
    y = t["blue_won"].to_numpy()
    out = {"status": "ok", "cutoff": cutoff, "end": end, "n_games": int(len(t)),
           "period": [str(t["match_date"].min()), str(t["match_date"].max())],
           "enough_games_for_primary": bool(len(t) >= MIN_GAMES_PRIMARY),
           "metrics": {k: H.summarise(y, p) for k, p in P.items()}, "comparisons": []}
    for a, b, tag in COMPARISONS:
        out["comparisons"].append({"id": tag, "model": a, "reference": b,
                                   "series": H.compare(y, P[a], P[b], t["series"].to_numpy()),
                                   "tournament": H.compare(y, P[a], P[b], t["tournament_key"].astype(str).to_numpy()),
                                   "log_loss_series": H.compare(y, P[a], P[b], t["series"].to_numpy(), "log_loss")})
    for c in out["comparisons"]:
        hi = c["series"]["ci95_high"]
        c["supported"] = bool(hi < 0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    d = Path(os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--processed", type=Path, default=d / "processed" / "oracles_elixir")
    ap.add_argument("--raw", type=Path, default=d / "raw" / "oracles_elixir")
    ap.add_argument("--cutoff", default=CUTOFF)
    ap.add_argument("--end", default=None)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    res = run(a.processed, a.raw, a.cutoff, a.end)
    res["dry_run"] = a.cutoff != CUTOFF
    text = json.dumps(res, indent=1, default=str)
    if a.out:
        a.out.write_text(text)
    print(text[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
