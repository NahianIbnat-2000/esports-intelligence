"""Elo rating system for single professional games, with optional league
offsets.

Expected score of team A against team B:

    E_A = 1 / (1 + 10 ** ((R_B - R_A) / 400))

Flat Elo (k_league = 0): R is one number per team, updated after each game by
R_A' = R_A + K (S_A - E_A).

Elo with league offsets (k_league > 0): a team's rating is the sum of a league
level and a team component, R = L_league + r_team.
- Games inside one league move only the team components (the league level
  cancels out of E_A).
- Games between teams from different leagues (international events, European
  Masters, cross-league cups) also move the two league levels by
  +/- k_league (S_A - E_A). A league's level therefore rises for every team in
  it when its representatives beat other leagues.
- A new team starts at its league's level, not at a global 1500.
- A team's home league is the league it has played most domestic games in so
  far (earlier games only). If it changes, the team component is re-based so
  its total rating does not jump.
With k_league = 0 every league stays at the initial value and the model is
exactly flat Elo.

Other design decisions (docs/methodology.md):
- Update after every game in time order. Games with the same timestamp are
  one batch: expectations use ratings from before the batch.
- No decay while inactive.
- New calendar year: the team component shrinks toward its league level,
  r <- (1 - carryover_shrink) r.
- No side term (the calibrated model estimates the blue-side effect).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

NO_LEAGUE = "__none__"


def expected_score(r_a: float | np.ndarray, r_b: float | np.ndarray) -> float | np.ndarray:
    return 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / 400.0))


@dataclass
class EloConfig:
    k: float = 20.0
    initial: float = 1500.0
    carryover_shrink: float = 0.0
    k_league: float = 0.0

    def as_dict(self) -> dict:
        return {"k": self.k, "initial": self.initial, "carryover_shrink": self.carryover_shrink,
                "k_league": self.k_league}


@dataclass
class EloState:
    config: EloConfig
    team: dict = field(default_factory=dict)          # team component r
    league: dict = field(default_factory=dict)        # league level L
    home: dict = field(default_factory=dict)          # current home league
    counts: dict = field(default_factory=lambda: defaultdict(Counter))
    last_year: dict = field(default_factory=dict)
    cross_games: Counter = field(default_factory=Counter)

    def L(self, lg: str) -> float:
        return self.config.initial if lg == NO_LEAGUE else self.league.get(lg, self.config.initial)

    def total(self, t) -> float:
        return self.L(self.home.get(t, NO_LEAGUE)) + self.team.get(t, 0.0)

    # kept for backward compatibility with earlier code and tests
    @property
    def ratings(self) -> dict:
        return {t: self.total(t) for t in self.team}

    def set_home(self, t, game_league: str | None) -> None:
        """Home = most frequent domestic league among earlier games; for a team
        with no domestic history, this game's league (if domestic)."""
        c = self.counts[t]
        new = c.most_common(1)[0][0] if c else (game_league or self.home.get(t, NO_LEAGUE))
        old = self.home.get(t)
        if old is None:
            self.home[t] = new
            self.team.setdefault(t, 0.0)
        elif new != old:
            total = self.total(t)
            self.home[t] = new
            self.team[t] = total - self.L(new)

    def new_year(self, t, year: int) -> None:
        if t in self.last_year and year > self.last_year[t]:
            self.team[t] = (1 - self.config.carryover_shrink) * self.team.get(t, 0.0)


def run_elo(matches: pd.DataFrame, config: EloConfig) -> tuple[pd.DataFrame, EloState]:
    """Replay games chronologically.

    `matches` needs: source_game_id, match_date, blue_team_key, red_team_key,
    winner_team_key, and (for league offsets) league and international.
    Returns one row per game with pre- and post-game total ratings and the
    post-game league levels, plus the final state.
    """
    m = matches.sort_values(["match_date", "source_game_id"]).reset_index(drop=True)
    st = EloState(config)
    n = len(m)
    out = {k: np.empty(n) for k in ("bpre", "rpre", "bpost", "rpost", "blg", "rlg")}
    dates = m["match_date"].values
    years = pd.DatetimeIndex(m["match_date"]).year.values
    blue = m["blue_team_key"].values
    red = m["red_team_key"].values
    blue_won = (m["winner_team_key"].values == blue).astype(float)
    leagues = m["league"].values if "league" in m else np.array([None] * n)
    intl = m["international"].values.astype(bool) if "international" in m else np.zeros(n, bool)
    home_b, home_r = np.empty(n, dtype=object), np.empty(n, dtype=object)

    i = 0
    while i < n:
        j = i
        while j < n and dates[j] == dates[i]:
            j += 1
        # 1. homes and season carry-over from earlier games only
        for t in range(i, j):
            game_lg = None if intl[t] else leagues[t]
            for team in (blue[t], red[t]):
                st.set_home(team, game_lg)
                st.new_year(team, years[t])
            home_b[t], home_r[t] = st.home[blue[t]], st.home[red[t]]
        # 2. expectations from pre-batch ratings
        team_delta: dict = defaultdict(float)
        league_delta: dict = defaultdict(float)
        for t in range(i, j):
            rb, rr = st.total(blue[t]), st.total(red[t])
            e = expected_score(rb, rr)
            out["bpre"][t], out["rpre"][t] = rb, rr
            d = blue_won[t] - e
            team_delta[blue[t]] += config.k * d
            team_delta[red[t]] -= config.k * d
            hb, hr = home_b[t], home_r[t]
            if hb != hr:
                if config.k_league > 0:
                    if hb != NO_LEAGUE:
                        league_delta[hb] += config.k_league * d
                    if hr != NO_LEAGUE:
                        league_delta[hr] -= config.k_league * d
                st.cross_games[hb] += 1
                st.cross_games[hr] += 1
        # 3. apply updates
        for team, dlt in team_delta.items():
            st.team[team] = st.team.get(team, 0.0) + dlt
        for lg, dlt in league_delta.items():
            st.league[lg] = st.L(lg) + dlt
        for t in range(i, j):
            for team in (blue[t], red[t]):
                st.last_year[team] = years[t]
            if not intl[t] and leagues[t] is not None:
                st.counts[blue[t]][leagues[t]] += 1
                st.counts[red[t]][leagues[t]] += 1
            out["bpost"][t], out["rpost"][t] = st.total(blue[t]), st.total(red[t])
            out["blg"][t], out["rlg"][t] = st.L(home_b[t]), st.L(home_r[t])
        i = j

    res = pd.DataFrame({
        "source_game_id": m["source_game_id"].values,
        "match_date": m["match_date"].reset_index(drop=True),
        "blue_team_key": blue, "red_team_key": red,
        "blue_elo_pre": out["bpre"], "red_elo_pre": out["rpre"],
        "blue_elo_post": out["bpost"], "red_elo_post": out["rpost"],
        "blue_league_post": out["blg"], "red_league_post": out["rlg"],
        "blue_home": home_b, "red_home": home_r,
        "blue_won": blue_won.astype(int),
    })
    res["p_blue_elo"] = expected_score(res["blue_elo_pre"], res["red_elo_pre"])
    return res, st


def league_table(state: EloState, min_cross_games: int = 30) -> list[dict]:
    """Final league levels for leagues with enough cross-league games."""
    rows = [{"league": lg, "level": state.L(lg), "offset_vs_initial": state.L(lg) - state.config.initial,
             "cross_league_games": int(state.cross_games[lg])}
            for lg in set(state.home.values()) if lg != NO_LEAGUE and state.cross_games[lg] >= min_cross_games]
    return sorted(rows, key=lambda r: -r["level"])
