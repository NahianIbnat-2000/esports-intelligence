"""Compute research outputs from the processed dataset and the Elo history,
and store them in analysis_outputs. Every payload records its definition,
sample period and sample size. Nothing is produced when inputs are missing.

Usage:  python -m analytics.run_all
"""
from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sqlalchemy import delete, select

from analytics.economics.concentration import (gini, hhi, hhi_normalised, lorenz_curve, noll_scully,
                                               wilson_interval)
from backend.app.core.jsonutil import jsonable as _jsonable
from backend.app.database.session import get_sessionmaker
from backend.app.models import AnalysisOutput, EloRating, Game, Match, ModelVersion, Team
from pipelines.oracle_elixir.config import PROCESSED_DIR

log = logging.getLogger("analytics")
MIN_TEAM_GAMES = 5


def _period(df: pd.DataFrame, col: str = "match_date") -> dict:
    return {"start": str(df[col].min()), "end": str(df[col].max())} if len(df) else {"start": None, "end": None}


def competitive_balance(m: pd.DataFrame, teams: pd.DataFrame) -> dict:
    """Regular-season balance per tournament (league + year + split)."""
    rs = m[~m["playoffs"].fillna(False).astype(bool) & ~m["international"]]
    long = pd.concat([
        rs[["tournament_key", "blue_team_key", "winner_team_key"]].rename(columns={"blue_team_key": "team"}),
        rs[["tournament_key", "red_team_key", "winner_team_key"]].rename(columns={"red_team_key": "team"})])
    long["win"] = (long["team"] == long["winner_team_key"]).astype(int)
    per = long.groupby(["tournament_key", "team"]).agg(games=("win", "size"), wins=("win", "sum")).reset_index()
    per = per[per["games"] >= MIN_TEAM_GAMES]
    meta = m.groupby("tournament_key").agg(league=("league", "first"), year=("year", "first"),
                                          split=("split", "first"), start=("match_date", "min"))
    rows = []
    for key, g in per.groupby("tournament_key"):
        if len(g) < 4:
            continue
        wp = g["wins"] / g["games"]
        lor = lorenz_curve(g["wins"])
        rows.append({"tournament_key": key, "league": meta.loc[key, "league"], "year": int(meta.loc[key, "year"]),
                     "lorenz_wins": lor,
                     "split": meta.loc[key, "split"], "start": str(meta.loc[key, "start"]),
                     "n_teams": int(len(g)), "n_games": int(g["games"].sum() // 2),
                     "noll_scully": noll_scully(wp, g["games"]),
                     "gini_wins": gini(g["wins"]), "hhi_win_share": hhi(g["wins"]),
                     "hhi_win_share_normalised": hhi_normalised(g["wins"]),
                     "top_team_win_pct": float(wp.max()), "bottom_team_win_pct": float(wp.min())})
    df = pd.DataFrame(rows)
    by_year = []
    if len(df):
        for y, g in df.groupby("year"):
            by_year.append({"year": int(y), "n_tournaments": int(len(g)),
                            "median_noll_scully": float(g["noll_scully"].median()),
                            "median_gini_wins": float(g["gini_wins"].median())})
    by_league_year = []
    if len(df):
        for (lg, y), g in df.groupby(["league", "year"]):
            by_league_year.append({"league": lg, "year": int(y), "n_splits": int(len(g)),
                                   "noll_scully": float(g["noll_scully"].mean()),
                                   "gini_wins": float(g["gini_wins"].mean()),
                                   "hhi_win_share_normalised": float(g["hhi_win_share_normalised"].mean()),
                                   "n_teams": float(g["n_teams"].mean())})
    return {
        "by_league_year": by_league_year,
        "definition": "Regular-season games only (playoffs and international events excluded). Teams with fewer "
                      f"than {MIN_TEAM_GAMES} games in a tournament are left out; tournaments with fewer than 4 "
                      "such teams are left out. Concentrated quantity: each team's share of all regular-season "
                      "wins in the tournament. Noll-Scully = sd(win%) / (0.5/sqrt(mean games)).",
        "sample_period": _period(rs), "n_tournaments": int(len(df)),
        "tournaments": df.sort_values("start").to_dict("records") if len(df) else [], "by_year": by_year}


def title_concentration(m: pd.DataFrame, tournaments: pd.DataFrame, teams: pd.DataFrame) -> dict:
    t = tournaments[tournaments["derived_champion_team_key"].notna()]
    name = teams.set_index("team_key")["name"]
    rows = []
    for league, g in t.groupby("league"):
        if len(g) < 4:
            continue
        counts = g["derived_champion_team_key"].value_counts()
        rows.append({"league": league, "n_tournaments_with_champion": int(len(g)),
                     "first_year": int(g["year"].min()), "last_year": int(g["year"].max()),
                     "distinct_champions": int(len(counts)), "hhi_titles": hhi(counts.values),
                     "top_team": name.get(counts.index[0]), "top_team_titles": int(counts.iloc[0]),
                     "top_team_share": float(counts.iloc[0] / counts.sum()),
                     "lorenz": lorenz_curve(counts.values)})
    return {"definition": "Concentrated quantity: derived titles, i.e. the winner of the chronologically last "
                          "playoff game of each league split. Only leagues with at least 4 such tournaments. "
                          "This is derived from game records, not an official title register; HHI over title "
                          "holders ignores teams that never won, so it describes how titles are shared among "
                          "winners only.",
            "sample_period": _period(m), "leagues": sorted(rows, key=lambda r: -r["n_tournaments_with_champion"])}


def persistence(m: pd.DataFrame) -> dict:
    rs = m[~m["playoffs"].fillna(False).astype(bool) & ~m["international"]]
    long = pd.concat([
        rs[["tournament_key", "league", "match_date", "blue_team_key", "winner_team_key"]]
        .rename(columns={"blue_team_key": "team"}),
        rs[["tournament_key", "league", "match_date", "red_team_key", "winner_team_key"]]
        .rename(columns={"red_team_key": "team"})])
    long["win"] = (long["team"] == long["winner_team_key"]).astype(int)
    per = long.groupby(["league", "tournament_key", "team"]).agg(games=("win", "size"), wp=("win", "mean"),
                                                                start=("match_date", "min")).reset_index()
    per = per[per["games"] >= MIN_TEAM_GAMES]
    order = per.groupby(["league", "tournament_key"])["start"].min().reset_index().sort_values("start")
    pairs = []
    for league, g in order.groupby("league"):
        keys = g["tournament_key"].tolist()
        for a, b in zip(keys, keys[1:]):
            pa = per[per["tournament_key"] == a].set_index("team")["wp"]
            pb = per[per["tournament_key"] == b].set_index("team")["wp"]
            common = pa.index.intersection(pb.index)
            for team in common:
                pairs.append({"league": league, "from": a, "to": b, "wp_t": pa[team], "wp_t1": pb[team]})
    df = pd.DataFrame(pairs)
    if len(df) < 20:
        return {"definition": "Persistence of team strength", "available": False,
                "reason": "fewer than 20 team pairs in consecutive splits", "n_pairs": int(len(df))}
    slope = float(np.polyfit(df["wp_t"], df["wp_t1"], 1)[0])
    sample = df.sample(min(len(df), 600), random_state=0)
    return {"definition": "Regular-season win % of the same team (same team id) in consecutive splits of the "
                          "same league. Pearson and Spearman correlation and OLS slope of win% t+1 on win% t. "
                          "A slope below 1 indicates regression toward 0.5.",
            "available": True, "sample_period": _period(rs), "n_pairs": int(len(df)),
            "pearson": float(df["wp_t"].corr(df["wp_t1"])),
            "spearman": float(df["wp_t"].corr(df["wp_t1"], method="spearman")), "ols_slope": slope,
            "scatter_sample": sample[["league", "wp_t", "wp_t1"]].round(4).to_dict("records")}


def placements(m: pd.DataFrame, tournaments: pd.DataFrame, teams: pd.DataFrame) -> dict:
    """Regular-season rank of each derived champion: how often does the best
    regular-season team win the title?"""
    rs = m[~m["playoffs"].fillna(False).astype(bool) & ~m["international"]]
    long = pd.concat([
        rs[["tournament_key", "blue_team_key", "winner_team_key"]].rename(columns={"blue_team_key": "team"}),
        rs[["tournament_key", "red_team_key", "winner_team_key"]].rename(columns={"red_team_key": "team"})])
    long["win"] = (long["team"] == long["winner_team_key"]).astype(int)
    per = long.groupby(["tournament_key", "team"]).agg(games=("win", "size"), wp=("win", "mean")).reset_index()
    per = per[per["games"] >= MIN_TEAM_GAMES]
    per["rank"] = per.groupby("tournament_key")["wp"].rank(ascending=False, method="min")
    champs = tournaments[tournaments["derived_champion_team_key"].notna()][["tournament_key", "league",
                                                                           "derived_champion_team_key"]]
    j = champs.merge(per, left_on=["tournament_key", "derived_champion_team_key"],
                     right_on=["tournament_key", "team"], how="inner")
    if len(j) < 20:
        return {"available": False, "reason": "fewer than 20 champions with a regular season in the data"}
    dist = j["rank"].clip(upper=6).value_counts().sort_index()
    return {"available": True,
            "definition": "Regular-season rank (by game win %, ties share the better rank) of the derived champion "
                          "of each split with both a regular season and playoffs in the data. Rank 6 = 6th or lower.",
            "n_splits": int(len(j)),
            "share_rs_first_wins_title": float((j["rank"] == 1).mean()),
            "distribution": [{"rank": ("6+" if int(r) == 6 else str(int(r))), "splits": int(n),
                              "share": float(n / len(j))} for r, n in dist.items()],
            "by_league": [{"league": lg, "splits": int(len(g)), "share_rs_first_wins_title": float((g["rank"] == 1).mean())}
                          for lg, g in j.groupby("league") if len(g) >= 8]}


def team_consistency(m: pd.DataFrame, teams: pd.DataFrame) -> dict:
    """Mean and standard deviation of regular-season win % across splits."""
    rs = m[~m["playoffs"].fillna(False).astype(bool) & ~m["international"]]
    long = pd.concat([
        rs[["tournament_key", "blue_team_key", "winner_team_key"]].rename(columns={"blue_team_key": "team"}),
        rs[["tournament_key", "red_team_key", "winner_team_key"]].rename(columns={"red_team_key": "team"})])
    long["win"] = (long["team"] == long["winner_team_key"]).astype(int)
    per = long.groupby(["team", "tournament_key"]).agg(games=("win", "size"), wp=("win", "mean")).reset_index()
    per = per[per["games"] >= MIN_TEAM_GAMES]
    agg = per.groupby("team").agg(splits=("wp", "size"), mean_wp=("wp", "mean"), sd_wp=("wp", "std")).reset_index()
    agg = agg[agg["splits"] >= 6]
    info = teams.set_index("team_key")
    agg["name"] = agg["team"].map(info["name"])
    agg["slug"] = agg["team"].map(info["slug"])
    agg["league"] = agg["team"].map(info["primary_league"])
    sample = agg.sort_values("splits", ascending=False).head(400)
    return {"definition": "Teams with at least 6 regular-season splits of 5+ games. Mean and standard deviation "
                          "of split win %. A low standard deviation at a high mean = consistently strong.",
            "n_teams": int(len(agg)),
            "teams": sample[["name", "slug", "league", "splits", "mean_wp", "sd_wp"]].round(4).to_dict("records")}


def season_trends(m: pd.DataFrame) -> dict:
    long = pd.concat([
        m[["match_date", "tournament_key", "blue_team_key", "winner_team_key"]].rename(columns={"blue_team_key": "team"}),
        m[["match_date", "tournament_key", "red_team_key", "winner_team_key"]].rename(columns={"red_team_key": "team"})])
    long["win"] = (long["team"] == long["winner_team_key"]).astype(int)
    long["year"] = long["match_date"].dt.year
    rows = []
    for y, g in long.groupby("year"):
        per = g.groupby("team").agg(games=("win", "size"), wp=("win", "mean"))
        per20 = per[per["games"] >= 20]["wp"]
        q = per20.quantile([0.1, 0.25, 0.5, 0.75, 0.9]) if len(per20) else None
        rows.append({"year": int(y), "games": int(len(g) // 2), "active_teams": int(len(per)),
                     "teams_20plus_games": int(len(per20)), "tournaments": int(g["tournament_key"].nunique()),
                     **({f"wp_p{int(k * 100)}": float(v) for k, v in q.items()} if q is not None else {})})
    return {"definition": "Calendar years. Active team = at least one game in the year. Win % quantiles across "
                          "teams with 20+ games that year (a wide spread = unequal results).",
            "by_year": rows}


def side_advantage(m: pd.DataFrame) -> dict:
    rows = []
    # calendar year of the game (the source `year` is a season label and can
    # differ, e.g. qualifiers played in the autumn for the next season)
    for y, g in m.groupby(m["match_date"].dt.year):
        wins = int((g["winner_team_key"] == g["blue_team_key"]).sum())
        lo, hi = wilson_interval(wins, len(g))
        rows.append({"year": int(y), "n_games": int(len(g)), "blue_win_rate": wins / len(g),
                     "ci95_low": lo, "ci95_high": hi})
    return {"definition": "Share of games won by the blue side per calendar year, with 95% Wilson intervals.",
            "sample_period": _period(m), "by_year": rows}


def duration_trend(m: pd.DataFrame) -> dict:
    d = m[m["duration_seconds"].notna()]
    rows = [{"year": int(y), "n_games": int(len(g)), "mean_minutes": float(g["duration_seconds"].mean() / 60),
             "median_minutes": float(g["duration_seconds"].median() / 60)} for y, g in d.groupby(d["match_date"].dt.year)]
    return {"definition": "Game length from the source `gamelength` field (seconds), shown in minutes, per calendar year.",
            "sample_period": _period(d), "n_missing": int(m["duration_seconds"].isna().sum()), "by_year": rows}


def regional(m: pd.DataFrame, teams: pd.DataFrame) -> dict:
    """International results by each team's primary domestic league. The
    league is a competitive region recorded in the source; it is not a
    country and says nothing about player nationality."""
    home = teams.set_index("team_key")["primary_league"]
    intl = m[m["international"]].copy()
    league_summary = (m.groupby("league").agg(n_games=("source_game_id", "size"),
                                              first=("match_date", "min"), last=("match_date", "max"))
                      .reset_index().sort_values("n_games", ascending=False))
    league_summary["n_teams"] = league_summary["league"].map(
        pd.concat([m[["league", "blue_team_key"]].rename(columns={"blue_team_key": "t"}),
                   m[["league", "red_team_key"]].rename(columns={"red_team_key": "t"})]).groupby("league")["t"].nunique())
    out = {"definition": "Domestic league = most frequent non-international league a team played in. "
                         "International results count games at Worlds, MSI, First Stand and the Esports World Cup (codes WLDs, MSI, FST, EWC), and only "
                         "games between teams from different domestic leagues.",
           "sample_period": _period(m),
           "leagues": [{**r, "first": str(r["first"]), "last": str(r["last"])}
                       for r in league_summary.to_dict("records")],
           "international_available": bool(len(intl))}
    if len(intl):
        intl["blue_home"] = intl["blue_team_key"].map(home)
        intl["red_home"] = intl["red_team_key"].map(home)
        intl = intl[intl["blue_home"].notna() & intl["red_home"].notna() & (intl["blue_home"] != intl["red_home"])]
        rows = []
        for side in ("blue", "red"):
            part = pd.DataFrame({"league": intl[f"{side}_home"],
                                 "win": (intl["winner_team_key"] == intl[f"{side}_team_key"]).astype(int)})
            rows.append(part)
        res = pd.concat(rows).groupby("league").agg(games=("win", "size"), wins=("win", "sum")).reset_index()
        res = res[res["games"] >= 10].sort_values("games", ascending=False)
        out["international_by_home_league"] = [
            {"league": r.league, "games": int(r.games), "wins": int(r.wins), "win_rate": r.wins / r.games,
             "ci95_low": wilson_interval(int(r.wins), int(r.games))[0],
             "ci95_high": wilson_interval(int(r.wins), int(r.games))[1]} for r in res.itertuples()]
    return out


def upset_rate(db, game_id: int, burn_in_end: str | None) -> dict:
    mv = db.scalar(select(ModelVersion).where(ModelVersion.game_id == game_id, ModelVersion.model_key == "elo"))
    if mv is None:
        return {"available": False, "reason": "Elo has not been computed"}
    rows = db.execute(select(EloRating.match_id, EloRating.team_id, EloRating.rating_before, EloRating.match_date,
                             Match.winner_team_id).join(Match, Match.id == EloRating.match_id)
                      .where(EloRating.model_version_id == mv.id)).all()
    df = pd.DataFrame(rows, columns=["match_id", "team_id", "r", "date", "winner"])
    df["date"] = pd.to_datetime(df["date"], utc=True)
    if burn_in_end:
        df = df[df["date"] >= pd.to_datetime(burn_in_end, utc=True)]
    piv = df.sort_values("r").groupby("match_id").agg(low_team=("team_id", "first"), r_low=("r", "first"),
                                                     r_high=("r", "last"), winner=("winner", "first"),
                                                     date=("date", "first"))
    piv = piv[piv["r_low"] < piv["r_high"]]
    piv["upset"] = (piv["winner"] == piv["low_team"]).astype(int)
    piv["quarter"] = piv["date"].dt.tz_localize(None).dt.to_period("Q").astype(str)
    q = piv.groupby("quarter").agg(n=("upset", "size"), upsets=("upset", "sum")).reset_index()
    q = q[q["n"] >= 30]
    return {"definition": "Share of games won by the team with the lower pre-game Elo (games with equal "
                          "ratings and the Elo burn-in period excluded). Higher values mean less predictable "
                          "results under Elo.", "available": True,
            "by_quarter": [{"quarter": r.quarter, "n_games": int(r.n), "upset_rate": r.upsets / r.n}
                           for r in q.itertuples()], "overall": float(piv["upset"].mean()) if len(piv) else None,
            "n_games": int(len(piv))}


def run(database_url: str | None = None) -> dict:
    if not (PROCESSED_DIR / "matches.parquet").exists():
        log.error("No processed dataset; run the pipeline first.")
        return {"status": "no_data"}
    m = pd.read_parquet(PROCESSED_DIR / "matches.parquet")
    teams = pd.read_parquet(PROCESSED_DIR / "teams.parquet")
    tournaments = pd.read_parquet(PROCESSED_DIR / "tournaments.parquet")
    sm = get_sessionmaker(database_url)
    with sm() as db:
        game = db.scalar(select(Game).where(Game.slug == "lol"))
        mv = db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == "elo"))
        burn = (mv.periods or {}).get("burn_in_end") if mv else None
        outputs = {
            "competitive_balance": competitive_balance(m, teams),
            "title_concentration": title_concentration(m, tournaments, teams),
            "persistence": persistence(m),
            "side_advantage": side_advantage(m),
            "duration_trend": duration_trend(m),
            "regional": regional(m, teams),
            "upset_rate": upset_rate(db, game.id, burn),
            "placements": placements(m, tournaments, teams),
            "team_consistency": team_consistency(m, teams),
            "season_trends": season_trends(m),
        }
        now = datetime.now(UTC)
        db.execute(delete(AnalysisOutput).where(AnalysisOutput.game_id == game.id))
        for k, v in outputs.items():
            db.add(AnalysisOutput(game_id=game.id, key=k, generated_at=now,
                                  payload=_jsonable(v)))
        db.commit()
    return {"status": "ok", "keys": list(outputs)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
    sys.exit(0)
