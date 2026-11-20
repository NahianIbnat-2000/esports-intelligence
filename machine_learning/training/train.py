"""Train and evaluate the match-outcome models on the processed LoL dataset.

Models (all predict P(blue side wins one game)):
  elo       Pure Elo expected score. K-factor and season carry-over are chosen
            by validation log loss. No parameters are fitted to outcomes.
  elo_logit Logistic regression on elo_diff only (calibrated Elo; the intercept
            estimates the blue-side advantage).
  logreg    Logistic regression on the pre-specified feature set
            (machine_learning/feature_engineering/features.py).

Procedure:
  1. Elo grid over K x carry-over, chosen on validation log loss.
  2. Features built from the chosen Elo run (pre-game values only).
  3. Regularisation strength C for logreg chosen on validation
     (fit on train, scored on validation).
  4. elo_logit and logreg refit on train + validation; all three models are
     scored once on the same test games.

Usage:  python -m machine_learning.training.train [--no-db]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from machine_learning.data_preparation.splits import SplitConfig, assign_splits
from machine_learning.elo.elo import EloConfig, league_table, run_elo
from machine_learning.evaluation import metrics as M
from machine_learning.feature_engineering.features import FEATURE_DEFINITIONS, FEATURES, build_feature_matrix

log = logging.getLogger("ml.train")

K_GRID = [8, 12, 16, 20, 24, 32, 40, 48, 56, 64, 80]
SHRINK_GRID = [0.0, 0.25, 0.5, 0.75]
K_LEAGUE_GRID = [0.0, 2.0, 4.0, 8.0, 16.0, 32.0]
C_GRID = [0.0003, 0.001, 0.003, 0.01, 0.1, 1.0, 10.0]


def series_key(df: pd.DataFrame) -> pd.Series:
    """Approximate series id: same tournament, same pair of teams, same UTC day.
    The source has no series id; this groups the games of one best-of."""
    a = df[["blue_team_key", "red_team_key"]].min(axis=1)
    b = df[["blue_team_key", "red_team_key"]].max(axis=1)
    return df["tournament_key"].astype(str) + "|" + a + "|" + b + "|" + df["match_date"].dt.strftime("%Y-%m-%d")
MIN_TRAIN, MIN_TEST = 500, 200


def dataset_fingerprint(files: list[dict]) -> str:
    return hashlib.sha256("".join(sorted(f["sha256"] for f in files)).encode()).hexdigest()[:10]


def tune_elo(matches: pd.DataFrame, cfg: SplitConfig):
    # Split membership depends only on dates and game counts, not on Elo, so
    # it is computed once and reused for every grid point.
    games0, _ = run_elo(matches, EloConfig())
    labelled, _ = assign_splits(build_feature_matrix(games0, matches), cfg)
    val_ids = set(labelled.loc[labelled["split"] == "validation", "source_game_id"])
    if not val_ids:
        raise ValueError("no validation games; dataset too small")
    grid: list[dict] = []
    cache: dict = {}

    def score(ec: EloConfig):
        key = (ec.k, ec.carryover_shrink, ec.k_league)
        if key not in cache:
            games, state = run_elo(matches, ec)
            v = games[games["source_game_id"].isin(val_ids)]
            row = {"k": ec.k, "carryover_shrink": ec.carryover_shrink, "k_league": ec.k_league,
                   "n_validation": int(len(v)),
                   "validation_log_loss": M.summary(v["blue_won"], v["p_blue_elo"])["log_loss"],
                   "validation_brier": M.brier(v["blue_won"], v["p_blue_elo"])}
            grid.append(row)
            cache[key] = (row["validation_log_loss"], ec, games, state)
        return cache[key]

    # Coordinate search, all on validation log loss:
    # 1) K x shrinkage with flat Elo (k_league = 0),
    # 2) k_league at that K and shrinkage,
    # 3) K x shrinkage again at the chosen k_league.
    best_flat = min((score(EloConfig(k=k, carryover_shrink=s)) for k in K_GRID for s in SHRINK_GRID),
                    key=lambda r: r[0])
    kf, sf = best_flat[1].k, best_flat[1].carryover_shrink
    best_kl = min((score(EloConfig(k=kf, carryover_shrink=sf, k_league=kl)) for kl in K_LEAGUE_GRID),
                  key=lambda r: r[0])[1].k_league
    best = min((score(EloConfig(k=k, carryover_shrink=s, k_league=best_kl)) for k in K_GRID for s in SHRINK_GRID),
               key=lambda r: r[0])
    best = min(best, best_flat, key=lambda r: r[0])
    ec, games, state = best[1], best[2], best[3]
    flat = {"config": best_flat[1].as_dict(), "games": best_flat[2], "state": best_flat[3]}
    return ec, grid, build_feature_matrix(games, matches, ec.initial), state, flat


def fit_logreg(X: pd.DataFrame, y: pd.Series, C: float) -> Pipeline:
    pipe = Pipeline([("scale", StandardScaler()), ("lr", LogisticRegression(C=C, max_iter=2000))])
    return pipe.fit(X, y)


def tree_experiment(train_df: pd.DataFrame, val_df: pd.DataFrame, C: float) -> dict:
    """Validation-only check of whether tree ensembles beat the logistic model
    on the same six features. They are never scored on the test period and
    are not deployed unless they win here (they have not so far)."""
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    y = val_df["blue_won"].values
    base = fit_logreg(train_df[FEATURES], train_df["blue_won"], C).predict_proba(val_df[FEATURES])[:, 1]
    rows = [{"model": "logistic regression (reference)", **{k: M.summary(y, base)[k] for k in ("brier", "log_loss")}}]
    candidates = {
        "gradient boosting (depth 3, lr 0.03)": HistGradientBoostingClassifier(
            learning_rate=0.03, max_depth=3, max_iter=300, early_stopping=True, validation_fraction=0.15,
            random_state=0),
        "random forest (300 trees, min leaf 200)": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=200, n_jobs=-1, random_state=0),
    }
    for name, mdl in candidates.items():
        p = mdl.fit(train_df[FEATURES], train_df["blue_won"]).predict_proba(val_df[FEATURES])[:, 1]
        cmp = M.paired_bootstrap_diff(y, p, base, "brier", n_boot=500)
        rows.append({"model": name, **{k: M.summary(y, p)[k] for k in ("brier", "log_loss")},
                     "brier_vs_logistic": cmp["difference"], "ci95_low": cmp["ci95_low"], "ci95_high": cmp["ci95_high"]})
    better = [r for r in rows[1:] if r["ci95_high"] < 0]
    return {"sample": "validation period only; models fit on training data", "results": rows,
            "decision": ("A tree model beat logistic regression on validation; review before deploying."
                         if better else "No tree model beats logistic regression on validation, so none is "
                                        "deployed or scored on the test period.")}


def train(processed_dir: Path, artifacts_dir: Path, files: list[dict], cfg: SplitConfig | None = None) -> dict:
    cfg = cfg or SplitConfig()
    matches = pd.read_parquet(processed_dir / "matches.parquet")
    trained_at = datetime.now(UTC)
    version = f"1.0.0+{dataset_fingerprint(files)}" if files else "1.0.0+nofiles"

    elo_cfg, elo_grid, df, elo_state, flat = tune_elo(matches, cfg)
    df, split_info = assign_splits(df, cfg)
    train_df, val_df, test_df = (df[df["split"] == s] for s in ("train", "validation", "test"))
    result = {"version": version, "trained_at": trained_at.isoformat(), "split": split_info,
              "elo_config": elo_cfg.as_dict(), "elo_grid": elo_grid, "features": FEATURE_DEFINITIONS,
              "league_levels": league_table(elo_state)}

    if len(train_df) < MIN_TRAIN or len(test_df) < MIN_TEST:
        result["status"] = "insufficient_data"
        result["reason"] = (f"Need at least {MIN_TRAIN} training and {MIN_TEST} test games; have "
                            f"{len(train_df)} and {len(test_df)}. Models are not activated.")
        return {"result": result, "games": df, "elo_config": elo_cfg}

    # C for logreg chosen on validation
    c_scores = []
    for C in C_GRID:
        mdl = fit_logreg(train_df[FEATURES], train_df["blue_won"], C)
        p = mdl.predict_proba(val_df[FEATURES])[:, 1]
        c_scores.append({"C": C, "validation_log_loss": M.summary(val_df["blue_won"], p)["log_loss"]})
    best_C = min(c_scores, key=lambda r: r["validation_log_loss"])["C"]

    result["experimental_models"] = tree_experiment(train_df, val_df, best_C)

    # Validation predictions (fit on train) for reporting
    lr_tr = fit_logreg(train_df[FEATURES], train_df["blue_won"], best_C)
    el_tr = fit_logreg(train_df[["elo_diff"]], train_df["blue_won"], 1e6)
    df.loc[val_df.index, "p_blue_logreg"] = lr_tr.predict_proba(val_df[FEATURES])[:, 1]
    df.loc[val_df.index, "p_blue_elo_logit"] = el_tr.predict_proba(val_df[["elo_diff"]])[:, 1]

    # Final fit on train + validation, scored once on test
    tv = pd.concat([train_df, val_df])
    logreg = fit_logreg(tv[FEATURES], tv["blue_won"], best_C)
    elo_logit = fit_logreg(tv[["elo_diff"]], tv["blue_won"], 1e6)
    df.loc[test_df.index, "p_blue_logreg"] = logreg.predict_proba(test_df[FEATURES])[:, 1]
    df.loc[test_df.index, "p_blue_elo_logit"] = elo_logit.predict_proba(test_df[["elo_diff"]])[:, 1]
    test_df = df.loc[test_df.index]

    # Prevalence baselines: no information about the teams at all.
    train_rate = float(train_df["blue_won"].mean())
    tv_rate = float(tv["blue_won"].mean())
    df["p_blue_const50"] = 0.5
    df.loc[val_df.index, "p_blue_prevalence"] = train_rate
    df.loc[test_df.index, "p_blue_prevalence"] = tv_rate
    test_df = df.loc[test_df.index]
    probs = {"baseline_50": "p_blue_const50", "baseline_prevalence": "p_blue_prevalence",
             "elo": "p_blue_elo", "elo_logit": "p_blue_elo_logit", "logreg": "p_blue_logreg"}
    y = test_df["blue_won"].values
    evaluation = {}
    for name, col in probs.items():
        p = test_df[col].values
        evaluation[name] = {"test": M.summary(y, p), "calibration": M.calibration_table(y, p),
                            "roc": M.roc_points(y, p), "confusion": M.confusion(y, p),
                            "probability_histogram": M.probability_histogram(p),
                            "validation": M.summary(val_df["blue_won"].values, df.loc[val_df.index, col].values)}
    result["baselines"] = {"train_blue_win_rate": train_rate, "train_plus_validation_blue_win_rate": tv_rate,
                           "note": "baseline_prevalence predicts the blue-side win rate of the data available "
                                   "before the period: the training rate for validation games, the train + "
                                   "validation rate for test games."}
    clusters = series_key(test_df).values
    comparisons = {f"{m}_vs_elo_{metric}": M.paired_bootstrap_diff(y, test_df[probs[m]].values,
                                                                  test_df["p_blue_elo"].values, metric,
                                                                  clusters=clusters)
                   for m in ("elo_logit", "logreg") for metric in ("brier", "log_loss")}
    comparisons["logreg_vs_elo_logit_brier"] = M.paired_bootstrap_diff(
        y, test_df["p_blue_logreg"].values, test_df["p_blue_elo_logit"].values, "brier", clusters=clusters)
    for base in ("baseline_50", "baseline_prevalence"):
        comparisons[f"elo_vs_{base}_brier"] = M.paired_bootstrap_diff(
            y, test_df["p_blue_elo"].values, test_df[probs[base]].values, "brier", clusters=clusters)
    # Sensitivity: cluster by tournament instead of series (much coarser)
    tclusters = test_df["tournament_key"].values
    comparisons["logreg_vs_elo_brier_tournament_clusters"] = M.paired_bootstrap_diff(
        y, test_df["p_blue_logreg"].values, test_df["p_blue_elo"].values, "brier", clusters=tclusters)
    comparisons["logreg_vs_elo_logit_brier_tournament_clusters"] = M.paired_bootstrap_diff(
        y, test_df["p_blue_logreg"].values, test_df["p_blue_elo_logit"].values, "brier", clusters=tclusters)
    comparisons["logreg_vs_elo_logit_log_loss"] = M.paired_bootstrap_diff(
        y, test_df["p_blue_logreg"].values, test_df["p_blue_elo_logit"].values, "log_loss", clusters=clusters)
    # single-game resampling kept for reference (ignores within-series dependence)
    comparisons["logreg_vs_elo_brier_single_game_bootstrap"] = M.paired_bootstrap_diff(
        y, test_df["p_blue_logreg"].values, test_df["p_blue_elo"].values, "brier")
    # League offsets vs flat Elo on the same test games
    fg = flat["games"].set_index("source_game_id").loc[test_df["source_game_id"]]
    result["league_offsets"] = {
        "selected_k_league": elo_cfg.k_league,
        "flat_config": flat["config"],
        "flat_test": M.summary(y, fg["p_blue_elo"].values),
        "selected_vs_flat_brier": M.paired_bootstrap_diff(y, test_df["p_blue_elo"].values, fg["p_blue_elo"].values,
                                                          "brier", clusters=clusters),
        "selected_vs_flat_log_loss": M.paired_bootstrap_diff(y, test_df["p_blue_elo"].values,
                                                             fg["p_blue_elo"].values, "log_loss", clusters=clusters),
        "cross_league_test_games": int((test_df["blue_home"] != test_df["red_home"]).sum()),
    }
    xl = (test_df["blue_home"] != test_df["red_home"]).values
    if xl.sum() >= 100:
        result["league_offsets"]["cross_league_only_brier"] = M.paired_bootstrap_diff(
            y[xl], test_df["p_blue_elo"].values[xl], fg["p_blue_elo"].values[xl], "brier", clusters=clusters[xl])
    test_df = test_df.assign(period=test_df["match_date"].dt.tz_localize(None).dt.to_period("Q").astype(str))
    model_probs = {k: v for k, v in probs.items() if not k.startswith("baseline")}
    temporal = M.breakdown(test_df, "period", model_probs)
    top_leagues = test_df["league"].value_counts().head(12).index
    by_league = M.breakdown(test_df[test_df["league"].isin(top_leagues)], "league", model_probs, min_n=150)

    lr = logreg.named_steps["lr"]
    coefs = [{"feature": f, "coef_per_sd": float(c), "odds_ratio_per_sd": float(np.exp(c))}
             for f, c in zip(FEATURES, lr.coef_[0])]
    el = elo_logit.named_steps["lr"]
    elo_logit_params = {"intercept": float(el.intercept_[0]),
                        "implied_blue_win_prob_equal_elo": float(1 / (1 + np.exp(-el.intercept_[0]))),
                        "coef_per_sd_elo_diff": float(el.coef_[0][0])}

    out_dir = artifacts_dir / version
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(logreg, out_dir / "logreg.joblib")
    joblib.dump(elo_logit, out_dir / "elo_logit.joblib")
    result.update({
        "status": "trained", "C_grid": c_scores, "best_C": best_C, "evaluation": evaluation,
        "comparisons": comparisons, "temporal_breakdown": temporal, "league_breakdown": by_league,
        "logreg_coefficients": coefs, "logreg_intercept": float(lr.intercept_[0]),
        "elo_logit_parameters": elo_logit_params, "artifact_dir": str(out_dir),
        "class_balance": {s: split_info[s]["blue_win_rate"] for s in ("train", "validation", "test")},
        "feature_means": {f: float(tv[f].mean()) for f in FEATURES},
    })
    (out_dir / "evaluation.json").write_text(json.dumps(result, indent=2, default=str))
    return {"result": result, "games": df, "elo_config": elo_cfg}


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db", action="store_true")
    a = ap.parse_args(argv)
    from backend.app.core.config import get_settings
    from pipelines.oracle_elixir.config import PROCESSED_DIR
    from pipelines.oracle_elixir.download import registered_files
    if not (PROCESSED_DIR / "matches.parquet").exists():
        log.error("No processed dataset. Run the Oracle's Elixir pipeline first.")
        return 1
    out = train(PROCESSED_DIR, Path(get_settings().models_dir), registered_files())
    r = out["result"]
    log.info("status=%s version=%s", r["status"], r["version"])
    if r["status"] == "trained":
        for k, v in r["evaluation"].items():
            auc = v["test"]["roc_auc"]
            log.info("%-20s test brier=%.4f log_loss=%.4f acc=%.3f auc=%s", k, v["test"]["brier"],
                     v["test"]["log_loss"], v["test"]["accuracy"], "n/a" if auc is None else f"{auc:.3f}")
    if not a.no_db:
        from machine_learning.training.persist import persist
        persist(out)
        log.info("model versions, Elo ratings and test predictions written to the database")
    # Pre-game player model (adds one model version; needs player rows from the pipeline)
    if r["status"] == "trained" and (PROCESSED_DIR / "player_rows.parquet").exists():
        from machine_learning.training import player_model
        player_model.main(["--no-db"] if a.no_db else [])
    return 0


if __name__ == "__main__":
    sys.exit(main())
