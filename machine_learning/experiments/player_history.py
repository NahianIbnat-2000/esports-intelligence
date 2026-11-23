"""Point-in-time player-history features for the mechanism study
(docs/PLAYER_EXPERIENCE_MECHANISMS.md).

Every feature describes each team's PREVIOUS lineup (the five players of the
team's previous game), using only games with an earlier timestamp. This is the
same information contract as the deployed feature `player_exp_prev_diff`: it
needs no knowledge of today's lineup. Games with the same timestamp never see
each other (batch rule, as in Elo).

Per player p, before the current timestamp:
  n_p        earlier professional games (any team)
  w_p        earlier wins
  gd_p       sum of gold difference at 15 minutes against the lane opponent
             (source column golddiff_at_15; games without it are skipped)
  first_p    date of first game in the data
  recent_p   games in the last 180 days
  dec_H,p    time-decayed game count, each game weighted 0.5 ** (age / H days)
  last_team  the team p played the latest earlier game for

Team-level features (mean over the previous lineup unless stated):
  exp_log    log(1 + n_p)                          (= player_exp_prev, deployed)
  exp_raw    n_p
  exp_sqrt   sqrt(n_p)
  sat_T      1 - exp(-n_p / T), T in SAT_T         (diminishing returns)
  exp_median / exp_min / exp_max / exp_sd  of log(1 + n_p) over the five
  dec_H      log(1 + dec_H,p), H in DECAY_H days
  role_<r>   log(1 + n_p) of the player who played role r (top, jng, mid, bot, sup)
  wr_shr     (w_p + 0.5 m) / (n_p + m), m = SHRINK_M  (win rate shrunk to 50%)
  gd15_shr   gd_p / (n_gd + m)                     (lane gold lead shrunk to 0)
  career     log(1 + days since first_p)
  recent     log(1 + recent_p)
  lineup_elo mean over players of the current team-Elo total of last_team
             (the rating of the teams the players last played for; captures
             transfers). Players without a previous team are skipped.

Diagnostics (use today's lineup, so they are NOT prediction features; they
only define subgroups):
  cur_exp      mean log(1 + n_p) over today's five
  continuity   share of today's five who played the team's previous game
  gap_days     days since the team's previous game
  successor    at the team's first game, >= 3 of today's five played their
               latest game for one other team, whose last game was within
               SUCCESSOR_DAYS (a rebrand or a roster taken over by a new
               organisation; decided by players, not by name)
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque

import numpy as np
import pandas as pd

from machine_learning.elo.elo import NO_LEAGUE, EloConfig, EloState, expected_score

SAT_T = [25, 50, 100, 200]
DECAY_H = [180, 365, 730]
ROLES = ["top", "jng", "mid", "bot", "sup"]
SHRINK_M = 20
RECENT_DAYS = 180
SUCCESSOR_DAYS = 180
SUCCESSOR_MIN = 3

TEAM_COLS = (["exp_log", "exp_raw", "exp_sqrt"] + [f"sat_{t}" for t in SAT_T]
             + ["exp_median", "exp_min", "exp_max", "exp_sd"] + [f"dec_{h}" for h in DECAY_H]
             + [f"role_{r}" for r in ROLES] + ["wr_shr", "gd15_shr", "career", "recent", "lineup_elo"])
DIAG_COLS = ["cur_exp", "continuity", "gap_days", "successor", "has_prev"]


def lineup_groups(player_rows: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) with players, roles, result and lane gold lead, sorted by time."""
    p = player_rows.dropna(subset=["player_key", "team_key"]).copy()
    p["gd"] = pd.to_numeric(p["golddiff_at_15"], errors="coerce")
    p = p.sort_values(["match_date", "source_game_id", "team_key"])
    g = p.groupby(["source_game_id", "team_key"], sort=False)
    out = g.agg(match_date=("match_date", "first"), result=("result", "first")).reset_index()
    out["players"] = [tuple(x) for x in g["player_key"].apply(list)]
    out["roles"] = [tuple(x) for x in g["position"].apply(list)]
    out["gds"] = [tuple(x) for x in g["gd"].apply(list)]
    return out.sort_values(["match_date", "source_game_id", "team_key"]).reset_index(drop=True)


def _days(ts: pd.Series) -> np.ndarray:
    """Days since 1970 as float, independent of the datetime resolution (ns or us)."""
    idx = pd.DatetimeIndex(ts)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    return ((idx - pd.Timestamp("1970-01-01")) / pd.Timedelta(days=1)).to_numpy(np.float64)


def player_history_features(lu: pd.DataFrame, elo_games: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per (game, team) features of the previous lineup, plus diagnostics.

    elo_games (from run_elo) supplies post-game team ratings for `lineup_elo`;
    without it that column is NaN."""
    days = _days(lu["match_date"])
    games, teams = lu["source_game_id"].values, lu["team_key"].values
    players, roles, gds, results = lu["players"].values, lu["roles"].values, lu["gds"].values, lu["result"].values
    post = {}
    if elo_games is not None:
        for gid, b, r, bp, rp in elo_games[["source_game_id", "blue_team_key", "red_team_key", "blue_elo_post",
                                           "red_elo_post"]].itertuples(index=False):
            post[(gid, b)] = bp
            post[(gid, r)] = rp

    n, w = defaultdict(int), defaultdict(int)
    gd_sum, gd_n = defaultdict(float), defaultdict(int)
    first, recent = {}, defaultdict(deque)
    dec = {h: {} for h in DECAY_H}            # h -> p -> (value, day)
    last_team, last_game_day = {}, {}
    team_prev: dict = {}                      # team -> (players, roles)
    team_last_day: dict = {}
    team_rating: dict = {}
    first_game_succ: dict = {}

    N = len(lu)
    F = np.full((N, len(TEAM_COLS)), np.nan)
    D = np.full((N, len(DIAG_COLS)), np.nan)
    col = {c: i for i, c in enumerate(TEAM_COLS)}

    def logn(p):
        return np.log1p(n[p])

    i = 0
    while i < N:
        j = i
        while j < N and days[j] == days[i]:
            j += 1
        t_now = days[i]
        # 1. read state from before this timestamp
        for t in range(i, j):
            team = teams[t]
            prev = team_prev.get(team)
            cur = players[t]
            D[t, 0] = float(np.mean([logn(p) for p in cur])) if cur else np.nan
            D[t, 1] = (len(set(cur) & set(prev[0])) / max(len(cur), 1)) if prev else 0.0
            D[t, 2] = (t_now - team_last_day[team]) if team in team_last_day else np.nan
            if team not in first_game_succ:     # team's first game: successor test on today's lineup
                c = Counter(last_team[p] for p in cur if p in last_team and last_team[p] != team)
                succ = False
                if c:
                    other, k = c.most_common(1)[0]
                    succ = k >= SUCCESSOR_MIN and (t_now - team_last_day.get(other, -1e9)) <= SUCCESSOR_DAYS
                first_game_succ[team] = succ
            D[t, 3] = float(first_game_succ[team])
            D[t, 4] = float(prev is not None)
            if not prev:
                continue
            pl, rl = prev
            lg = np.array([logn(p) for p in pl])
            raw = np.array([n[p] for p in pl], dtype=float)
            F[t, col["exp_log"]] = lg.mean()
            F[t, col["exp_raw"]] = raw.mean()
            F[t, col["exp_sqrt"]] = np.sqrt(raw).mean()
            for T in SAT_T:
                F[t, col[f"sat_{T}"]] = (1 - np.exp(-raw / T)).mean()
            F[t, col["exp_median"]] = np.median(lg)
            F[t, col["exp_min"]] = lg.min()
            F[t, col["exp_max"]] = lg.max()
            F[t, col["exp_sd"]] = lg.std()
            for h in DECAY_H:
                vals = []
                for p in pl:
                    v = dec[h].get(p)
                    vals.append(np.log1p(v[0] * 0.5 ** ((t_now - v[1]) / h)) if v else 0.0)
                F[t, col[f"dec_{h}"]] = float(np.mean(vals))
            for p, r in zip(pl, rl):
                if r in ROLES:
                    F[t, col[f"role_{r}"]] = logn(p)
            F[t, col["wr_shr"]] = float(np.mean([(w[p] + 0.5 * SHRINK_M) / (n[p] + SHRINK_M) for p in pl]))
            F[t, col["gd15_shr"]] = float(np.mean([gd_sum[p] / (gd_n[p] + SHRINK_M) for p in pl]))
            F[t, col["career"]] = float(np.mean([np.log1p(t_now - first[p]) if p in first else 0.0 for p in pl]))
            rec = []
            for p in pl:
                dq = recent[p]
                while dq and dq[0] < t_now - RECENT_DAYS:
                    dq.popleft()
                rec.append(np.log1p(len(dq)))
            F[t, col["recent"]] = float(np.mean(rec))
            le = [team_rating[last_team[p]] for p in pl if p in last_team and last_team[p] in team_rating]
            F[t, col["lineup_elo"]] = float(np.mean(le)) if le else np.nan
        # 2. update with this timestamp's games
        for t in range(i, j):
            team, cur = teams[t], players[t]
            won = float(results[t]) if results[t] is not None and not pd.isna(results[t]) else 0.0
            for p, g in zip(cur, gds[t]):
                n[p] += 1
                w[p] += won
                if g is not None and not pd.isna(g):
                    gd_sum[p] += float(g)
                    gd_n[p] += 1
                first.setdefault(p, t_now)
                recent[p].append(t_now)
                for h in DECAY_H:
                    v = dec[h].get(p)
                    dec[h][p] = ((v[0] * 0.5 ** ((t_now - v[1]) / h) if v else 0.0) + 1.0, t_now)
                last_team[p] = team
                last_game_day[p] = t_now
            team_prev[team] = (cur, roles[t])
            team_last_day[team] = t_now
            if (games[t], team) in post:
                team_rating[team] = post[(games[t], team)]
        i = j

    out = pd.DataFrame(F, columns=TEAM_COLS)
    out[DIAG_COLS] = D
    out.insert(0, "team_key", teams)
    out.insert(0, "source_game_id", games)
    # roles missing in the previous game (rare): use the lineup mean
    for r in ROLES:
        out[f"role_{r}"] = out[f"role_{r}"].fillna(out["exp_log"])
    return out


def add_history_diffs(df: pd.DataFrame, feats: pd.DataFrame, cols=TEAM_COLS, diag=DIAG_COLS) -> pd.DataFrame:
    """Blue minus red differences of `cols` (NaN -> 0), plus per-side diagnostics."""
    f = feats.set_index(["source_game_id", "team_key"])
    out = df.copy()
    sides = {}
    for side in ("blue", "red"):
        sub = f.reindex(list(zip(out["source_game_id"], out[f"{side}_team_key"])))
        sides[side] = sub
        for c in diag:
            out[f"{side}_{c}"] = sub[c].to_numpy()
    for c in cols:
        b, r = sides["blue"][c].to_numpy(), sides["red"][c].to_numpy()
        if c == "lineup_elo":               # missing -> team's own Elo, so the diff falls back to elo_diff
            b = np.where(np.isnan(b), out["blue_elo_pre"].to_numpy(), b)
            r = np.where(np.isnan(r), out["red_elo_pre"].to_numpy(), r)
        out[f"{c}_diff"] = np.nan_to_num(b - r, nan=0.0)
    return out


# --------------------------------------------------------------------------- player-informed Elo start
def run_elo_init(matches: pd.DataFrame, config: EloConfig, lineups: pd.DataFrame, alpha: float):
    """Team Elo exactly as machine_learning.elo.run_elo, except that a team's
    component at its FIRST game starts at

        alpha * mean over today's five of (R_last_team(p) - L_home)

    where R_last_team(p) is the current total rating of the team player p last
    played for (0 for a player with no earlier game). alpha = 0 reproduces
    run_elo. Uses today's lineup at the team's first game (lineup-confirmed
    information)."""
    lu = lineups.set_index(["source_game_id", "team_key"])["players"].to_dict()
    m = matches.sort_values(["match_date", "source_game_id"]).reset_index(drop=True)
    st = EloState(config)
    n = len(m)
    bpre, rpre = np.empty(n), np.empty(n)
    bpost, rpost = np.empty(n), np.empty(n)
    dates = m["match_date"].values
    years = pd.DatetimeIndex(m["match_date"]).year.values
    gid = m["source_game_id"].values
    blue, red = m["blue_team_key"].values, m["red_team_key"].values
    blue_won = (m["winner_team_key"].values == blue).astype(float)
    leagues = m["league"].values
    intl = m["international"].values.astype(bool)
    home_b, home_r = np.empty(n, dtype=object), np.empty(n, dtype=object)
    last_team: dict = {}

    i = 0
    while i < n:
        j = i
        while j < n and dates[j] == dates[i]:
            j += 1
        for t in range(i, j):
            game_lg = None if intl[t] else leagues[t]
            for team in (blue[t], red[t]):
                is_new = team not in st.home
                st.set_home(team, game_lg)
                if is_new and alpha:
                    cur = lu.get((gid[t], team), ())
                    vals = [st.total(last_team[p]) - st.L(st.home[team]) if p in last_team else 0.0 for p in cur]
                    st.team[team] = alpha * float(np.mean(vals)) if vals else 0.0
                st.new_year(team, years[t])
            home_b[t], home_r[t] = st.home[blue[t]], st.home[red[t]]
        team_delta, league_delta = defaultdict(float), defaultdict(float)
        for t in range(i, j):
            rb, rr = st.total(blue[t]), st.total(red[t])
            e = expected_score(rb, rr)
            bpre[t], rpre[t] = rb, rr
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
        for team, dlt in team_delta.items():
            st.team[team] = st.team.get(team, 0.0) + dlt
        for lg, dlt in league_delta.items():
            st.league[lg] = st.L(lg) + dlt
        for t in range(i, j):
            for team in (blue[t], red[t]):
                st.last_year[team] = years[t]
                for p in lu.get((gid[t], team), ()):
                    last_team[p] = team
            if not intl[t] and leagues[t] is not None:
                st.counts[blue[t]][leagues[t]] += 1
                st.counts[red[t]][leagues[t]] += 1
            bpost[t], rpost[t] = st.total(blue[t]), st.total(red[t])
        i = j
    res = pd.DataFrame({"source_game_id": gid, "match_date": m["match_date"].reset_index(drop=True),
                        "blue_team_key": blue, "red_team_key": red, "blue_elo_pre": bpre, "red_elo_pre": rpre,
                        "blue_elo_post": bpost, "red_elo_post": rpost,
                        "blue_league_post": np.nan, "red_league_post": np.nan,
                        "blue_home": home_b, "red_home": home_r, "blue_won": blue_won.astype(int)})
    res["p_blue_elo"] = expected_score(res["blue_elo_pre"], res["red_elo_pre"])
    return res, st
