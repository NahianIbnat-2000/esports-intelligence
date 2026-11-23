"""League connectivity and league-rating uncertainty
(docs/LEAGUE_RATING_UNCERTAINTY.md).

1. Network. Nodes are home leagues (the league a team has played most
   domestic games in, from earlier games only, as in the Elo replay). An edge
   joins two leagues when teams from them met before the cutoff. Reported per
   calendar year and for the 24 months before the end of the test period.
2. Static league strength with uncertainty. On cross-league games in the 24
   months before the cutoff, a Bradley-Terry model with one strength per
   league and a blue-side intercept:
       logit P(blue wins) = b0 + theta[home_blue] - theta[home_red]
   fitted with a light ridge penalty (only fixes the scale for weakly linked
   leagues). 95% intervals: percentile bootstrap resampling whole series (500
   draws). Strengths are on the Elo scale (multiplied by 400 / ln 10) and
   centred on the mean of LCK and LPL. Like Elo league levels, theta describes
   how a league's REPRESENTATIVES did against other leagues' representatives,
   not the average team of the league.
3. Elo league levels at the cutoff under the configurations that the
   walk-forward windows chose and nearby k_league values (sensitivity, not a
   confidence interval).
4. Does weak connectivity hurt forecasts? Test games between teams from
   different leagues, split by how many cross-league games the two leagues
   had in the previous 365 days.

Usage: python -m machine_learning.experiments.league_uncertainty [--processed DIR] [--raw DIR]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression

from machine_learning.elo.elo import NO_LEAGUE, EloConfig, run_elo
from machine_learning.evaluation import metrics as M
from machine_learning.experiments import harness as H
from machine_learning.experiments import registry
from machine_learning.training.train import series_key

log = logging.getLogger("ml.league_uncertainty")

WINDOW_MONTHS = 24
N_BOOT = 500
RIDGE_C = 10.0
MIN_GAMES_TABLE = 30
SCALE = 400 / np.log(10)
SENS_K_LEAGUE = [8.0, 16.0, 32.0]
CONNECT_BINS = [0, 50, 200, np.inf]


def cross_games(g: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    x = g[(g["blue_home"] != g["red_home"]) & (g["blue_home"] != NO_LEAGUE) & (g["red_home"] != NO_LEAGUE)].copy()
    x["tournament_key"] = matches.set_index("source_game_id")["tournament_key"].reindex(x["source_game_id"]).to_numpy()
    x["series"] = series_key(x)
    return x


def network_stats(x: pd.DataFrame, leagues_active: set) -> dict:
    G = nx.Graph()
    G.add_nodes_from(leagues_active)
    for (a, b), n in x.groupby(["blue_home", "red_home"]).size().items():
        w = G[a][b]["weight"] + n if G.has_edge(a, b) else n
        G.add_edge(a, b, weight=w)
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    deg = {lg: int(G.degree(lg)) for lg in G}
    games = {lg: int(sum(d["weight"] for _, _, d in G.edges(lg, data=True))) for lg in G}
    return {"leagues": G.number_of_nodes(), "edges": G.number_of_edges(), "cross_games": int(len(x)),
            "components": len(comps), "largest_component": len(comps[0]) if comps else 0,
            "isolated_leagues": sorted(lg for lg in G if G.degree(lg) == 0),
            "small_components": [sorted(c) for c in comps[1:] if len(c) > 1],
            "per_league": {lg: {"opponent_leagues": deg[lg], "cross_games": games[lg],
                                "component": next(i for i, c in enumerate(comps) if lg in c)} for lg in G}}, G


def bradley_terry(x: pd.DataFrame, leagues: list[str], seed: int = 0) -> dict:
    idx = {lg: i for i, lg in enumerate(leagues)}
    X = np.zeros((len(x), len(leagues)))
    X[np.arange(len(x)), x["blue_home"].map(idx).to_numpy()] = 1.0
    X[np.arange(len(x)), x["red_home"].map(idx).to_numpy()] = -1.0
    y = x["blue_won"].to_numpy()
    anchor = [idx[a] for a in ("LCK", "LPL") if a in idx]

    def fit(Xb, yb):
        lr = LogisticRegression(C=RIDGE_C, max_iter=5000).fit(Xb, yb)
        th = lr.coef_[0] * SCALE
        return th - th[anchor].mean() if anchor else th - th.mean()

    theta = fit(X, y)
    codes, uniq = pd.factorize(x["series"])
    groups = [np.where(codes == k)[0] for k in range(len(uniq))]
    rng = np.random.default_rng(seed)
    boots = np.empty((N_BOOT, len(leagues)))
    for b in range(N_BOOT):
        pick = np.concatenate([groups[k] for k in rng.integers(0, len(groups), len(groups))])
        boots[b] = fit(X[pick], y[pick])
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    return {lg: {"strength": float(theta[i]), "ci95_low": float(lo[i]), "ci95_high": float(hi[i]),
                 "ci_width": float(hi[i] - lo[i])} for lg, i in idx.items()}


def run(processed: Path, raw: Path) -> dict:
    matches = pd.read_parquet(processed / "matches.parquet")
    s_main = H.settings()[0]
    g, st = run_elo(matches, EloConfig(k=s_main.elo[0], carryover_shrink=s_main.elo[1], k_league=s_main.elo[2]))
    _, df = H.elo_frame(matches, s_main.elo)
    tr, va, te = H.split_masks(df.reset_index(drop=True), s_main)
    cutoff = df.reset_index(drop=True).loc[te, "match_date"].max()
    x_all = cross_games(g, matches)
    year = x_all["match_date"].dt.year
    dom = g[g["blue_home"] == g["red_home"]]
    per_year = {}
    for Y in sorted(g["match_date"].dt.year.unique()):
        active = set(dom.loc[dom["match_date"].dt.year == Y, "blue_home"]) - {NO_LEAGUE}
        ns, _ = network_stats(x_all[year == Y], active)
        ns.pop("per_league")
        per_year[int(Y)] = ns

    start = cutoff - pd.DateOffset(months=WINDOW_MONTHS)
    xw = x_all[(x_all["match_date"] > start) & (x_all["match_date"] <= cutoff)]
    active = set(dom.loc[(dom["match_date"] > start) & (dom["match_date"] <= cutoff), "blue_home"]) - {NO_LEAGUE}
    net, G = network_stats(xw, active)
    main_comp = max(nx.connected_components(G), key=len)
    leagues_bt = sorted(lg for lg in main_comp if net["per_league"][lg]["cross_games"] > 0)
    xb = xw[xw["blue_home"].isin(leagues_bt) & xw["red_home"].isin(leagues_bt)]
    bt = bradley_terry(xb, leagues_bt)

    # Elo league levels at the cutoff under several configurations
    upto = matches[matches["match_date"] <= cutoff]
    configs = {f"published k={s_main.elo[0]}, shrink={s_main.elo[1]}, k_league={s_main.elo[2]}": s_main.elo}
    for s in H.settings()[1:]:
        configs.setdefault(f"walk-forward choice k={s.elo[0]}, shrink={s.elo[1]}, k_league={s.elo[2]}", s.elo)
    for kl in SENS_K_LEAGUE:
        configs.setdefault(f"sensitivity k={s_main.elo[0]}, shrink={s_main.elo[1]}, k_league={kl}",
                           (s_main.elo[0], s_main.elo[1], kl))
    levels = {}
    for lab, c in configs.items():
        _, stc = run_elo(upto, EloConfig(k=c[0], carryover_shrink=c[1], k_league=c[2]))
        ref = np.mean([stc.L(a) for a in ("LCK", "LPL")])
        levels[lab] = {lg: float(stc.L(lg) - ref) for lg in leagues_bt}
    pub = next(iter(levels))
    table = []
    for lg in leagues_bt:
        vals = [levels[k][lg] for k in levels]
        n = net["per_league"][lg]["cross_games"]
        table.append({"league": lg, "cross_games_24m": n, "opponent_leagues_24m": net["per_league"][lg]["opponent_leagues"],
                      "bt_strength": bt[lg]["strength"], "bt_ci95": [bt[lg]["ci95_low"], bt[lg]["ci95_high"]],
                      "bt_ci_width": bt[lg]["ci_width"], "elo_level_published": levels[pub][lg],
                      "elo_level_range_across_configs": [min(vals), max(vals)],
                      "warning": "few cross-league games" if n < MIN_GAMES_TABLE else
                      ("wide interval" if bt[lg]["ci_width"] > 200 else None)})
    table.sort(key=lambda r: -r["bt_strength"])
    well = [r for r in table if r["cross_games_24m"] >= MIN_GAMES_TABLE]
    rho = spearmanr([r["bt_strength"] for r in well], [r["elo_level_published"] for r in well])
    width_vs_games = spearmanr([r["cross_games_24m"] for r in table], [r["bt_ci_width"] for r in table])

    # connectivity and forecast quality on test games between leagues
    mp = pd.read_parquet("/tmp/mechanisms_main_preds.parquet") if Path("/tmp/mechanisms_main_preds.parquet").exists() else None
    conn = None
    if mp is not None:
        xs = x_all.sort_values("match_date")
        cg = []
        for _, r in mp[(mp["blue_home"] != mp["red_home"])].iterrows():
            w0 = r["match_date"] - pd.Timedelta(days=365)
            past = xs[(xs["match_date"] < r["match_date"]) & (xs["match_date"] >= w0)]
            cnt = [int(((past["blue_home"] == lg) | (past["red_home"] == lg)).sum()) for lg in (r["blue_home"], r["red_home"])]
            cg.append((r.name, min(cnt)))
        cgs = pd.Series(dict(cg))
        sub = mp.loc[cgs.index].copy()
        sub["min_cross_games_365d"] = cgs
        sub["bin"] = pd.cut(sub["min_cross_games_365d"], CONNECT_BINS, right=False)
        conn = []
        for b, gg in sub.groupby("bin", observed=True):
            if len(gg) < 30:
                continue
            y = gg["blue_won"].to_numpy()
            conn.append({"bin": str(b), "n": int(len(gg)), "brier_form": M.brier(y, gg["form"].to_numpy()),
                         "brier_exp": M.brier(y, gg["exp"].to_numpy()),
                         "mean_forecast_exp": float(gg["exp"].mean()), "blue_win_rate": float(y.mean()),
                         "exp_vs_form": H.compare(y, gg["exp"].to_numpy(), gg["form"].to_numpy(), gg["series"].to_numpy())})
    return {"data": H.data_record(raw),
            "design": {"window_months": WINDOW_MONTHS, "cutoff": str(cutoff), "ridge_C": RIDGE_C, "n_boot": N_BOOT,
                       "bootstrap_unit": "series", "scale": "Elo points (400/ln 10 per logit), 0 = mean of LCK and LPL",
                       "min_games_table": MIN_GAMES_TABLE, "elo_configs": {k: list(v) for k, v in configs.items()}},
            "per_year": per_year, "window_network": {k: v for k, v in net.items()},
            "league_table": table,
            "spearman_bt_vs_elo_wellconnected": {"rho": float(rho.statistic), "p": float(rho.pvalue), "n": len(well)},
            "spearman_games_vs_ci_width": {"rho": float(width_vs_games.statistic), "n": len(table)},
            "connectivity_and_forecasts": conn}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    d = Path(os.environ.get("DATA_DIR", "data"))
    ap.add_argument("--processed", type=Path, default=d / "processed" / "oracles_elixir")
    ap.add_argument("--raw", type=Path, default=d / "raw" / "oracles_elixir")
    a = ap.parse_args()
    print(registry.save(run(a.processed, a.raw), "league-uncertainty"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
