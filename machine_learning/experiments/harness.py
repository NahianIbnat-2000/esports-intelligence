"""Shared evaluation harness for follow-up studies (mechanisms, robustness).

It rebuilds exactly the evaluation settings that the published results used,
without re-tuning Elo:

  main      the published split (train to 11 Aug 2024, validation to 22 Sep 2025,
            test to 14 Nov 2026) and the published Elo configuration, read from
            the saved evaluation.json.
  wf2022 .. wf2026  the five walk-forward windows, each with the team-Elo and
            player-Elo configuration that the saved walk-forward record chose on
            that window's validation year.

Every logistic model: C chosen on validation log loss (fit on train), refit on
train + validation, scored once on test. Uncertainty: paired bootstrap that
resamples whole series (tournament, team pair, UTC day), as in the published work.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from machine_learning.data_preparation.splits import SplitConfig, assign_splits
from machine_learning.elo.elo import EloConfig, run_elo
from machine_learning.evaluation import metrics as M
from machine_learning.feature_engineering.features import FEATURES, build_feature_matrix
from machine_learning.training.train import C_GRID, series_key

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_EVAL = ROOT / "machine_learning/models/artifacts/1.0.0+c8b6f8e19c/evaluation.json"
WF_RECORD = ROOT / "machine_learning/experiments/registry/walk-forward-20261120-154137-c8b6f8e19c.json"
N_BOOT, SEED = 2000, 0


@dataclass
class Setting:
    name: str
    elo: tuple            # (k, carryover_shrink, k_league)
    player_elo: tuple     # (k, carryover_shrink, k_league)
    test_year: int | None = None


def settings() -> list[Setting]:
    ev = json.loads(ARTIFACT_EVAL.read_text())
    ec = ev["elo_config"]
    wf = json.loads(WF_RECORD.read_text())
    out = []
    pl_main = None
    for w in wf["windows"]:
        c, p = w["chosen"]["elo_league"], w["chosen"]["player_elo"]
        s = Setting(f"wf{w['test_year']}", (c["k"], c["carryover_shrink"], c["k_league"]),
                    (p["k"], p["carryover_shrink"], p["k_league"]), w["test_year"])
        out.append(s)
        if w["test_year"] == 2025:      # validation year 2024 is closest to the main validation period
            pl_main = s.player_elo
    out.insert(0, Setting("main", (ec["k"], ec["carryover_shrink"], ec["k_league"]), pl_main))
    return out


def split_masks(df: pd.DataFrame, s: Setting) -> tuple[pd.Series, pd.Series, pd.Series]:
    if s.name == "main":
        ev = json.loads(ARTIFACT_EVAL.read_text())
        sp, info = assign_splits(df.copy(), SplitConfig(**ev["split"]["config"]))
        for k in ("train_end", "validation_end"):
            if str(info[k]) != str(ev["split"][k]):
                raise RuntimeError(f"rebuilt split differs from the published one ({k})")
        lab = sp["split"]
        return lab.eq("train"), lab.eq("validation"), lab.eq("test")
    cfg = SplitConfig()
    start = df["match_date"].min()
    eligible = (df["match_date"] >= start + pd.Timedelta(days=cfg.burn_in_days)) & \
               (df["min_prior_games"] >= cfg.min_prior_games)
    year = df["match_date"].dt.year
    Y = s.test_year
    return eligible & (year < Y - 1), eligible & (year == Y - 1), eligible & (year == Y)


def elo_frame(matches: pd.DataFrame, elo: tuple) -> tuple[pd.DataFrame, pd.DataFrame]:
    games, _ = run_elo(matches, EloConfig(k=elo[0], carryover_shrink=elo[1], k_league=elo[2]))
    df = build_feature_matrix(games, matches)
    df["series"] = series_key(df)
    return games, df


def fit_lr(X, y, C):
    return Pipeline([("s", StandardScaler()), ("lr", LogisticRegression(C=C, max_iter=3000))]).fit(X, y)


def logloss(y, p) -> float:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def fit_select(df, feats, tr, va, te, c_grid=C_GRID) -> dict:
    """C on validation log loss, refit on train+validation, score test once."""
    ytr, yva = df.loc[tr, "blue_won"], df.loc[va, "blue_won"].to_numpy()
    scores = []
    for C in c_grid:
        p = fit_lr(df.loc[tr, feats], ytr, C).predict_proba(df.loc[va, feats])[:, 1]
        scores.append((logloss(yva, p), C))
    val_ll, C = min(scores)
    trva = tr | va
    model = fit_lr(df.loc[trva, feats], df.loc[trva, "blue_won"], C)
    p = model.predict_proba(df.loc[te, feats])[:, 1]
    lr = model.named_steps["lr"]
    return {"p": p, "C": C, "val_log_loss": val_ll,
            "coef": dict(zip(feats, map(float, lr.coef_[0]))), "intercept": float(lr.intercept_[0])}


def summarise(y, p) -> dict:
    s = M.summary(y, p)
    return {k: s.get(k) for k in ("n", "brier", "log_loss", "accuracy", "roc_auc")}


def compare(y, pa, pb, clusters, metric="brier", n_boot=N_BOOT) -> dict:
    r = M.paired_bootstrap_diff(y, pa, pb, metric, n_boot, SEED, clusters)
    return {k: r[k] for k in ("difference", "ci95_low", "ci95_high", "share_bootstrap_model_better", "n_units")}


def cluster_se(y, pa, pb, clusters, metric="brier", n_boot=N_BOOT, seed=SEED) -> tuple[float, float]:
    """Mean loss difference and its cluster-bootstrap standard error."""
    y = np.asarray(y, float)
    pa, pb = np.clip(pa, 1e-12, 1 - 1e-12), np.clip(pb, 1e-12, 1 - 1e-12)
    if metric == "brier":
        d = (pa - y) ** 2 - (pb - y) ** 2
    else:
        d = -(y * np.log(pa) + (1 - y) * np.log(1 - pa)) + (y * np.log(pb) + (1 - y) * np.log(1 - pb))
    codes, uniq = pd.factorize(pd.Series(clusters))
    k = len(uniq)
    sums, sizes = np.bincount(codes, weights=d, minlength=k), np.bincount(codes, minlength=k)
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, k, k)
        boots[b] = sums[pick].sum() / sizes[pick].sum()
    return float(d.mean()), float(boots.std(ddof=1))


def data_record(raw_dir: Path) -> dict:
    from machine_learning.experiments import registry
    return registry.data_checksum(raw_dir / "manifest.json")
