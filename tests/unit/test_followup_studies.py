"""Checks for the 2026-11 follow-up studies: player-history features, the
player-informed Elo start, forecast-timing helpers, multiple-testing
correction, the claims registry and the release manifest."""
import json

import numpy as np
import pandas as pd
import pytest

from machine_learning.elo.elo import EloConfig, run_elo
from machine_learning.experiments.lineups import lineup_table, roster_features
from machine_learning.experiments.player_history import (TEAM_COLS, add_history_diffs, lineup_groups,
                                                         player_history_features, run_elo_init)
from machine_learning.experiments.robustness import gap_series, holm, pre_series
from machine_learning.experiments.verify_claims import check_claims, check_manifest, lookup, normalise, render

T0 = pd.Timestamp("2024-01-01", tz="UTC")
ROLES = ["top", "jng", "mid", "bot", "sup"]


def toy():
    """Four teams, eight games. Team D appears at game 5 with three of B's players (a successor)."""
    lineups = {"A": ["a1", "a2", "a3", "a4", "a5"], "B": ["b1", "b2", "b3", "b4", "b5"],
               "C": ["c1", "c2", "c3", "c4", "c5"], "D": ["b1", "b2", "b3", "d4", "d5"]}
    sched = [("A", "B", "A"), ("B", "C", "B"), ("A", "C", "C"), ("A", "B", "A"), ("C", "B", "C"),
             ("D", "A", "D"), ("C", "D", "C"), ("A", "D", "A")]
    games, rows = [], []
    for i, (b, r, w) in enumerate(sched):
        gid, date = f"g{i}", T0 + pd.Timedelta(days=i)
        games.append({"source_game_id": gid, "match_date": date, "blue_team_key": b, "red_team_key": r,
                      "winner_team_key": w, "league": "L", "international": False, "tournament_key": "T"})
        for team in (b, r):
            for role, p in zip(ROLES, lineups[team]):
                rows.append({"source_game_id": gid, "team_key": team, "player_key": p, "match_date": date,
                             "position": role, "result": int(team == w), "golddiff_at_15": 100.0 if team == w else -100.0})
    return pd.DataFrame(games), pd.DataFrame(rows)


def test_history_matches_deployed_feature():
    _, rows = toy()
    f = player_history_features(lineup_groups(rows))
    r = roster_features(lineup_table(rows[["source_game_id", "team_key", "player_key", "match_date"]]))
    m = f.merge(r, on=["source_game_id", "team_key"])
    assert np.allclose(m["exp_log"].fillna(0.0), m["player_exp_prev"])


def test_history_ignores_future_games():
    games, rows = toy()
    base = player_history_features(lineup_groups(rows))
    changed = rows.copy()
    late = changed["source_game_id"].isin(["g6", "g7"])
    changed.loc[late, "result"] = 1 - changed.loc[late, "result"]
    changed.loc[late, "golddiff_at_15"] = 9999.0
    changed.loc[late, "player_key"] = changed.loc[late, "player_key"] + "_x"
    after = player_history_features(lineup_groups(changed))
    early = [f"g{i}" for i in range(6)]
    cols = TEAM_COLS[:-1]          # lineup_elo needs Elo input, absent here
    a = base[base.source_game_id.isin(early)].set_index(["source_game_id", "team_key"])[cols]
    b = after[after.source_game_id.isin(early)].set_index(["source_game_id", "team_key"])[cols]
    pd.testing.assert_frame_equal(a.sort_index(), b.sort_index())


def test_history_values_and_successor():
    _, rows = toy()
    f = player_history_features(lineup_groups(rows)).set_index(["source_game_id", "team_key"])
    # before g3, A's previous lineup (g2) has 2 earlier games each, 1 win each (g0 win, g2 loss)
    assert f.loc[("g3", "A"), "exp_raw"] == pytest.approx(2.0)
    assert f.loc[("g3", "A"), "wr_shr"] == pytest.approx((1 + 0.5 * 20) / (2 + 20))
    assert f.loc[("g5", "D"), "successor"] == 1.0          # 3 of 5 came from B, B played 1 day earlier
    assert f.loc[("g0", "A"), "successor"] == 0.0
    assert np.isnan(f.loc[("g0", "A"), "exp_log"])        # no previous lineup


def test_history_diffs_are_blue_minus_red():
    games, rows = toy()
    team, _ = run_elo(games, EloConfig(k=20))
    f = player_history_features(lineup_groups(rows), team)
    d = add_history_diffs(team, f, cols=["exp_raw"], diag=[]).set_index("source_game_id")
    fi = f.set_index(["source_game_id", "team_key"])
    assert d.loc["g4", "exp_raw_diff"] == pytest.approx(fi.loc[("g4", "C"), "exp_raw"] - fi.loc[("g4", "B"), "exp_raw"])


def test_elo_init_zero_equals_run_elo_and_alpha_moves_new_team():
    games, rows = toy()
    lu = lineup_groups(rows)
    a, _ = run_elo(games, EloConfig(k=20))
    b, _ = run_elo_init(games, EloConfig(k=20), lu, 0.0)
    assert np.allclose(a.sort_values("source_game_id")["blue_elo_pre"], b.sort_values("source_game_id")["blue_elo_pre"])
    c, _ = run_elo_init(games, EloConfig(k=20), lu, 1.0)
    pre_d = c.set_index("source_game_id").loc["g5", "blue_elo_pre"]
    r_b = a.set_index("source_game_id").loc["g4", "red_elo_post"]      # B's rating before g5
    # three of D's five players last played for B; the other two have no history (count as 0)
    assert pre_d == pytest.approx(1500.0 + 3 / 5 * (r_b - 1500.0))


def test_pre_series_freezes_and_flips():
    df = pd.DataFrame({"series": ["s", "s", "s"], "match_date": [T0, T0 + pd.Timedelta(hours=1), T0 + pd.Timedelta(hours=2)],
                       "blue_team_key": ["A", "B", "A"], "x": [10.0, 3.0, 7.0]})
    out = pre_series(df, ["x"])
    assert list(out["x"]) == [10.0, -10.0, 10.0]
    assert list(out["game_number_in_series"]) == [1, 2, 3]


def test_gap_series_splits_on_gap_not_on_utc_day():
    d = pd.DataFrame({"blue_team_key": ["A", "B", "A"], "red_team_key": ["B", "A", "B"], "tournament_key": ["T"] * 3,
                      "match_date": pd.to_datetime(["2024-01-01 23:00", "2024-01-02 00:30", "2024-01-03 12:00"], utc=True)})
    s = gap_series(d)
    assert s.iloc[0] == s.iloc[1] and s.iloc[1] != s.iloc[2]


def test_holm_is_monotone_and_bounded():
    p = np.array([0.01, 0.04, 0.03, 0.5])
    adj = holm(p)
    assert np.all(adj >= p) and np.all(adj <= 1)
    assert adj[0] == pytest.approx(0.04)                    # 4 * 0.01


def test_claim_helpers():
    obj = {"a": [{"m": "x", "v": 1.5}, {"m": "y", "v": -0.00477}]}
    assert lookup(obj, "a[m=y].v") == -0.00477
    assert render({"format": "{:.4f}"}, -0.00477) == "0.0048"
    assert normalise("$-$0.0048 and \\textminus 1") == "-0.0048 and - 1"


def test_published_claims_match_artifacts():
    bad = [c for c in check_claims() if not c["ok"]]
    assert not bad, bad


def test_release_manifest_checksums():
    res = check_manifest()
    assert res, "research/release_manifest.json is missing"
    bad = [r for r in res if not r["ok"]]
    assert not bad, f"files changed since the manifest was written (regenerate it): {bad}"


def test_preregistered_artifacts_unchanged():
    from machine_learning.experiments.prospective import verify_frozen
    spec = verify_frozen()
    assert "research/preregistration_2027/skill_exp.joblib" in spec["frozen_sha256"]
    assert len(spec["frozen_sha256"]) == 6
