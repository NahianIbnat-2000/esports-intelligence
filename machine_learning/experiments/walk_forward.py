"""Walk-forward (rolling-origin) evaluation and feature-family ablation.

Design (fixed before running; recorded in every registry record):

Windows   For each test calendar year Y in TEST_YEARS: train = eligible games in
          years before Y-1, validation = year Y-1, test = year Y (UTC dates).
          Eligible = after the 90-day burn-in and both teams have at least 5
          earlier games (same rule as the published split). Each game is in at
          most one test window.
Elo       Team Elo is replayed once per grid point over all games. Pre-game
          ratings only use earlier games, so one replay serves every window.
          Per window, hyperparameters are chosen on that window's validation
          log loss: flat Elo over k_league = 0, league Elo over the full grid.
          Player Elo likewise over its own grid.
Models    All logistic models: C chosen on validation (fit on train), then refit
          on train + validation and scored once on test.
            baseline       blue-side win rate of train + validation
            elo_flat       flat Elo expected score
            elo_league     Elo with league levels, expected score
            elo_cal        logistic regression on elo_diff (calibrated Elo)
            form           published logistic model (6 features)
            form_roster    form + roster features (lineup known at start)
            form_<one>     form + a single roster feature (ablation)
            form_player_exp_prev  form + player experience of the PREVIOUS lineup
                           (pre-match: needs no knowledge of today's lineup)
            player_cal     logistic regression on player_elo_diff
            player_cal_prev  calibrated player Elo of each team's previous lineup
            prematch       form + player_exp_prev + player_elo_prev (no knowledge of
                           today's lineup: usable before match day)
            all            form + roster + player_elo_diff
Comparisons  Paired differences in Brier and log loss with a series-cluster
          bootstrap, per window and pooled over all test windows.
Subgroups Pooled test games by type: both teams from the same home league in a
          domestic game (league levels cancel, so league tier cannot explain a
          gain), top leagues only, teams from different leagues, and games with a
          team that has fewer than 20 earlier games.
Patch     Pooled test games split into the first 7 days after a patch first
          appears in the data vs later; Brier of elo_cal and all in each group.

Usage:  python -m machine_learning.experiments.walk_forward [--processed DIR] [--raw DIR]
"""
from __future__ import annotations

import argparse
import itertools
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from machine_learning.data_preparation.splits import SplitConfig
from machine_learning.elo.elo import EloConfig, run_elo
from machine_learning.evaluation import metrics as M
from machine_learning.experiments import registry
from machine_learning.experiments.lineups import PREMATCH_FEATURE, ROSTER_DEFINITIONS, ROSTER_FEATURES, \
    add_roster_diffs, lineup_table, roster_features
from machine_learning.experiments.player_elo import PlayerEloConfig, run_player_elo
from machine_learning.feature_engineering.features import FEATURES, build_feature_matrix
from machine_learning.training.train import C_GRID, K_GRID, K_LEAGUE_GRID, SHRINK_GRID, series_key

log = logging.getLogger("ml.walk_forward")

TEST_YEARS = [2022, 2023, 2024, 2025, 2026]
PLAYER_K_GRID = [24, 32, 40, 48, 56, 64]
PLAYER_SHRINK_GRID = [0.0, 0.1, 0.25, 0.5]
PLAYER_K_LEAGUE_GRID = [0.0, 8.0, 16.0, 32.0]
PATCH_EARLY_DAYS = 7
TOP_LEAGUES = ["LCK", "LPL", "LEC", "LCS", "LTA N"]   # LTA N = North America in 2025
NEW_TEAM_GAMES = 20
SUBGROUP_COMPARISONS = [("form_player_exp", "form"), ("form_player_exp_prev", "form"), ("prematch", "form"),
                        ("player_cal_prev", "elo_cal"), ("all", "form")]
N_BOOT_WINDOW, N_BOOT_POOLED, SEED = 1000, 2000, 0

MODELS = ["baseline", "elo_flat", "elo_league", "elo_cal", "form", "form_continuity", "form_tenure",
          "form_player_exp", "form_player_exp_prev", "form_roster", "player_cal",
          "player_cal_prev", "prematch", "all"]
COMPARISONS = [  # (model, reference, question)
    ("elo_league", "elo_flat", "League levels vs flat Elo"),
    ("elo_cal", "elo_league", "Calibration of league Elo"),
    ("form", "elo_cal", "Form features over calibrated Elo"),
    ("form_continuity", "form", "Continuity alone over form"),
    ("form_tenure", "form", "Tenure alone over form"),
    ("form_player_exp", "form", "Player experience alone over form"),
    ("form_player_exp_prev", "form", "Player experience, previous lineup (pre-match)"),
    ("form_roster", "form", "Roster features over form"),
    ("player_cal", "elo_cal", "Player Elo vs team Elo (both calibrated)"),
    ("player_cal_prev", "elo_cal", "Player Elo, previous lineup (pre-match) vs team Elo"),
    ("prematch", "form", "Pre-match additions over form (previous lineup only)"),
    ("all", "form", "Roster + player Elo over form"),
    ("all", "elo_cal", "Everything over calibrated Elo"),
]

_MATCHES: pd.DataFrame | None = None


def _init(matches):
    global _MATCHES
    _MATCHES = matches


def _team_run(cfg: tuple) -> tuple:
    k, s, kl = cfg
    g, _ = run_elo(_MATCHES, EloConfig(k=k, carryover_shrink=s, k_league=kl))
    return cfg, (g["blue_elo_pre"] - g["red_elo_pre"]).to_numpy(np.float64)


def logloss(y, p):
    return M.summary(y, p)["log_loss"]


def fit_lr(X, y, C):
    return Pipeline([("s", StandardScaler()), ("lr", LogisticRegression(C=C, max_iter=2000))]).fit(X, y)


def choose_and_fit(df, feats, tr, va, trva):
    best = None
    for C in C_GRID:
        p = fit_lr(df.loc[tr, feats], df.loc[tr, "blue_won"], C).predict_proba(df.loc[va, feats])[:, 1]
        ll = logloss(df.loc[va, "blue_won"], p)
        if best is None or ll < best[0]:
            best = (ll, C)
    model = fit_lr(df.loc[trva, feats], df.loc[trva, "blue_won"], best[1])
    return model, best[1]


def summarise(y, p) -> dict:
    s = M.summary(y, p)
    keep = ("n", "brier", "log_loss", "accuracy", "roc_auc", "ece")
    out = {k: s.get(k) for k in keep}
    if out.get("ece") is None:
        out["ece"] = M.expected_calibration_error(y, p)
    return out


def run(processed: Path, raw: Path, workers: int) -> dict:
    matches = pd.read_parquet(processed / "matches.parquet")
    players = pd.read_parquet(processed / "player_rows.parquet",
                              columns=["source_game_id", "team_key", "player_key", "match_date"])
    data = registry.data_checksum(raw / "manifest.json")
    split_cfg = SplitConfig()

    log.info("lineups and roster features")
    lineups = lineup_table(players)
    roster = roster_features(lineups)

    log.info("base replay")
    base_games, _ = run_elo(matches, EloConfig())
    base = build_feature_matrix(base_games, matches)            # n_prior, context, homes
    base = add_roster_diffs(base, roster)
    base["series"] = series_key(base)
    start = base["match_date"].min()
    eligible = (base["match_date"] >= start + pd.Timedelta(days=split_cfg.burn_in_days)) & \
               (base["min_prior_games"] >= split_cfg.min_prior_games)
    year = base["match_date"].dt.year

    log.info("team Elo grid (%d runs)", len(K_GRID) * len(SHRINK_GRID) * len(K_LEAGUE_GRID))
    grid = list(itertools.product(K_GRID, SHRINK_GRID, K_LEAGUE_GRID))
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(matches,)) as ex:
        diffs = dict(ex.map(_team_run, grid))
    y = base["blue_won"].to_numpy()

    log.info("player Elo grid")
    pgrid = list(itertools.product(PLAYER_K_GRID, PLAYER_SHRINK_GRID, PLAYER_K_LEAGUE_GRID))
    pdiffs, pdiffs_prev = {}, {}
    for k, s, kl in pgrid:
        pe = run_player_elo(base_games, lineups, PlayerEloConfig(k=k, carryover_shrink=s, k_league=kl))
        pe = pe.set_index("source_game_id").reindex(base["source_game_id"])
        pdiffs[(k, s, kl)] = pe["player_elo_diff"].to_numpy()
        pdiffs_prev[(k, s, kl)] = pe["player_elo_prev_diff"].to_numpy()

    feat_cache: dict = {}

    def form_features(cfg):
        if cfg not in feat_cache:
            g, _ = run_elo(matches, EloConfig(k=cfg[0], carryover_shrink=cfg[1], k_league=cfg[2]))
            fm = build_feature_matrix(g, matches).set_index("source_game_id").reindex(base["source_game_id"])
            feat_cache[cfg] = fm[FEATURES].reset_index(drop=True)
        return feat_cache[cfg]

    windows, pooled = [], []
    for Y in TEST_YEARS:
        tr = eligible & (year < Y - 1)
        va = eligible & (year == Y - 1)
        te = eligible & (year == Y)
        if te.sum() < 200 or va.sum() < 200:
            continue
        trva = tr | va
        yv = y[va.to_numpy()]

        def val_ll(d):
            return logloss(yv, 1 / (1 + 10 ** (-d[va.to_numpy()] / 400)))

        flat_cfg = min((c for c in grid if c[2] == 0.0), key=lambda c: val_ll(diffs[c]))
        lg_cfg = min(grid, key=lambda c: val_ll(diffs[c]))
        pl_cfg = min(pgrid, key=lambda c: val_ll(pdiffs[c]))
        log.info("window %d: flat %s, league %s, player %s", Y, flat_cfg, lg_cfg, pl_cfg)

        df = base[["source_game_id", "match_date", "blue_won", "series", "tournament_key"] + ROSTER_FEATURES + ["player_exp_prev_diff"]].copy()
        df = pd.concat([df.reset_index(drop=True), form_features(lg_cfg)], axis=1)
        df["player_elo_diff"] = pdiffs[pl_cfg]
        df["player_elo_prev_diff"] = pdiffs_prev[pl_cfg]
        df["flat_diff"] = diffs[flat_cfg]
        df.index = base.index

        p = pd.DataFrame(index=df.index[te.to_numpy()])
        p["baseline"] = float(df.loc[trva, "blue_won"].mean())
        p["elo_flat"] = 1 / (1 + 10 ** (-df.loc[te, "flat_diff"] / 400))
        p["elo_league"] = 1 / (1 + 10 ** (-df.loc[te, "elo_diff"] / 400))
        chosen_C = {}
        coefs = {}
        for name, feats in (("elo_cal", ["elo_diff"]), ("form", FEATURES),
                            ("form_continuity", FEATURES + ["continuity_diff"]),
                            ("form_tenure", FEATURES + ["tenure_diff"]),
                            ("form_player_exp", FEATURES + ["player_exp_diff"]),
                            ("form_player_exp_prev", FEATURES + ["player_exp_prev_diff"]),
                            ("form_roster", FEATURES + ROSTER_FEATURES), ("player_cal", ["player_elo_diff"]),
                            ("player_cal_prev", ["player_elo_prev_diff"]),
                            ("prematch", FEATURES + ["player_exp_prev_diff", "player_elo_prev_diff"]),
                            ("all", FEATURES + ROSTER_FEATURES + ["player_elo_diff"])):
            model, C = choose_and_fit(df, feats, tr, va, trva)
            p[name] = model.predict_proba(df.loc[te, feats])[:, 1]
            chosen_C[name] = C
            if name in ("form_roster", "prematch", "all"):
                lr = model.named_steps["lr"]
                coefs[name] = {"intercept": float(lr.intercept_[0]),
                               "standardised": dict(zip(feats, map(float, lr.coef_[0])))}
        yt = df.loc[te, "blue_won"].to_numpy()
        cl = df.loc[te, "series"].to_numpy()
        res = {m: summarise(yt, p[m].to_numpy()) for m in MODELS}
        comps = []
        for a, b, q in COMPARISONS:
            r = M.paired_bootstrap_diff(yt, p[a].to_numpy(), p[b].to_numpy(), "brier", N_BOOT_WINDOW, SEED, cl)
            comps.append({"model": a, "reference": b, "question": q, **r})
        windows.append({
            "test_year": Y,
            "periods": {k: {"n": int(m.sum()), "start": str(df.loc[m, "match_date"].min()),
                            "end": str(df.loc[m, "match_date"].max())}
                        for k, m in (("train", tr), ("validation", va), ("test", te))},
            "chosen": {"elo_flat": dict(zip(("k", "carryover_shrink", "k_league"), flat_cfg)),
                       "elo_league": dict(zip(("k", "carryover_shrink", "k_league"), lg_cfg)),
                       "player_elo": dict(zip(("k", "carryover_shrink", "k_league"), pl_cfg)),
                       "C": chosen_C},
            "coefficients": coefs,
            "metrics": res, "comparisons_brier": comps})
        p["blue_won"], p["series"], p["window"] = yt, cl, Y
        p["match_date"] = df.loc[te, "match_date"].to_numpy()
        p["source_game_id"] = df.loc[te, "source_game_id"].to_numpy()
        pooled.append(p)

    P = pd.concat(pooled)
    yp, cp = P["blue_won"].to_numpy(), P["series"].to_numpy()
    pooled_metrics = {m: summarise(yp, P[m].to_numpy()) for m in MODELS}
    pooled_comps = []
    for a, b, q in COMPARISONS:
        row = {"model": a, "reference": b, "question": q}
        for metric in ("brier", "log_loss"):
            row[metric] = M.paired_bootstrap_diff(yp, P[a].to_numpy(), P[b].to_numpy(), metric, N_BOOT_POOLED,
                                                  SEED, cp)
        per = [next(c for c in w["comparisons_brier"] if c["model"] == a and c["reference"] == b)
               for w in windows]
        row["windows_better"] = sum(c["difference"] < 0 for c in per)
        row["windows_ci_below_zero"] = sum(c["ci95_high"] < 0 for c in per)
        row["window_sd"] = float(np.std([c["difference"] for c in per], ddof=1)) if len(per) > 1 else None
        pooled_comps.append(row)

    # Patch analysis on pooled test games
    pm = matches.set_index("source_game_id")["patch"]
    first_seen = matches.groupby("patch")["match_date"].min()
    P["patch"] = pm.reindex(P["source_game_id"]).to_numpy()
    P["days_into_patch"] = (P["match_date"] - P["patch"].map(first_seen)).dt.days
    P["patch_group"] = np.where(P["days_into_patch"] < PATCH_EARLY_DAYS, "first 7 days", "later")
    patch = []
    for grp, g in P.dropna(subset=["patch"]).groupby("patch_group"):
        d = M.paired_bootstrap_diff(g["blue_won"], g["all"], g["elo_cal"], "brier", N_BOOT_POOLED, SEED,
                                    g["series"].to_numpy())
        patch.append({"group": grp, "n": int(len(g)), "elo_cal": summarise(g["blue_won"], g["elo_cal"]),
                      "all": summarise(g["blue_won"], g["all"]), "all_vs_elo_cal_brier": d})

    # Subgroups: does player information still help where league tier cannot explain it?
    ctx = base.set_index("source_game_id")[["blue_home", "red_home", "international", "min_prior_games"]]
    P = P.join(ctx, on="source_game_id")
    same = (P["blue_home"] == P["red_home"]) & ~P["international"].astype(bool)
    groups = {
        "Same home league, domestic game (league level cancels out)": same,
        "Top leagues only, domestic (LCK, LPL, LEC, LCS / LTA N)": same & P["blue_home"].isin(TOP_LEAGUES),
        "Teams from different leagues": P["blue_home"] != P["red_home"],
        f"Established teams (both >= {NEW_TEAM_GAMES} earlier games)": P["min_prior_games"] >= NEW_TEAM_GAMES,
        f"A newer team (< {NEW_TEAM_GAMES} earlier games)": P["min_prior_games"] < NEW_TEAM_GAMES,
    }
    subgroups = []
    for label, mask in groups.items():
        g = P[mask.to_numpy()]
        row = {"group": label, "n": int(len(g)),
               "brier": {m: M.brier(g["blue_won"], g[m]) for m in ("elo_cal", "form", "prematch", "all")},
               "comparisons": []}
        for a, b in SUBGROUP_COMPARISONS:
            d = M.paired_bootstrap_diff(g["blue_won"], g[a], g[b], "brier", N_BOOT_POOLED, SEED, g["series"].to_numpy())
            row["comparisons"].append({"model": a, "reference": b, **d})
        subgroups.append(row)

    return {
        "data": data,
        "design": {"test_years": TEST_YEARS, "split_rule": "train < Y-1, validation = Y-1, test = Y (UTC year)",
                   "eligibility": {"burn_in_days": split_cfg.burn_in_days,
                                   "min_prior_games": split_cfg.min_prior_games},
                   "team_elo_grid": {"k": K_GRID, "carryover_shrink": SHRINK_GRID, "k_league": K_LEAGUE_GRID},
                   "player_elo_grid": {"k": PLAYER_K_GRID, "carryover_shrink": PLAYER_SHRINK_GRID,
                                       "k_league": PLAYER_K_LEAGUE_GRID},
                   "C_grid": C_GRID, "selection_metric": "validation log loss",
                   "bootstrap": {"unit": "series (tournament, team pair, UTC day)",
                                 "n_window": N_BOOT_WINDOW, "n_pooled": N_BOOT_POOLED, "seed": SEED},
                   "features": {"form": FEATURES, "roster": ROSTER_DEFINITIONS + [PREMATCH_FEATURE], "player": ["player_elo_diff", "player_elo_prev_diff"]},
                   "lineup_note": "Roster and player-Elo features use the lineup that played, which is known when "
                                  "the game starts but not days before.",
                   "patch_early_days": PATCH_EARLY_DAYS, "models": MODELS,
                   "subgroups": {"top_leagues": TOP_LEAGUES, "new_team_games": NEW_TEAM_GAMES,
                                 "home_league": "league a team played most domestic games in, earlier games only"}},
        "windows": windows,
        "pooled": {"n": int(len(P)), "metrics": pooled_metrics, "comparisons": pooled_comps},
        "patch_analysis": patch,
        "subgroups": subgroups,
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", type=Path,
                    default=Path(os.environ.get("DATA_DIR", "data")) / "processed" / "oracles_elixir")
    ap.add_argument("--raw", type=Path, default=Path(os.environ.get("DATA_DIR", "data")) / "raw" / "oracles_elixir")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    a = ap.parse_args()
    rec = run(a.processed, a.raw, a.workers)
    path = registry.save(rec, "walk-forward")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
