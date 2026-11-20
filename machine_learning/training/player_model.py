"""Pre-match player model: the published logistic model plus one feature,
player_exp_prev_diff (see machine_learning/experiments/lineups.py).

Why this one feature: in the walk-forward study (docs/EXPERIMENTS.md) it gave
most of the pre-match gain (-0.0044 of -0.0053 Brier over the form model),
needs no knowledge of today's lineup, and can be computed at prediction time
with two small queries. Player-level Elo added a further, smaller gain but
needs a stored player-rating history; it is left for a later version.

The model uses the same Elo configuration, the same date split and the same C
grid as the published models, so its test games are exactly the published
test games and the comparison is paired.

Two ways to run it:
- inside a full retrain (train.py calls `fit_player_model`), or
- as an add-on to an existing trained model version, without touching Elo
  ratings or the other models:
      python -m machine_learning.training.player_model
  This reads the saved evaluation.json for the Elo configuration, rebuilds the
  same split, fits the model, saves logreg_player.joblib next to the other
  artifacts and writes one model version and its validation/test predictions to
  the database at DATABASE_URL (replacing an earlier logreg_player, if any).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from machine_learning.evaluation import metrics as M
from machine_learning.experiments.lineups import PREMATCH_FEATURE, add_roster_diffs, lineup_table, roster_features
from machine_learning.feature_engineering.features import FEATURES

log = logging.getLogger("ml.player_model")

MODEL_KEY = "logreg_player"
DISPLAY_NAME = "Logistic + player experience (pre-match)"
PLAYER_FEATURES = FEATURES + ["player_exp_prev_diff"]


def add_player_feature(df: pd.DataFrame, player_rows: pd.DataFrame) -> pd.DataFrame:
    feats = roster_features(lineup_table(player_rows))
    out = add_roster_diffs(df, feats)
    return out.drop(columns=[c for c in out.columns if c.startswith(("blue_continuity", "red_continuity",
                                                                     "blue_tenure", "red_tenure"))])


def fit_player_model(df: pd.DataFrame, c_grid: list[float]) -> dict:
    """df: feature matrix with `split` and player_exp_prev_diff. Returns the fitted model,
    chosen C, validation/test probabilities and test metrics."""
    from machine_learning.training.train import fit_logreg, series_key
    tr, va, te = (df[df["split"] == s] for s in ("train", "validation", "test"))
    c_scores = []
    for C in c_grid:
        p = fit_logreg(tr[PLAYER_FEATURES], tr["blue_won"], C).predict_proba(va[PLAYER_FEATURES])[:, 1]
        c_scores.append({"C": C, "validation_log_loss": M.summary(va["blue_won"], p)["log_loss"]})
    best_C = min(c_scores, key=lambda r: r["validation_log_loss"])["C"]
    p_val = fit_logreg(tr[PLAYER_FEATURES], tr["blue_won"], best_C).predict_proba(va[PLAYER_FEATURES])[:, 1]
    tv = pd.concat([tr, va])
    model = fit_logreg(tv[PLAYER_FEATURES], tv["blue_won"], best_C)
    p_test = model.predict_proba(te[PLAYER_FEATURES])[:, 1]
    lr = model.named_steps["lr"]
    y = te["blue_won"].to_numpy()
    out = {"model": model, "best_C": best_C, "C_grid": c_scores,
           "p_validation": pd.Series(p_val, index=va.index), "p_test": pd.Series(p_test, index=te.index),
           "test": M.summary(y, p_test), "validation": M.summary(va["blue_won"], p_val),
           "calibration": M.calibration_table(y, p_test), "roc": M.roc_points(y, p_test),
           "confusion": M.confusion(y, p_test), "probability_histogram": M.probability_histogram(p_test),
           "coefficients": [{"feature": f, "coef_per_sd": float(c), "odds_ratio_per_sd": float(np.exp(c))}
                            for f, c in zip(PLAYER_FEATURES, lr.coef_[0])],
           "intercept": float(lr.intercept_[0]),
           "feature_means": {f: float(tv[f].mean()) for f in PLAYER_FEATURES}}
    clusters = series_key(te).to_numpy()
    comps = {}
    for ref in ("p_blue_logreg", "p_blue_elo_logit", "p_blue_elo"):
        if ref in te:
            name = ref.replace("p_blue_", "")
            comps[f"{MODEL_KEY}_vs_{name}_brier"] = M.paired_bootstrap_diff(y, p_test, te[ref].to_numpy(), "brier",
                                                                           clusters=clusters)
            comps[f"{MODEL_KEY}_vs_{name}_log_loss"] = M.paired_bootstrap_diff(y, p_test, te[ref].to_numpy(),
                                                                              "log_loss", clusters=clusters)
    out["comparisons"] = comps
    return out


def rebuild_published(processed: Path, eval_path: Path) -> tuple[pd.DataFrame, dict]:
    """Rebuild the published feature matrix, split and test predictions from the saved
    evaluation.json (no Elo tuning)."""
    from machine_learning.data_preparation.splits import SplitConfig, assign_splits
    from machine_learning.elo.elo import EloConfig, run_elo
    from machine_learning.feature_engineering.features import build_feature_matrix
    from machine_learning.training.train import fit_logreg
    ev = json.loads(eval_path.read_text())
    ec = ev["elo_config"]
    matches = pd.read_parquet(processed / "matches.parquet")
    games, _ = run_elo(matches, EloConfig(k=ec["k"], initial=ec["initial"], carryover_shrink=ec["carryover_shrink"],
                                          k_league=ec["k_league"]))
    df = build_feature_matrix(games, matches, ec["initial"])
    df, split = assign_splits(df, SplitConfig(**ev["split"]["config"]))
    for k in ("train_end", "validation_end"):
        if str(split[k]) != str(ev["split"][k]):
            raise RuntimeError(f"Rebuilt split differs from the saved model ({k}); retrain everything instead.")
    tr, va, te = (df[df["split"] == s] for s in ("train", "validation", "test"))
    tv = pd.concat([tr, va])
    df.loc[te.index, "p_blue_logreg"] = fit_logreg(tv[FEATURES], tv["blue_won"], ev["best_C"]).predict_proba(
        te[FEATURES])[:, 1]
    df.loc[te.index, "p_blue_elo_logit"] = fit_logreg(tv[["elo_diff"]], tv["blue_won"], 1e6).predict_proba(
        te[["elo_diff"]])[:, 1]
    check = M.brier(te["blue_won"], df.loc[te.index, "p_blue_logreg"])
    saved = ev["evaluation"]["logreg"]["test"]["brier"]
    if abs(check - saved) > 1e-9:
        raise RuntimeError(f"Rebuilt logistic model does not match the saved one ({check} vs {saved}).")
    return df, ev


def persist_player_model(res: dict, ev: dict, df: pd.DataFrame, database_url: str | None = None) -> int:
    from sqlalchemy import delete, insert, select

    from backend.app.core.jsonutil import jsonable
    from backend.app.database.session import get_sessionmaker
    from backend.app.models import Game, Match, ModelPrediction, ModelVersion
    from pipelines.oracle_elixir.load import records
    from machine_learning.feature_engineering.features import FEATURE_DEFINITIONS
    sm = get_sessionmaker(database_url)
    with sm() as db:
        game = db.scalar(select(Game).where(Game.slug == "lol"))
        base = db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == "logreg"))
        if base is None or base.version != ev["version"]:
            raise RuntimeError("The database does not hold the matching published model version "
                               f"({ev['version']}); load or retrain that first.")
        old = select(ModelVersion.id).where(ModelVersion.game_id == game.id, ModelVersion.model_key == MODEL_KEY)
        db.execute(delete(ModelPrediction).where(ModelPrediction.model_version_id.in_(old)))
        db.execute(delete(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == MODEL_KEY))
        metrics = {"test": res["test"], "validation": res["validation"], "calibration": res["calibration"],
                   "roc": res["roc"], "confusion": res["confusion"],
                   "probability_histogram": res["probability_histogram"], "comparisons": res["comparisons"],
                   "class_balance": (base.metrics or {}).get("class_balance")}
        row = ModelVersion(
            game_id=game.id, model_key=MODEL_KEY, version=ev["version"], display_name=DISPLAY_NAME, status="trained",
            trained_at=datetime.now(UTC), periods=base.periods,
            hyperparameters=jsonable({"elo": ev["elo_config"], "C": res["best_C"], "C_grid": res["C_grid"],
                                      "coefficients": res["coefficients"], "intercept": res["intercept"],
                                      "feature_means": res["feature_means"],
                                      "evidence": "docs/EXPERIMENTS.md (walk-forward 2022-2026)"}),
            feature_definitions=FEATURE_DEFINITIONS + [PREMATCH_FEATURE],
            metrics=jsonable(metrics), artifact_path=f"{ev['version']}/{MODEL_KEY}.joblib")
        db.add(row)
        db.flush()
        match_id = dict(db.execute(select(Match.source_match_id, Match.id).where(Match.game_id == game.id)).all())
        rows = []
        for split, p in (("validation", res["p_validation"]), ("test", res["p_test"])):
            sub = df.loc[p.index]
            rows.append(pd.DataFrame({"model_version_id": row.id, "match_id": sub["source_game_id"].map(match_id),
                                      "split": split, "prob_blue_win": p.to_numpy(), "blue_won": sub["blue_won"]}))
        recs = pd.concat(rows).dropna(subset=["match_id"]).astype({"match_id": int})
        db.execute(insert(ModelPrediction), records(recs))
        db.commit()
        return row.id


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    from backend.app.core.config import get_settings
    from pipelines.oracle_elixir.config import PROCESSED_DIR
    from machine_learning.training.train import C_GRID
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--processed", type=Path, default=PROCESSED_DIR)
    a = ap.parse_args(argv)
    models_dir = Path(get_settings().models_dir)
    evals = sorted(models_dir.glob("*/evaluation.json"), key=lambda p: p.stat().st_mtime)
    if not evals:
        log.error("No trained model version found in %s", models_dir)
        return 1
    eval_path = evals[-1]
    df, ev = rebuild_published(a.processed, eval_path)
    players = pd.read_parquet(a.processed / "player_rows.parquet",
                              columns=["source_game_id", "team_key", "player_key", "match_date"])
    df = add_player_feature(df, players)
    res = fit_player_model(df, C_GRID)
    joblib.dump(res["model"], eval_path.parent / f"{MODEL_KEY}.joblib")
    summary = {k: res[k] for k in ("best_C", "C_grid", "test", "validation", "coefficients", "intercept",
                                   "comparisons", "feature_means")}
    (eval_path.parent / f"evaluation_{MODEL_KEY}.json").write_text(json.dumps(summary, indent=2, default=str))
    t = res["test"]
    c = res["comparisons"][f"{MODEL_KEY}_vs_logreg_brier"]
    log.info("test brier=%.4f log_loss=%.4f acc=%.3f | vs logreg %.5f [%.5f, %.5f]", t["brier"], t["log_loss"],
             t["accuracy"], c["difference"], c["ci95_low"], c["ci95_high"])
    if not a.no_db:
        mv_id = persist_player_model(res, ev, df)
        log.info("model version %d (%s) and its predictions written to the database", mv_id, MODEL_KEY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
