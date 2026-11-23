"""What does player experience capture? (docs/PLAYER_EXPERIENCE_MECHANISMS.md)

Hypotheses (fixed before running):
  H1 skill proxy      If experience only stands in for player quality, adding
                      point-in-time quality measures (shrunk player win rate,
                      lane gold lead at 15 minutes, player Elo, rating of the
                      players' previous teams) should remove most of its gain.
  H2 participation    If it stands in for recent activity or career length,
                      those measures should remove its gain.
  H3 cold start       If it mainly fixes the rating of new teams, its gain
                      should be concentrated in new teams, and a player-informed
                      Elo start for new teams should capture much of it.
  H4 measurement      The simple mean of log(1 + games) should be competitive
                      with other transformations chosen on validation data.

Information contract: every feature describes each team's PREVIOUS lineup and
uses earlier games only (same as the deployed feature), except the
player-informed Elo start (`init`), which uses today's lineup at a team's
first game and is labelled as lineup-confirmed.

Usage: python -m machine_learning.experiments.mechanisms [--processed DIR] [--raw DIR]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from machine_learning.evaluation import metrics as M
from machine_learning.experiments import harness as H
from machine_learning.experiments import registry
from machine_learning.experiments.lineups import lineup_table
from machine_learning.experiments.player_elo import PlayerEloConfig, run_player_elo
from machine_learning.experiments.player_history import (DECAY_H, ROLES, SAT_T, TEAM_COLS, add_history_diffs,
                                                         lineup_groups, player_history_features, run_elo_init)
from machine_learning.feature_engineering.features import FEATURES, build_feature_matrix

log = logging.getLogger("ml.mechanisms")

INIT_ALPHA = [0.25, 0.5, 0.75, 1.0]
NEW_TEAM_GAMES = 20
RETURN_GAP_DAYS = 90
TURNOVER_CONT = 0.6          # today's lineup keeps at most 3 of 5 from the previous game
EXPERIENCED_NEW = np.log1p(50)

SKILL = ["wr_shr_diff", "gd15_shr_diff", "pelo_prev_diff", "lineup_elo_diff"]
PART = ["career_diff", "recent_diff"]
EXP = ["exp_log_diff"]

# name -> extra features on top of FEATURES (family, question)
FIXED_MODELS = {
    "form": ([], "base", "Published form model"),
    "exp": (EXP, "A", "Deployed: form + player experience"),
    "wr": (["wr_shr_diff"], "A", "form + shrunk player win rate"),
    "gd15": (["gd15_shr_diff"], "A", "form + lane gold lead at 15 min"),
    "pelo": (["pelo_prev_diff"], "A", "form + player Elo (previous lineup)"),
    "lineup_elo": (["lineup_elo_diff"], "A", "form + Elo of players' previous teams"),
    "career": (["career_diff"], "A", "form + career length"),
    "recent": (["recent_diff"], "A", "form + games in last 180 days"),
    "rel": (["exp_rel_diff"], "A", "form + experience relative to league peers"),
    "skill": (SKILL, "A", "form + all four skill measures"),
    "skill_exp": (SKILL + EXP, "A", "form + skill + experience"),
    "part": (PART, "A", "form + career + recent"),
    "part_exp": (PART + EXP, "A", "form + career + recent + experience"),
    "all_exp": (SKILL + PART + EXP, "A", "form + skill + participation + experience"),
    "all_noexp": (SKILL + PART, "A", "form + skill + participation"),
    "raw": (["exp_raw_diff"], "C", "raw game count"),
    "sqrt": (["exp_sqrt_diff"], "C", "square root of games"),
    "median": (["exp_median_diff"], "C", "median log games"),
    "min": (["exp_min_diff"], "C", "least experienced player"),
    "max": (["exp_max_diff"], "C", "most experienced player"),
    "mean_sd": (EXP + ["exp_sd_diff"], "C", "mean + dispersion"),
    "roles": ([f"role_{r}_diff" for r in ROLES], "C", "one experience feature per role"),
}
TUNED = {"sat": ([f"sat_{t}_diff" for t in SAT_T], "C", "diminishing returns 1-exp(-n/T), T on validation"),
         "decay": ([f"dec_{h}_diff" for h in DECAY_H], "C", "time-decayed games, half-life on validation")}

COMPARISONS = [  # (model, reference, family, question)
    ("exp", "form", "A", "Experience over form (replication)"),
    ("skill", "form", "A", "Skill measures over form"),
    ("skill_exp", "skill", "A", "H1: does experience add after skill?"),
    ("part_exp", "part", "A", "H2: does experience add after participation?"),
    ("all_exp", "all_noexp", "A", "H1+H2: experience after skill and participation"),
    ("exp", "skill", "A", "Experience alone vs four skill measures"),
    ("rel", "exp", "A", "Relative-to-league vs plain experience"),
    ("pelo", "form", "A", "Player Elo over form"),
    ("lineup_elo", "form", "A", "Previous-team Elo over form"),
    ("init", "form", "B", "Player-informed Elo start over form"),
    ("init_exp", "init", "B", "H3: does experience add after the player-informed start?"),
    ("init_exp", "exp", "B", "Player-informed start on top of experience"),
    ("sat", "exp", "C", "Diminishing returns vs log"),
    ("decay", "exp", "C", "Time decay vs log"),
    ("roles", "exp", "C", "Per-role vs mean"),
    ("mean_sd", "exp", "C", "Adding dispersion"),
    ("min", "exp", "C", "Weakest link vs mean"),
    ("median", "exp", "C", "Median vs mean"),
    ("raw", "exp", "C", "Raw count vs log"),
    ("sqrt", "exp", "C", "Square root vs log"),
    ("max", "exp", "C", "Most experienced vs mean"),
]
SUBGROUP_PAIRS = [("exp", "form"), ("skill_exp", "skill"), ("init", "form"), ("init_exp", "init")]


def add_relative(df: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    """exp_rel = exp_log minus the mean exp_log of the team's home league in the
    PREVIOUS calendar year (global previous-year mean when the league has none)."""
    rows = []
    for side in ("blue", "red"):
        rows.append(pd.DataFrame({"home": df[f"{side}_home"].values, "year": df["match_date"].dt.year.values,
                                  "exp": df[f"blue_exp_log" if side == "blue" else "red_exp_log"].values}))
    long = pd.concat(rows).dropna()
    lm = long.groupby(["home", "year"])["exp"].mean()
    gm = long.groupby("year")["exp"].mean()
    out = df.copy()
    for side in ("blue", "red"):
        key = list(zip(out[f"{side}_home"], out["match_date"].dt.year - 1))
        ref = pd.Series(lm.reindex(key).to_numpy())
        ref = ref.fillna(pd.Series(gm.reindex(out["match_date"].dt.year - 1).to_numpy()))
        out[f"{side}_exp_rel"] = out[f"{side}_exp_log"].to_numpy() - ref.to_numpy()
    out["exp_rel_diff"] = (out["blue_exp_rel"] - out["red_exp_rel"]).fillna(0.0)
    return out


def team_category(n_prior, succ, cur_exp, gap, cont) -> np.ndarray:
    cat = np.full(len(n_prior), "stable", dtype=object)
    new = n_prior < NEW_TEAM_GAMES
    cat[~new & (cont <= TURNOVER_CONT)] = "turnover"
    cat[~new & (gap >= RETURN_GAP_DAYS)] = "returning"
    cat[new] = np.where(succ[new] > 0, "new_successor",
                        np.where(cur_exp[new] >= EXPERIENCED_NEW, "new_experienced", "new_inexperienced"))
    return cat


def build_setting(s: H.Setting, matches, lu, lt, cache) -> pd.DataFrame:
    if s.elo not in cache:
        games, df = H.elo_frame(matches, s.elo)
        feats = player_history_features(lu, games)
        df = add_history_diffs(df, feats, diag=["exp_log", "cur_exp", "continuity", "gap_days", "successor"])
        df = add_relative(df, feats)
        cache[s.elo] = (games, df)
    games, df = cache[s.elo]
    df = df.copy()
    pe = run_player_elo(games, lt, PlayerEloConfig(k=s.player_elo[0], carryover_shrink=s.player_elo[1],
                                                   k_league=s.player_elo[2]))
    df["pelo_prev_diff"] = pe.set_index("source_game_id")["player_elo_prev_diff"].reindex(
        df["source_game_id"]).fillna(0.0).to_numpy()
    for side in ("blue", "red"):
        df[f"{side}_cat"] = team_category(df[f"{side}_n_prior"].to_numpy(), df[f"{side}_successor"].to_numpy(),
                                          df[f"{side}_cur_exp"].to_numpy(), df[f"{side}_gap_days"].fillna(0).to_numpy(),
                                          df[f"{side}_continuity"].to_numpy())
    return df


def init_features(s: H.Setting, matches, lu, alpha, df, cache) -> pd.Series:
    key = (s.elo, alpha)
    if key not in cache:
        from machine_learning.elo.elo import EloConfig
        g, _ = run_elo_init(matches, EloConfig(k=s.elo[0], carryover_shrink=s.elo[1], k_league=s.elo[2]), lu, alpha)
        fm = build_feature_matrix(g, matches).set_index("source_game_id")
        cache[key] = fm[FEATURES]
    return cache[key].reindex(df["source_game_id"]).reset_index(drop=True)


def run_setting(s, matches, lu, lt, cache, init_cache) -> dict:
    df = build_setting(s, matches, lu, lt, cache).reset_index(drop=True)
    tr, va, te = H.split_masks(df, s)
    log.info("%s: train %d, validation %d, test %d", s.name, tr.sum(), va.sum(), te.sum())
    preds, info = {}, {}
    for name, (extra, fam, _) in FIXED_MODELS.items():
        r = H.fit_select(df, FEATURES + extra, tr, va, te)
        preds[name], info[name] = r["p"], {k: r[k] for k in ("C", "val_log_loss", "coef", "intercept")}
    for name, (cands, fam, _) in TUNED.items():
        best = min((H.fit_select(df, FEATURES + [c], tr, va, te) | {"feat": c} for c in cands),
                   key=lambda r: r["val_log_loss"])
        preds[name] = best["p"]
        info[name] = {k: best[k] for k in ("C", "val_log_loss", "coef", "feat")}
    # player-informed Elo start: alpha on validation (form model refit with the new Elo features)
    best = None
    for a in INIT_ALPHA:
        d2 = df.copy()
        d2[FEATURES] = init_features(s, matches, lu, a, df, init_cache).to_numpy()
        r = H.fit_select(d2, FEATURES, tr, va, te)
        if best is None or r["val_log_loss"] < best[0]["val_log_loss"]:
            best = (r, a, d2)
    r, a, d2 = best
    preds["init"], info["init"] = r["p"], {"C": r["C"], "val_log_loss": r["val_log_loss"], "alpha": a}
    r2 = H.fit_select(d2, FEATURES + EXP, tr, va, te)
    preds["init_exp"], info["init_exp"] = r2["p"], {"C": r2["C"], "val_log_loss": r2["val_log_loss"], "alpha": a}

    t = df.loc[te].reset_index(drop=True)
    P = pd.DataFrame(preds)
    P["blue_won"], P["series"], P["setting"] = t["blue_won"].to_numpy(), t["series"].to_numpy(), s.name
    for c in ("blue_cat", "red_cat", "blue_n_prior", "red_n_prior", "blue_home", "red_home", "international",
              "match_date", "source_game_id"):
        P[c] = t[c].to_numpy()
    corr = df.loc[tr, EXP + SKILL + PART + ["exp_rel_diff", "elo_diff", "experience_diff"]].corr()
    return {"setting": s, "preds": P, "info": info,
            "periods": {k: {"n": int(m.sum()), "start": str(df.loc[m, "match_date"].min()),
                            "end": str(df.loc[m, "match_date"].max())} for k, m in
                        (("train", tr), ("validation", va), ("test", te))},
            "corr": corr.round(3).to_dict()}


def evaluate(P: pd.DataFrame, models) -> dict:
    y, cl = P["blue_won"].to_numpy(), P["series"].to_numpy()
    return {"metrics": {m: H.summarise(y, P[m].to_numpy()) for m in models},
            "comparisons": [{"model": a, "reference": b, "family": f, "question": q,
                             "brier": H.compare(y, P[a].to_numpy(), P[b].to_numpy(), cl),
                             "log_loss": H.compare(y, P[a].to_numpy(), P[b].to_numpy(), cl, "log_loss")}
                            for a, b, f, q in COMPARISONS]}


def subgroups(P: pd.DataFrame) -> list[dict]:
    order = ["new_successor", "new_experienced", "new_inexperienced", "returning", "turnover"]
    groups = {f"At least one team: {c}": (P["blue_cat"] == c) | (P["red_cat"] == c) for c in order}
    groups["Both teams stable"] = (P["blue_cat"] == "stable") & (P["red_cat"] == "stable")
    out = []
    for label, mask in groups.items():
        g = P[mask.to_numpy()]
        if len(g) < 100:
            out.append({"group": label, "n": int(len(g)), "note": "fewer than 100 games: not reported"})
            continue
        y, cl = g["blue_won"].to_numpy(), g["series"].to_numpy()
        out.append({"group": label, "n": int(len(g)),
                    "brier": {m: M.brier(y, g[m].to_numpy()) for m in ("form", "exp", "init", "init_exp")},
                    "comparisons": [{"model": a, "reference": b, **H.compare(y, g[a].to_numpy(), g[b].to_numpy(), cl)}
                                    for a, b in SUBGROUP_PAIRS]})
    return out


def run(processed: Path, raw: Path) -> dict:
    matches = pd.read_parquet(processed / "matches.parquet")
    pr = pd.read_parquet(processed / "player_rows.parquet")
    lu = lineup_groups(pr)
    lt = lineup_table(pr[["source_game_id", "team_key", "player_key", "match_date"]])
    cache, init_cache, results = {}, {}, []
    for s in H.settings():
        results.append(run_setting(s, matches, lu, lt, cache, init_cache))
    models = list(FIXED_MODELS) + list(TUNED) + ["init", "init_exp"]
    main = next(r for r in results if r["setting"].name == "main")
    wf = [r for r in results if r["setting"].name != "main"]
    pooled = pd.concat([r["preds"] for r in wf], ignore_index=True)
    per_window = []
    for r in wf:
        P = r["preds"]
        y, cl = P["blue_won"].to_numpy(), P["series"].to_numpy()
        per_window.append({"setting": r["setting"].name, "periods": r["periods"], "chosen": r["info"],
                           "brier": {m: M.brier(y, P[m].to_numpy()) for m in models},
                           "comparisons": [{"model": a, "reference": b,
                                            **H.compare(y, P[a].to_numpy(), P[b].to_numpy(), cl, n_boot=1000)}
                                           for a, b, _, _ in COMPARISONS]})
    pooled_eval = evaluate(pooled, models)
    for c in pooled_eval["comparisons"]:
        per = [next(x for x in w["comparisons"] if x["model"] == c["model"] and x["reference"] == c["reference"])
               for w in per_window]
        c["windows_better"] = sum(x["difference"] < 0 for x in per)
        c["windows_ci_below_zero"] = sum(x["ci95_high"] < 0 for x in per)
        c["windows_ci_above_zero"] = sum(x["ci95_low"] > 0 for x in per)
    # attenuation of the experience coefficient (main setting, standardised)
    att = {m: main["info"][m]["coef"].get("exp_log_diff") for m in ("exp", "skill_exp", "part_exp", "all_exp")}
    main_eval = evaluate(main["preds"], models)
    pooled.to_parquet(Path("/tmp") / "mechanisms_pooled_preds.parquet")
    main["preds"].to_parquet(Path("/tmp") / "mechanisms_main_preds.parquet")
    return {
        "data": H.data_record(raw),
        "design": {"hypotheses": ["H1 skill proxy", "H2 participation", "H3 cold start", "H4 measurement"],
                   "settings": [{"name": r["setting"].name, "elo": r["setting"].elo,
                                 "player_elo": r["setting"].player_elo, "periods": r["periods"]} for r in results],
                   "models": {k: {"extra": v[0], "family": v[1], "description": v[2]} for k, v in
                              {**FIXED_MODELS, **TUNED}.items()},
                   "init_alpha_grid": INIT_ALPHA, "sat_T": SAT_T, "decay_H": DECAY_H,
                   "categories": {"new_team_games": NEW_TEAM_GAMES, "return_gap_days": RETURN_GAP_DAYS,
                                  "turnover_continuity_max": TURNOVER_CONT,
                                  "experienced_new_mean_games": 50},
                   "bootstrap": {"unit": "series", "n_pooled": H.N_BOOT, "n_window": 1000, "seed": H.SEED},
                   "information": "all features use each team's previous lineup and earlier games; 'init' uses "
                                  "today's lineup at a team's first game (lineup-confirmed)"},
        "main": {"periods": main["periods"], "chosen": main["info"], **main_eval,
                 "experience_coefficient_per_sd": att, "train_correlations": main["corr"],
                 "subgroups": subgroups(main["preds"])},
        "walk_forward": {"n": int(len(pooled)), "windows": per_window, **pooled_eval,
                         "subgroups": subgroups(pooled),
                         "category_counts": pd.concat([pooled["blue_cat"], pooled["red_cat"]]).value_counts().to_dict()},
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    d = Path(os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--processed", type=Path, default=d / "processed" / "oracles_elixir")
    ap.add_argument("--raw", type=Path, default=d / "raw" / "oracles_elixir")
    a = ap.parse_args()
    print(registry.save(run(a.processed, a.raw), "mechanisms"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
