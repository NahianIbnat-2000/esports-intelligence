"""Player-level Elo with league levels.

Each player has a rating component r_p. A team's rating in a game is the level
of the team's home league plus the mean component of the five players who
actually played:

    R_team = L_home + mean(r_p for p in lineup)

Update after each game (same-timestamp games are one batch, as in team Elo):
- every player in the lineup: r_p += K (S - E) for the winner, -= for the loser,
  so the team mean moves by exactly K (S - E), as in team Elo;
- league levels move only in games between teams with different home leagues,
  by k_league (S - E).
A pre-match variant rates each team by the lineup of its PREVIOUS game
(`player_elo_prev_diff`), so it needs no knowledge of today's lineup.
New players start at r_p = 0, i.e. at their team's league level. A player who
moves to another league keeps r_p (an approximation: r_p is relative to the
league the player left). At a player's first game in a new calendar year,
r_p <- (1 - s) r_p.

Assumption: player ratings are not independent (five players share one result);
this is not a model of individual skill, only a way to let a rating follow
players when lineups change. Home leagues are taken from the team Elo replay
(`blue_home`, `red_home`), which uses earlier games only.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from machine_learning.elo.elo import NO_LEAGUE, expected_score


@dataclass
class PlayerEloConfig:
    k: float = 32.0
    carryover_shrink: float = 0.5
    k_league: float = 16.0
    initial: float = 1500.0

    def as_dict(self) -> dict:
        return {"k": self.k, "carryover_shrink": self.carryover_shrink, "k_league": self.k_league,
                "initial": self.initial}


def run_player_elo(team_games: pd.DataFrame, lineups: pd.DataFrame, cfg: PlayerEloConfig) -> pd.DataFrame:
    """team_games: output of run_elo (needs source_game_id, match_date, blue/red_team_key,
    blue_home, red_home, blue_won). Returns source_game_id, blue/red player-Elo pre-game
    ratings and p_blue_player."""
    g = team_games.sort_values(["match_date", "source_game_id"]).reset_index(drop=True)
    lu = lineups.set_index(["source_game_id", "team_key"])["players"]
    def norm(x):
        return tuple(x) if isinstance(x, (tuple, list, np.ndarray)) else None
    def col(team_col):
        arr = np.empty(len(g), dtype=object)   # filled one by one: np.array would make a 2-D array
        for i, x in enumerate(lu.reindex(list(zip(g["source_game_id"], g[team_col])))):
            arr[i] = norm(x)
        return arr
    bl, rl = col("blue_team_key"), col("red_team_key")
    dates = g["match_date"].values
    years = pd.DatetimeIndex(g["match_date"]).year.values
    hb, hr = g["blue_home"].values, g["red_home"].values
    won = g["blue_won"].values.astype(float)

    r: dict = defaultdict(float)
    last_year: dict = {}
    league: dict = defaultdict(float)
    n = len(g)
    pre_b, pre_r = np.empty(n), np.empty(n)
    prev_b, prev_r = np.empty(n), np.empty(n)      # rating of each team's PREVIOUS lineup (pre-match)
    last_lineup: dict = {}
    bt, rt = g["blue_team_key"].values, g["red_team_key"].values

    def L(lg):
        return cfg.initial + (league[lg] if lg not in (None, NO_LEAGUE) else 0.0)

    def team_rating(players, home):
        if not isinstance(players, tuple) or not players:
            return L(home)
        return L(home) + float(np.mean([r[p] for p in players]))

    i = 0
    while i < n:
        j = i
        while j < n and dates[j] == dates[i]:
            j += 1
        for t in range(i, j):
            for players in (bl[t], rl[t]):
                if isinstance(players, tuple):
                    for p in players:
                        if p in last_year and last_year[p] != years[t]:
                            r[p] *= (1.0 - cfg.carryover_shrink)
                        last_year[p] = years[t]
        pdelta: dict = defaultdict(float)
        ldelta: dict = defaultdict(float)
        for t in range(i, j):
            rb, rr = team_rating(bl[t], hb[t]), team_rating(rl[t], hr[t])
            pre_b[t], pre_r[t] = rb, rr
            prev_b[t] = team_rating(last_lineup.get(bt[t], bl[t]), hb[t])
            prev_r[t] = team_rating(last_lineup.get(rt[t], rl[t]), hr[t])
            d = won[t] - expected_score(rb, rr)
            for p in (bl[t] if isinstance(bl[t], tuple) else ()):
                pdelta[p] += cfg.k * d
            for p in (rl[t] if isinstance(rl[t], tuple) else ()):
                pdelta[p] -= cfg.k * d
            if cfg.k_league > 0 and hb[t] != hr[t]:
                if hb[t] != NO_LEAGUE:
                    ldelta[hb[t]] += cfg.k_league * d
                if hr[t] != NO_LEAGUE:
                    ldelta[hr[t]] -= cfg.k_league * d
        for p, dl in pdelta.items():
            r[p] += dl
        for t in range(i, j):
            if bl[t]:
                last_lineup[bt[t]] = bl[t]
            if rl[t]:
                last_lineup[rt[t]] = rl[t]
        for lg, dl in ldelta.items():
            league[lg] += dl
        i = j

    out = pd.DataFrame({"source_game_id": g["source_game_id"].values,
                        "blue_pelo_pre": pre_b, "red_pelo_pre": pre_r})
    out["player_elo_diff"] = out["blue_pelo_pre"] - out["red_pelo_pre"]
    out["p_blue_player"] = expected_score(out["blue_pelo_pre"], out["red_pelo_pre"])
    # Pre-match variant: previous lineup of each team (its own lineup for a team's first game,
    # which only affects games excluded by the 5-earlier-games rule).
    out["player_elo_prev_diff"] = prev_b - prev_r
    return out
