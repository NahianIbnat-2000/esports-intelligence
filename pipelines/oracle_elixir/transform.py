"""Step 5: build the analytical tables from validated rows.

Outputs (data/processed/oracles_elixir/*.parquet):
  matches, team_rows, player_rows, teams, players, tournaments, rosters.

Definitions:
- tournament key = league | year | split (source fields). Name = "LEAGUE YEAR SPLIT".
- team identity = source teamid (fallback: team name, flagged).
- derived champion = winner of the chronologically last playoff game of the
  tournament. This is a derived value, not an official title record, and is
  null when no playoff games are present.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np
import pandas as pd

from pipelines.oracle_elixir.config import PLAYER_LOL_METRICS, TEAM_LOL_METRICS


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "item"


def unique_slugs(names: pd.Series, keys: pd.Series) -> pd.Series:
    base = names.map(slugify)
    dup = base.duplicated(keep=False)
    short = keys.map(lambda k: hashlib.sha1(str(k).encode()).hexdigest()[:6])
    return base.where(~dup, base + "-" + short)


def _mode(s: pd.Series):
    s = s.dropna()
    return s.mode().iloc[0] if len(s) else None


def build_tables(rows: pd.DataFrame, game_status: pd.DataFrame,
                 international_leagues: set[str]) -> dict[str, pd.DataFrame]:
    valid_ids = set(game_status.loc[game_status["valid"], "source_game_id"])
    rows = rows[rows["source_game_id"].isin(valid_ids)].copy()
    rows["year"] = rows["year"].fillna(rows["date"].dt.year).astype(int)
    rows["split"] = rows["split"].fillna("Unspecified")
    rows["tournament_key"] = rows["league"] + "|" + rows["year"].astype(str) + "|" + rows["split"]

    team = rows[rows["row_type"] == "team"].copy()
    player = rows[rows["row_type"] == "player"].copy()
    # The same player key twice in one game cannot be told apart; drop those
    # player rows (team level is unaffected) and report them.
    conflict = player.duplicated(["source_game_id", "player_key"], keep=False) | player["player_key"].isna()
    player_conflicts = player.loc[conflict, ["source_file", "source_row", "source_game_id", "participant_id"]].copy()
    player_conflicts["reason"] = "player key missing or repeated within one game"
    player = player.loc[~conflict]

    # ---- matches -------------------------------------------------------
    blue = team[team["side"] == "Blue"].set_index("source_game_id")
    red = team[team["side"] == "Red"].set_index("source_game_id")
    # Built from Series (not .values) so the UTC timezone is kept on dates.
    m = blue.reset_index()[["source_game_id", "date", "league", "year", "split", "tournament_key", "playoffs",
                            "game_in_series", "patch", "duration_seconds", "data_completeness", "source_url",
                            "source_file", "team_key"]].rename(columns={"date": "match_date",
                                                                       "team_key": "blue_team_key"})
    m["playoffs"] = m["playoffs"].map(lambda v: None if pd.isna(v) else bool(v)).astype(object)
    m["red_team_key"] = m["source_game_id"].map(red["team_key"])
    blue_won = m["source_game_id"].map(blue["result"]) == 1
    m["winner_team_key"] = np.where(blue_won, m["blue_team_key"], m["red_team_key"])
    m["international"] = m["league"].isin(international_leagues)
    status = game_status.set_index("source_game_id")
    m["player_rows_complete"] = m["source_game_id"].map(status["player_rows_complete"]).astype(bool)
    m = m.sort_values(["match_date", "source_game_id"]).reset_index(drop=True)

    # ---- team rows -----------------------------------------------------
    opp = team[["source_game_id", "side", "team_key"]].copy()
    opp["side"] = opp["side"].map({"Blue": "Red", "Red": "Blue"})
    team = team.merge(opp.rename(columns={"team_key": "opponent_team_key"}), on=["source_game_id", "side"])
    team_rows = team[["source_game_id", "team_key", "opponent_team_key", "side", "result", "kills",
                      "deaths", "assists", "date"] + TEAM_LOL_METRICS].rename(columns={"date": "match_date"})

    # ---- player rows ---------------------------------------------------
    player["kda"] = np.where(player["deaths"] > 0, (player["kills"] + player["assists"]) / player["deaths"],
                             player["kills"] + player["assists"])
    player.loc[player[["kills", "deaths", "assists"]].isna().any(axis=1), "kda"] = np.nan
    player_rows = player[["source_game_id", "player_key", "team_key", "side", "position", "result",
                          "kills", "deaths", "assists", "kda", "date", "tournament_key"]
                         + [c for c in PLAYER_LOL_METRICS if c not in ("kda",)]].rename(
        columns={"date": "match_date"})

    # ---- teams ---------------------------------------------------------
    team_sorted = team.sort_values("date")
    domestic = team_sorted[~team_sorted["league"].isin(international_leagues)]
    teams = team_sorted.groupby("team_key").agg(
        name=("team_name", "last"), id_from_name=("team_id_from_name", "max"),
        first_match_date=("date", "min"), last_match_date=("date", "max"),
        n_matches=("result", "size"), n_wins=("result", "sum")).reset_index()
    teams["primary_league"] = teams["team_key"].map(domestic.groupby("team_key")["league"].agg(_mode))
    teams["slug"] = unique_slugs(teams["name"], teams["team_key"])

    # ---- players -------------------------------------------------------
    ps = player.sort_values("date")
    players = ps.groupby("player_key").agg(
        name=("player_name", "last"), id_from_name=("player_id_from_name", "max"),
        primary_position=("position", _mode), first_match_date=("date", "min"),
        last_match_date=("date", "max"), n_matches=("result", "size")).reset_index()
    players = players[players["name"].notna()]
    players["slug"] = unique_slugs(players["name"], players["player_key"])

    # ---- tournaments ---------------------------------------------------
    tg = m.groupby("tournament_key")
    tournaments = tg.agg(league=("league", "first"), year=("year", "first"), split=("split", "first"),
                         start_date=("match_date", "min"), end_date=("match_date", "max"),
                         n_matches=("source_game_id", "size"),
                         has_playoffs=("playoffs", lambda s: bool(s.fillna(False).astype(bool).any())))
    tournaments = tournaments.reset_index()
    n_teams = pd.concat([m[["tournament_key", "blue_team_key"]].rename(columns={"blue_team_key": "k"}),
                         m[["tournament_key", "red_team_key"]].rename(columns={"red_team_key": "k"})])
    tournaments["n_teams"] = tournaments["tournament_key"].map(n_teams.groupby("tournament_key")["k"].nunique())
    po = m[m["playoffs"].fillna(False).astype(bool)].sort_values(["match_date", "source_game_id"])
    champ = po.groupby("tournament_key")["winner_team_key"].last()
    tournaments["derived_champion_team_key"] = tournaments["tournament_key"].map(champ)
    tournaments["name"] = (tournaments["league"] + " " + tournaments["year"].astype(str) + " "
                           + tournaments["split"].where(tournaments["split"] != "Unspecified", "")).str.strip()
    tournaments["slug"] = unique_slugs(tournaments["name"], tournaments["tournament_key"])

    # ---- rosters (observed appearances) ---------------------------------
    rosters = player.groupby(["team_key", "player_key", "tournament_key", "position"]).agg(
        games_played=("result", "size"), first_match_date=("date", "min"),
        last_match_date=("date", "max")).reset_index()
    rosters = rosters[rosters["player_key"].isin(players["player_key"])]

    return {"matches": m, "team_rows": team_rows, "player_rows": player_rows, "teams": teams,
            "players": players, "tournaments": tournaments, "rosters": rosters,
            "player_row_exclusions": player_conflicts}
