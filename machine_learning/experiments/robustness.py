"""Robustness and sensitivity checks (docs/ROBUSTNESS_AND_SENSITIVITY.md).

1. Forecast information contracts
   pre-series   every feature frozen at the first game of the series (state
                before the series starts; previous lineup). Usable the day
                before. Later games of a series reuse game 1's features,
                with the sign flipped when the teams swap sides.
   pre-game     the published contract: state after every earlier game,
                including earlier games of the same series.
   lineup       pre-game + today's lineup (player_exp_diff of the five who
                play). Known at the draft, not before.
   Each contract is trained and tested on its own information, so models
   inside one contract are compared on equal information.
2. Series reconstruction: the published key (tournament, team pair, UTC day)
   against a gap rule (same tournament and pair, less than 6 hours since the
   previous game) and against the source's game_in_series column.
3. Bootstrap sensitivity: the same comparisons with different resampling
   units (game, series, gap-rule series, tournament, calendar week, month).
4. Multiple comparisons: Holm and Bonferroni over all pooled walk-forward
   comparisons, using standard errors from the published intervals.
5. Temporal: expanding vs rolling (last 2 years) training; a model frozen
   after 2021 vs yearly refits; calibration slope and intercept by test year.

Usage: python -m machine_learning.experiments.robustness [--processed DIR] [--raw DIR]
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
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression

from machine_learning.evaluation import metrics as M
from machine_learning.experiments import harness as H
from machine_learning.experiments import registry
from machine_learning.experiments.lineups import add_roster_diffs, lineup_table, roster_features
from machine_learning.feature_engineering.features import FEATURES

log = logging.getLogger("ml.robustness")

GAP_HOURS = 6
EXP_PREV, EXP_TODAY = "player_exp_prev_diff", "player_exp_diff"
ROLLING_YEARS = 2


def gap_series(df: pd.DataFrame) -> pd.Series:
    """Series id by gap rule: same tournament and team pair, < GAP_HOURS since the previous game."""
    a = df[["blue_team_key", "red_team_key"]].min(axis=1)
    b = df[["blue_team_key", "red_team_key"]].max(axis=1)
    d = pd.DataFrame({"t": df["tournament_key"].astype(str), "a": a, "b": b, "ts": df["match_date"]},
                     index=df.index).sort_values("ts")
    new = d.groupby(["t", "a", "b"])["ts"].diff().gt(pd.Timedelta(hours=GAP_HOURS)) | \
        d.groupby(["t", "a", "b"])["ts"].diff().isna()
    sid = new.astype(int).groupby([d["t"], d["a"], d["b"]]).cumsum()
    key = d["t"] + "|" + d["a"] + "|" + d["b"] + "|" + sid.astype(str)
    return key.reindex(df.index)


def series_audit(df: pd.DataFrame, matches: pd.DataFrame) -> dict:
    gs = gap_series(df)
    pub = df["series"]
    by_pub, by_gap = pub.nunique(), gs.nunique()
    pg = pd.DataFrame({"p": pub.to_numpy(), "g": gs.to_numpy()})
    split_pub = int(pg.groupby("g")["p"].nunique().gt(1).sum())   # gap-series split over >1 published series
    merged = int(pg.groupby("p")["g"].nunique().gt(1).sum())      # published series containing >1 gap-series
    gis = matches.set_index("source_game_id")["game_in_series"].reindex(df["source_game_id"]).to_numpy()
    d = pd.DataFrame({"series": pub.to_numpy(), "ts": df["match_date"].to_numpy(), "gis": gis})
    d = d.sort_values(["series", "ts"])
    d["order"] = d.groupby("series").cumcount() + 1
    known = d["gis"].notna()
    return {"games": int(len(df)), "series_published_key": int(by_pub), "series_gap_rule": int(by_gap),
            "gap_series_split_across_utc_days": split_pub, "published_series_with_two_gap_series": merged,
            "games_with_source_game_in_series": int(known.sum()),
            "share_order_matches_source": float((d.loc[known, "order"] == d.loc[known, "gis"]).mean()),
            "series_size_distribution": d.groupby("series").size().value_counts().sort_index().to_dict()}


def pre_series(df: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    """Replace feats by game-1-of-series values, oriented to each game's blue side."""
    out = df.copy()
    o = out.sort_values("match_date")
    first = o.groupby("series").head(1).set_index("series")
    f1 = first.reindex(out["series"])
    sign = np.where(f1["blue_team_key"].to_numpy() == out["blue_team_key"].to_numpy(), 1.0, -1.0)
    for c in feats:
        out[c] = sign * f1[c].to_numpy()
    out["game_number_in_series"] = o.groupby("series").cumcount().reindex(out.index) + 1
    return out


def calib_slope(y, p) -> dict:
    lp = np.log(np.clip(p, 1e-9, 1 - 1e-9) / np.clip(1 - p, 1e-9, 1))
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(lp.reshape(-1, 1), y)
    return {"slope": float(lr.coef_[0, 0]), "intercept": float(lr.intercept_[0]),
            "ece": float(M.expected_calibration_error(y, p))}


def clusters_for(t: pd.DataFrame) -> dict:
    wk = t["match_date"].dt.tz_convert(None) if t["match_date"].dt.tz is not None else t["match_date"]
    return {"game": np.arange(len(t)), "series (published)": t["series"].to_numpy(),
            "series (6-hour gap rule)": t["gap_series"].to_numpy(),
            "tournament": t["tournament_key"].astype(str).to_numpy(),
            "calendar week": wk.dt.strftime("%G-%V").to_numpy(),
            "calendar month": wk.dt.strftime("%Y-%m").to_numpy()}


def run(processed: Path, raw: Path) -> dict:
    matches = pd.read_parquet(processed / "matches.parquet")
    pr = pd.read_parquet(processed / "player_rows.parquet", columns=["source_game_id", "team_key", "player_key",
                                                                    "match_date"])
    roster = roster_features(lineup_table(pr))
    cache = {}
    contracts = {"pre-series": None, "pre-game": None, "lineup": None}
    models = {"elo_cal": ["elo_diff"], "form": FEATURES, "exp": FEATURES + [EXP_PREV]}
    lineup_models = {"exp_today": FEATURES + [EXP_TODAY], "exp_both": FEATURES + [EXP_PREV, EXP_TODAY]}
    out_settings, pooled = [], []
    audit = None
    for s in H.settings():
        if s.elo not in cache:
            _, df = H.elo_frame(matches, s.elo)
            df = add_roster_diffs(df, roster).reset_index(drop=True)
            df["gap_series"] = gap_series(df)
            cache[s.elo] = df
        df = cache[s.elo]
        tr, va, te = H.split_masks(df, s)
        if s.name == "main":
            audit = series_audit(df, matches)
        ps = pre_series(df, FEATURES + [EXP_PREV])
        P = pd.DataFrame(index=np.where(te)[0])
        info = {}
        for name, feats in models.items():
            for tag, frame in (("pre-game", df), ("pre-series", ps)):
                r = H.fit_select(frame, feats, tr, va, te)
                P[f"{name}|{tag}"] = r["p"]
                info[f"{name}|{tag}"] = r["C"]
        for name, feats in lineup_models.items():
            r = H.fit_select(df, feats, tr, va, te)
            P[f"{name}|lineup"] = r["p"]
            info[f"{name}|lineup"] = r["C"]
        # temporal: rolling training window (last ROLLING_YEARS years of train)
        if s.name != "main":
            Y = s.test_year
            roll = tr & (df["match_date"].dt.year >= Y - 1 - ROLLING_YEARS)
            for name in ("form", "exp"):
                r = H.fit_select(df, models[name], roll, va, te)
                P[f"{name}|rolling"] = r["p"]
        t = df.loc[te].reset_index(drop=True)
        P = P.reset_index(drop=True)
        for c in ("blue_won", "series", "gap_series", "tournament_key", "match_date", "international",
                  "source_game_id"):
            P[c] = t[c].to_numpy()
        P["game_number_in_series"] = ps.loc[te, "game_number_in_series"].to_numpy()
        P["setting"] = s.name
        out_settings.append({"setting": s.name, "C": info})
        pooled.append(P)

    main = pooled[0]
    wf = pd.concat(pooled[1:], ignore_index=True)

    def contract_table(P):
        y, cl = P["blue_won"].to_numpy(), P["series"].to_numpy()
        cols = [c for c in P.columns if "|" in c]
        res = {"metrics": {c: H.summarise(y, P[c].to_numpy()) for c in cols}, "comparisons": []}
        pairs = [("exp|pre-series", "form|pre-series", "Experience over form, pre-series"),
                 ("form|pre-series", "elo_cal|pre-series", "Form over calibrated Elo, pre-series"),
                 ("exp|pre-game", "form|pre-game", "Experience over form, pre-game (published)"),
                 ("form|pre-game", "elo_cal|pre-game", "Form over calibrated Elo, pre-game (published)"),
                 ("elo_cal|pre-game", "elo_cal|pre-series", "Value of in-series updates, calibrated Elo"),
                 ("exp|pre-game", "exp|pre-series", "Value of in-series updates, experience model"),
                 ("exp_today|lineup", "exp|pre-game", "Today's lineup instead of previous lineup"),
                 ("exp_both|lineup", "exp|pre-game", "Today's lineup in addition to previous lineup")]
        if "form|rolling" in P:
            pairs += [("form|rolling", "form|pre-game", "Rolling 2-year training vs expanding, form"),
                      ("exp|rolling", "exp|pre-game", "Rolling 2-year training vs expanding, experience")]
        for a, b, q in pairs:
            res["comparisons"].append({"model": a, "reference": b, "question": q,
                                       "brier": H.compare(y, P[a].to_numpy(), P[b].to_numpy(), cl)})
        # pre-series vs pre-game on later games only (game 1 is identical by construction)
        later = P["game_number_in_series"] > 1
        g = P[later]
        res["later_games_only"] = {"n": int(later.sum()), "comparisons": [
            {"model": a, "reference": b,
             "brier": H.compare(g["blue_won"].to_numpy(), g[a].to_numpy(), g[b].to_numpy(), g["series"].to_numpy())}
            for a, b in (("elo_cal|pre-game", "elo_cal|pre-series"), ("exp|pre-game", "exp|pre-series"),
                         ("exp|pre-series", "form|pre-series"))]}
        return res

    # bootstrap sensitivity
    def boot_table(P, pairs):
        rows = []
        cl = clusters_for(P)
        y = P["blue_won"].to_numpy()
        for a, b, q in pairs:
            for unit, c in cl.items():
                d, se = H.cluster_se(y, P[a].to_numpy(), P[b].to_numpy(), c)
                r = H.compare(y, P[a].to_numpy(), P[b].to_numpy(), c)
                rows.append({"comparison": q, "unit": unit, "n_units": int(pd.Series(c).nunique()),
                             "difference": d, "se": se, "ci95_low": r["ci95_low"], "ci95_high": r["ci95_high"]})
        return rows

    bpairs = [("exp|pre-game", "form|pre-game", "Experience over form"),
              ("form|pre-game", "elo_cal|pre-game", "Form over calibrated Elo")]

    # temporal: frozen 2021 model applied to later years vs yearly refits
    frozen = []
    df0 = cache[next(s for s in H.settings() if s.name == "wf2022").elo]
    s22 = next(s for s in H.settings() if s.name == "wf2022")
    tr22, va22, _ = H.split_masks(df0, s22)
    for name in ("form", "exp"):
        r = H.fit_select(df0, models[name], tr22, va22, va22)   # fit on data to end of 2021
        from machine_learning.experiments.harness import fit_lr
        m_frozen = fit_lr(df0.loc[tr22 | va22, models[name]], df0.loc[tr22 | va22, "blue_won"], r["C"])
        for s in H.settings():
            if s.name in ("main", "wf2022"):
                continue
            d = cache[s.elo]
            _, _, te = H.split_masks(d, s)
            # frozen model uses features from this window's Elo config (ratings keep updating;
            # only the logistic coefficients are frozen)
            pf = m_frozen.predict_proba(d.loc[te, models[name]])[:, 1]
            P = next(p for p in pooled if p["setting"].iloc[0] == s.name)
            y = P["blue_won"].to_numpy()
            frozen.append({"model": name, "test_year": s.test_year,
                           "brier_frozen_2021": M.brier(y, pf), "brier_yearly_refit": M.brier(y, P[f"{name}|pre-game"]),
                           "difference": H.compare(y, P[f"{name}|pre-game"].to_numpy(), pf, P["series"].to_numpy())})

    calib = [{"test_year": int(P["match_date"].dt.year.iloc[0]) if P["setting"].iloc[0] != "main" else None,
              "setting": P["setting"].iloc[0],
              **{m: calib_slope(P["blue_won"].to_numpy(), P[f"{m}|pre-game"].to_numpy()) for m in ("elo_cal", "exp")}}
             for P in pooled]

    intl = {}
    for lab, mask in (("international", wf["international"].astype(bool)), ("domestic", ~wf["international"].astype(bool))):
        g = wf[mask.to_numpy()]
        intl[lab] = {"n": int(len(g)), "exp_vs_form": H.compare(g["blue_won"].to_numpy(), g["exp|pre-game"].to_numpy(),
                                                                g["form|pre-game"].to_numpy(), g["series"].to_numpy())}

    main.to_parquet("/tmp/robust_main_preds.parquet")
    wf.to_parquet("/tmp/robust_wf_preds.parquet")
    return {"data": H.data_record(raw),
            "design": {"contracts": ["pre-series", "pre-game", "lineup"], "gap_hours": GAP_HOURS,
                       "rolling_years": ROLLING_YEARS, "bootstrap": {"n": H.N_BOOT, "seed": H.SEED}},
            "settings": out_settings, "series_audit": audit,
            "contracts": {"main": contract_table(main), "walk_forward": contract_table(wf)},
            "bootstrap_sensitivity": {"main": boot_table(main, bpairs), "walk_forward": boot_table(wf, bpairs)},
            "frozen_vs_refit": frozen, "calibration_by_window": calib, "international_vs_domestic": intl,
            "multiple_comparisons": multiple_comparisons()}


def holm(p: np.ndarray) -> np.ndarray:
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run_max = 0.0
    for rank, i in enumerate(order):
        run_max = max(run_max, min(1.0, (m - rank) * p[i]))
        adj[i] = run_max
    return adj


def multiple_comparisons(mech_record: Path | None = None) -> dict:
    """Holm and Bonferroni over every pooled comparison already reported.
    z = difference / SE, SE = (CI high - CI low) / (2 * 1.96) from the stored
    percentile intervals (an approximation; documented)."""
    wf = json.loads(H.WF_RECORD.read_text())
    rows = []
    for c in wf["pooled"]["comparisons"]:
        for metric in ("brier", "log_loss"):
            r = c[metric]
            rows.append({"source": "walk-forward (published)", "comparison": f"{c['model']} vs {c['reference']}",
                         "metric": metric, "difference": r["difference"], "lo": r["ci95_low"], "hi": r["ci95_high"]})
    for sg in wf["subgroups"]:
        for c in sg["comparisons"]:
            rows.append({"source": "walk-forward subgroups (published)",
                         "comparison": f"{c['model']} vs {c['reference']} | {sg['group']}", "metric": "brier",
                         "difference": c["difference"], "lo": c["ci95_low"], "hi": c["ci95_high"]})
    if mech_record is None:
        found = sorted(registry.REGISTRY_DIR.glob("mechanisms-*.json"))
        mech_record = found[-1] if found else None
    if mech_record:
        mr = json.loads(mech_record.read_text())
        for c in mr["walk_forward"]["comparisons"]:
            r = c["brier"]
            rows.append({"source": "mechanisms (new)", "comparison": f"{c['model']} vs {c['reference']}",
                         "metric": "brier", "difference": r["difference"], "lo": r["ci95_low"], "hi": r["ci95_high"]})
    d = pd.DataFrame(rows)
    se = (d["hi"] - d["lo"]) / (2 * 1.96)
    d["z"] = d["difference"] / se
    d["p"] = 2 * norm.sf(np.abs(d["z"]))
    d["p_holm"] = holm(d["p"].to_numpy())
    d["p_bonferroni"] = np.minimum(1.0, d["p"] * len(d))
    d["nominal_ci_excludes_zero"] = (d["hi"] < 0) | (d["lo"] > 0)
    return {"n_tests": int(len(d)), "nominal_significant": int(d["nominal_ci_excludes_zero"].sum()),
            "holm_significant_5pct": int((d["p_holm"] < 0.05).sum()),
            "bonferroni_significant_5pct": int((d["p_bonferroni"] < 0.05).sum()),
            "rows": d.round(8).to_dict(orient="records")}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    d = Path(os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--processed", type=Path, default=d / "processed" / "oracles_elixir")
    ap.add_argument("--raw", type=Path, default=d / "raw" / "oracles_elixir")
    a = ap.parse_args()
    print(registry.save(run(a.processed, a.raw), "robustness"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
