"""Point-in-time lineup (roster) features.

The source lists the five players who played each game. A lineup is known when
the game starts (it is visible in the draft), but not days before. Every result
that uses these features therefore answers "does knowing the lineup help?",
not "can we predict a week ahead?".

For each team in each game (strictly earlier games only, same-timestamp games
never see each other):

  continuity     share of today's five who also played the team's previous game
  tenure         mean over today's five of log(1 + earlier games for THIS team)
  player_exp     mean over today's five of log(1 + earlier pro games, any team)
  player_exp_prev  the same, but for the five who played the team's PREVIOUS game
                 (known before match day: no knowledge of today's lineup)

The model features are blue minus red differences:
  continuity_diff, tenure_diff, player_exp_diff
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

ROSTER_FEATURES = ["continuity_diff", "tenure_diff", "player_exp_diff"]

ROSTER_DEFINITIONS = [
    {"name": "continuity_diff", "definition": "Blue minus red share of today's players who also played the "
                                              "team's previous game", "unit": "share"},
    {"name": "tenure_diff", "definition": "Blue minus red mean log(1 + earlier games for this team) over "
                                          "today's players", "unit": "log games"},
    {"name": "player_exp_diff", "definition": "Blue minus red mean log(1 + earlier professional games, any "
                                              "team) over today's players", "unit": "log games"},
]

PREMATCH_FEATURE = {"name": "player_exp_prev_diff",
                    "definition": "Same as player_exp_diff but for the players of each team's previous game, "
                                  "so it needs no knowledge of today's lineup", "unit": "log games"}


def lineup_table(player_rows: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team): match_date and the tuple of player keys."""
    p = player_rows.dropna(subset=["player_key", "team_key"])
    g = (p.groupby(["source_game_id", "team_key"], sort=False)
         .agg(match_date=("match_date", "first"), players=("player_key", lambda s: tuple(sorted(set(s)))))
         .reset_index())
    # pyarrow-backed frames turn tuples into lists; keep plain Python tuples
    g["players"] = pd.Series([tuple(x) for x in g["players"]], index=g.index, dtype=object)
    g["source_game_id"] = g["source_game_id"].astype(object)
    g["team_key"] = g["team_key"].astype(object)
    return g


def roster_features(lineups: pd.DataFrame) -> pd.DataFrame:
    """Per (game, team) roster features using strictly earlier games only."""
    lu = lineups.sort_values(["match_date", "source_game_id", "team_key"]).reset_index(drop=True)
    dates = lu["match_date"].values
    games = lu["source_game_id"].values
    teams = lu["team_key"].values
    players = lu["players"].values

    last_lineup: dict = {}
    team_player: dict = defaultdict(int)
    player_total: dict = defaultdict(int)
    out = np.empty((len(lu), 4))

    i, n = 0, len(lu)
    while i < n:
        j = i
        while j < n and dates[j] == dates[i]:
            j += 1
        for t in range(i, j):          # read state from before this timestamp
            cur = players[t]
            prev = last_lineup.get(teams[t])
            k = max(len(cur), 1)
            out[t, 0] = (len(set(cur) & set(prev)) / k) if prev else 0.0
            out[t, 1] = float(np.mean([np.log1p(team_player[(teams[t], p)]) for p in cur])) if cur else 0.0
            out[t, 2] = float(np.mean([np.log1p(player_total[p]) for p in cur])) if cur else 0.0
            out[t, 3] = float(np.mean([np.log1p(player_total[p]) for p in prev])) if prev else 0.0
        for t in range(i, j):          # then update
            last_lineup[teams[t]] = players[t]
            for p in players[t]:
                team_player[(teams[t], p)] += 1
                player_total[p] += 1
        i = j
    return pd.DataFrame({"source_game_id": games, "team_key": teams, "continuity": out[:, 0],
                         "tenure": out[:, 1], "player_exp": out[:, 2], "player_exp_prev": out[:, 3]})


def add_roster_diffs(df: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    """Join per-team roster features onto a game-level frame (blue minus red)."""
    f = feats.set_index(["source_game_id", "team_key"])
    out = df.copy()
    for side in ("blue", "red"):
        idx = list(zip(out["source_game_id"], out[f"{side}_team_key"]))
        sub = f.reindex(idx)
        for c in ("continuity", "tenure", "player_exp", "player_exp_prev"):
            out[f"{side}_{c}"] = sub[c].to_numpy()
    for c in ("continuity", "tenure", "player_exp", "player_exp_prev"):
        out[f"{c}_diff"] = (out[f"blue_{c}"] - out[f"red_{c}"]).fillna(0.0)
    return out
