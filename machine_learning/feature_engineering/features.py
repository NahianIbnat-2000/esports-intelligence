"""Pre-game features. Every feature for a game uses only games that ENDED
before it, i.e. games with a strictly earlier timestamp.

Games in the same best-of series have different timestamps, so game 2 can use
the result of game 1 (it was known before game 2 started). Games with an
identical timestamp never see each other.

The feature set is fixed in advance (not chosen by test performance):

  elo_diff              blue pre-game Elo - red pre-game Elo
  recent_wr_diff        difference in shrunk win rate over each team's last 10 games
  hist_wr_diff          difference in shrunk win rate over all earlier games
  opp_strength_diff     difference in mean pre-game Elo of each team's last 10 opponents
  experience_diff       difference in log(1 + number of earlier games)
  elo_diff_x_intl       elo_diff * 1[international event]

The intercept of the logistic model captures the blue-side advantage.
Shrinkage: recent = (wins + 1) / (n + 2), historical = (wins + 2.5) / (n + 5).
"""
from __future__ import annotations

from collections import deque

import numpy as np
import pandas as pd

WINDOW = 10
FEATURES = ["elo_diff", "recent_wr_diff", "hist_wr_diff", "opp_strength_diff", "experience_diff",
            "elo_diff_x_intl"]

FEATURE_DEFINITIONS = [
    {"name": "elo_diff", "definition": "Blue pre-game Elo minus red pre-game Elo", "unit": "Elo points"},
    {"name": "recent_wr_diff", "definition": "Blue minus red win rate over last 10 earlier games, "
                                             "shrunk: (wins+1)/(n+2)", "unit": "share"},
    {"name": "hist_wr_diff", "definition": "Blue minus red win rate over all earlier games, "
                                           "shrunk: (wins+2.5)/(n+5)", "unit": "share"},
    {"name": "opp_strength_diff", "definition": "Blue minus red mean pre-game Elo of last 10 opponents "
                                                "(initial rating when no history)", "unit": "Elo points"},
    {"name": "experience_diff", "definition": "Blue minus red log(1 + number of earlier games)", "unit": "log games"},
    {"name": "elo_diff_x_intl", "definition": "elo_diff times 1 if the league is a tier-1 international event "
                                              "(Worlds, MSI, First Stand, Esports World Cup)", "unit": "Elo points"},
]


def long_form(elo_games: pd.DataFrame) -> pd.DataFrame:
    """One row per team per game with the opponent's pre-game Elo."""
    b = pd.DataFrame({"source_game_id": elo_games["source_game_id"], "match_date": elo_games["match_date"],
                      "team": elo_games["blue_team_key"], "won": elo_games["blue_won"],
                      "opp_elo_pre": elo_games["red_elo_pre"], "side": "Blue"})
    r = pd.DataFrame({"source_game_id": elo_games["source_game_id"], "match_date": elo_games["match_date"],
                      "team": elo_games["red_team_key"], "won": 1 - elo_games["blue_won"],
                      "opp_elo_pre": elo_games["blue_elo_pre"], "side": "Red"})
    return pd.concat([b, r], ignore_index=True).sort_values(["team", "match_date", "source_game_id"])


def team_history_features(long: pd.DataFrame, initial: float = 1500.0) -> pd.DataFrame:
    out = []
    for team, g in long.groupby("team", sort=False):
        recent = deque(maxlen=WINDOW)
        opps = deque(maxlen=WINDOW)
        n_all = w_all = 0
        dates = g["match_date"].values
        won = g["won"].values
        opp = g["opp_elo_pre"].values
        gids = g["source_game_id"].values
        k = 0
        while k < len(g):
            # all games of this team at the same timestamp share the same "before" state
            j = k
            while j < len(g) and dates[j] == dates[k]:
                j += 1
            n_r = len(recent)
            feat = (n_all,
                    (sum(recent) + 1) / (n_r + 2),
                    (w_all + 2.5) / (n_all + 5),
                    float(np.mean(opps)) if opps else initial)
            for t in range(k, j):
                out.append((gids[t], team) + feat)
            for t in range(k, j):
                recent.append(won[t])
                opps.append(opp[t])
                n_all += 1
                w_all += won[t]
            k = j
    return pd.DataFrame(out, columns=["source_game_id", "team", "n_prior", "recent_wr", "hist_wr",
                                      "opp_strength"])


def build_feature_matrix(elo_games: pd.DataFrame, matches: pd.DataFrame, initial: float = 1500.0) -> pd.DataFrame:
    """elo_games from run_elo; matches from the processed dataset (for league/context)."""
    hist = team_history_features(long_form(elo_games), initial).set_index(["source_game_id", "team"])
    df = elo_games.copy()
    bh = hist.loc[list(zip(df["source_game_id"], df["blue_team_key"]))].reset_index(drop=True)
    rh = hist.loc[list(zip(df["source_game_id"], df["red_team_key"]))].reset_index(drop=True)
    ctx = matches.set_index("source_game_id").loc[df["source_game_id"], ["league", "international", "playoffs",
                                                                           "tournament_key"]].reset_index(drop=True)
    df = pd.concat([df.reset_index(drop=True), ctx], axis=1)
    df["elo_diff"] = df["blue_elo_pre"] - df["red_elo_pre"]
    df["recent_wr_diff"] = bh["recent_wr"] - rh["recent_wr"]
    df["hist_wr_diff"] = bh["hist_wr"] - rh["hist_wr"]
    df["opp_strength_diff"] = bh["opp_strength"] - rh["opp_strength"]
    df["experience_diff"] = np.log1p(bh["n_prior"]) - np.log1p(rh["n_prior"])
    df["elo_diff_x_intl"] = df["elo_diff"] * df["international"].astype(float)
    df["blue_n_prior"] = bh["n_prior"].values
    df["red_n_prior"] = rh["n_prior"].values
    df["min_prior_games"] = np.minimum(df["blue_n_prior"], df["red_n_prior"])
    return df
