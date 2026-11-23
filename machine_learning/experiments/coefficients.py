"""Coefficient table of the deployed player model, with bootstrap intervals.

Reproduces Table 4 of the case study (docs/case-study): the logistic model
`logreg_player` refit on the published training + validation games with the
published C, its standardised coefficients and odds ratios, and 95% intervals
from re-drawing whole series (percentile bootstrap, N_BOOT draws, fixed seed).
Also stores the scale facts quoted in the text: the SD of each input, the
median lineup's typical number of earlier games, and the predicted blue-side
win chance for otherwise equal teams at 0 and +1 SD of player experience.

Usage: python -m machine_learning.experiments.coefficients [--processed DIR] [--raw DIR]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from machine_learning.experiments import harness as H
from machine_learning.experiments import registry
from machine_learning.training.player_model import PLAYER_FEATURES, add_player_feature, rebuild_published

N_BOOT, SEED = 200, 0
log = logging.getLogger("ml.coefficients")


def run(processed: Path, raw: Path) -> dict:
    df, ev = rebuild_published(processed, H.ARTIFACT_EVAL)
    players = pd.read_parquet(processed / "player_rows.parquet",
                              columns=["source_game_id", "team_key", "player_key", "match_date"])
    df = add_player_feature(df, players)
    saved = json.loads((H.ARTIFACT_EVAL.parent / "evaluation_logreg_player.json").read_text())
    C = saved["best_C"]
    tv = df[df["split"].isin(["train", "validation"])].reset_index(drop=True)
    from machine_learning.training.train import series_key
    tv["series"] = series_key(tv)
    X, y = tv[PLAYER_FEATURES], tv["blue_won"]
    model = H.fit_lr(X, y, C)
    coef = model.named_steps["lr"].coef_[0]
    check = max(abs(c - s["coef_per_sd"]) for c, s in zip(coef, saved["coefficients"]))
    if check > 1e-6:
        raise RuntimeError(f"refit differs from the saved player model by {check}")
    codes, uniq = pd.factorize(tv["series"])
    groups = [np.where(codes == k)[0] for k in range(len(uniq))]
    rng = np.random.default_rng(SEED)
    boots = np.empty((N_BOOT, len(PLAYER_FEATURES)))
    for b in range(N_BOOT):
        pick = np.concatenate([groups[k] for k in rng.integers(0, len(groups), len(groups))])
        boots[b] = H.fit_lr(X.iloc[pick], y.iloc[pick], C).named_steps["lr"].coef_[0]
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    sd = X.std(ddof=0)
    lr = model.named_steps["lr"]
    # median lineup's typical player: exp(median of per-team player_exp_prev) - 1
    per_team = pd.concat([tv["blue_player_exp_prev"], tv["red_player_exp_prev"]]).dropna()
    typical_games = float(np.expm1(per_team.median()))
    # equal teams except +1 SD of player experience: all other standardised inputs at 0 means
    # the raw value equal to the training mean; with diffs, "equal" is raw 0, which is not the mean.
    sc = model.named_steps["s"]
    x0 = np.zeros((1, len(PLAYER_FEATURES)))
    x1 = x0.copy()
    j = PLAYER_FEATURES.index("player_exp_prev_diff")
    x1[0, j] = sd.iloc[j]
    p0 = float(model.predict_proba(pd.DataFrame(x0, columns=PLAYER_FEATURES))[:, 1][0])
    p1 = float(model.predict_proba(pd.DataFrame(x1, columns=PLAYER_FEATURES))[:, 1][0])
    rows = [{"feature": f, "sd": float(sd.iloc[i]), "coef_per_sd": float(coef[i]), "odds_ratio": float(np.exp(coef[i])),
             "coef_ci95": [float(lo[i]), float(hi[i])], "odds_ratio_ci95": [float(np.exp(lo[i])), float(np.exp(hi[i]))]}
            for i, f in enumerate(PLAYER_FEATURES)]
    return {"data": H.data_record(raw),
            "design": {"model": "logreg_player", "C": C, "n_fit": int(len(tv)), "n_boot": N_BOOT, "seed": SEED,
                       "unit": "series (tournament, team pair, UTC day)", "intervals": "percentile"},
            "coefficients": rows, "intercept": float(lr.intercept_[0]),
            "scale_facts": {"median_lineup_typical_earlier_games": typical_games,
                            "p_blue_equal_teams": p0, "p_blue_plus_1sd_player_experience": p1,
                            "refit_matches_saved_model_max_abs_diff": float(check)}}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    d = Path(os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--processed", type=Path, default=d / "processed" / "oracles_elixir")
    ap.add_argument("--raw", type=Path, default=d / "raw" / "oracles_elixir")
    a = ap.parse_args()
    print(registry.save(run(a.processed, a.raw), "coefficients"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
