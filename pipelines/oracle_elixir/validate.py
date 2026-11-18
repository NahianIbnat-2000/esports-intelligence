"""Step 4: validate the structure of each game.

A game (gameid) is accepted for match-level analysis only if:
  1. it has exactly two team rows,
  2. one Blue and one Red,
  3. two different team keys,
  4. exactly one winner (results sum to 1),
  5. a single date for both team rows.
Games that fail are excluded from match tables, with the reason recorded.
Player rows are kept only for accepted games. A game with a number of player
rows other than 10 is accepted at team level but flagged.
"""
from __future__ import annotations

import pandas as pd


def validate_games(rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (game_status, game_exclusions). game_status has one row per gameid."""
    team = rows[rows["row_type"] == "team"]
    player = rows[rows["row_type"] == "player"]
    g = team.groupby("source_game_id").agg(
        n_team_rows=("participant_id", "size"),
        sides=("side", lambda s: "".join(sorted(s.dropna()))),
        n_teams=("team_key", "nunique"),
        result_sum=("result", "sum"),
        n_dates=("date", "nunique"),
    )
    n_players = player.groupby("source_game_id").size().rename("n_player_rows")
    g = g.join(n_players, how="left").fillna({"n_player_rows": 0})
    all_ids = pd.Index(rows["source_game_id"].unique(), name="source_game_id")
    g = g.reindex(all_ids)
    g["n_team_rows"] = g["n_team_rows"].fillna(0)

    reasons = pd.Series("", index=g.index, dtype="object")
    reasons[g["n_team_rows"] != 2] = "expected 2 team rows"
    reasons[(reasons == "") & (g["sides"] != "BlueRed")] = "team rows not one Blue + one Red"
    reasons[(reasons == "") & (g["n_teams"] != 2)] = "same team on both sides"
    reasons[(reasons == "") & (g["result_sum"] != 1)] = "not exactly one winner"
    reasons[(reasons == "") & (g["n_dates"] != 1)] = "team rows have different dates"
    g["valid"] = reasons == ""
    g["reason"] = reasons
    g["player_rows_complete"] = g["n_player_rows"] == 10
    excl = g.loc[~g["valid"], ["reason", "n_team_rows", "n_player_rows"]].reset_index()
    return g.reset_index(), excl
