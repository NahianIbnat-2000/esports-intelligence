"""Point-in-time checks for roster features and player Elo, and the registry."""
import json

import numpy as np
import pandas as pd
import pytest

from machine_learning.elo.elo import EloConfig, run_elo
from machine_learning.experiments import registry
from machine_learning.experiments.lineups import add_roster_diffs, lineup_table, roster_features
from machine_learning.experiments.player_elo import PlayerEloConfig, run_player_elo

T0 = pd.Timestamp("2024-01-01", tz="UTC")


def toy():
    """Three teams, six games; team C replaces two players after game 3."""
    lineups = {"A": ["a1", "a2", "a3", "a4", "a5"], "B": ["b1", "b2", "b3", "b4", "b5"],
               "C": ["c1", "c2", "c3", "c4", "c5"]}
    sched = [("A", "B", "A"), ("B", "C", "B"), ("A", "C", "C"), ("A", "B", "A"), ("C", "B", "C"), ("A", "C", "A")]
    games, rows = [], []
    for i, (b, r, w) in enumerate(sched):
        gid = f"g{i}"
        date = T0 + pd.Timedelta(hours=i)
        games.append({"source_game_id": gid, "match_date": date, "blue_team_key": b, "red_team_key": r,
                      "winner_team_key": w, "league": "L", "international": False})
        for team in (b, r):
            names = list(lineups[team])
            if team == "C" and i >= 3:
                names[:2] = ["c6", "c7"]
            rows += [{"source_game_id": gid, "team_key": team, "player_key": p, "match_date": date} for p in names]
    return pd.DataFrame(games), pd.DataFrame(rows)


def test_roster_features_values():
    games, rows = toy()
    f = roster_features(lineup_table(rows)).set_index(["source_game_id", "team_key"])
    assert f.loc[("g0", "A"), "continuity"] == 0.0          # no previous game
    assert f.loc[("g3", "A"), "continuity"] == 1.0          # same five as g2
    assert f.loc[("g4", "C"), "continuity"] == pytest.approx(3 / 5)  # c6, c7 new
    # tenure before g4 for C: c3..c5 played g1, g2 (2 games); c6, c7 none (g3 was A vs B)
    assert f.loc[("g4", "C"), "tenure"] == pytest.approx((3 * np.log1p(2) + 2 * np.log1p(0)) / 5)


def test_roster_features_ignore_future():
    games, rows = toy()
    base = roster_features(lineup_table(rows))
    changed = rows.copy()
    later = changed["source_game_id"].isin(["g4", "g5"])
    changed.loc[later, "player_key"] = changed.loc[later, "player_key"] + "_x"
    after = roster_features(lineup_table(changed))
    early = ["g0", "g1", "g2", "g3"]
    pd.testing.assert_frame_equal(base[base.source_game_id.isin(early)].reset_index(drop=True),
                                  after[after.source_game_id.isin(early)].reset_index(drop=True))


def test_roster_diffs_are_blue_minus_red():
    games, rows = toy()
    f = roster_features(lineup_table(rows))
    d = add_roster_diffs(games, f).set_index("source_game_id")
    assert d.loc["g4", "continuity_diff"] == pytest.approx(3 / 5 - 1.0)


def test_player_elo_point_in_time_and_symmetry():
    games, rows = toy()
    lu = lineup_table(rows)
    team, _ = run_elo(games, EloConfig(k=20))
    cfg = PlayerEloConfig(k=20, carryover_shrink=0.0, k_league=0.0)
    pe = run_player_elo(team, lu, cfg).set_index("source_game_id")
    assert pe.loc["g0", "player_elo_diff"] == 0.0
    # flipping the result of the last game must not change any pre-game rating
    flipped = games.copy()
    flipped.loc[5, "winner_team_key"] = "C"
    team2, _ = run_elo(flipped, EloConfig(k=20))
    pe2 = run_player_elo(team2, lu, cfg).set_index("source_game_id")
    pd.testing.assert_series_equal(pe["player_elo_diff"], pe2["player_elo_diff"])


def test_player_elo_equals_team_elo_when_lineups_never_change():
    games, rows = toy()
    rows = rows[~rows.player_key.isin(["c6", "c7"])]
    rows = pd.concat([rows, rows[(rows.team_key == "C") & rows.player_key.isin(["c3", "c4"])].assign(
        player_key=lambda d: d.player_key.map({"c3": "c1", "c4": "c2"}))])
    rows = rows[~rows.duplicated()]
    lu = lineup_table(rows)
    team, _ = run_elo(games, EloConfig(k=20))
    pe = run_player_elo(team, lu, PlayerEloConfig(k=20, carryover_shrink=0.0, k_league=0.0))
    np.testing.assert_allclose(pe["player_elo_diff"].to_numpy(),
                               (team["blue_elo_pre"] - team["red_elo_pre"]).to_numpy(), atol=1e-9)


def test_registry_record(tmp_path, monkeypatch):
    man = tmp_path / "manifest.json"
    man.write_text(json.dumps({"files": [{"filename": "a.csv", "sha256": "aa"}, {"filename": "b.csv", "sha256": "bb"}]}))
    monkeypatch.setattr(registry, "REGISTRY_DIR", tmp_path / "reg")
    path = registry.save({"data": registry.data_checksum(man), "x": 1}, "test")
    rec = json.loads(path.read_text())
    assert rec["data"]["n_files"] == 2 and len(rec["code_sha256"]) == 64
    assert rec["environment"]["packages"]["numpy"]
    assert rec["experiment_id"].startswith("test-")


def test_prematch_variants_do_not_use_todays_lineup():
    games, rows = toy()
    lu = lineup_table(rows)
    f = roster_features(lu).set_index(["source_game_id", "team_key"])
    changed = rows.copy()
    m = (changed.source_game_id == "g4") & (changed.team_key == "C")
    changed.loc[m, "player_key"] = ["z1", "z2", "z3", "z4", "z5"]
    lu2 = lineup_table(changed)
    f2 = roster_features(lu2).set_index(["source_game_id", "team_key"])
    assert f.loc[("g4", "C"), "player_exp_prev"] == f2.loc[("g4", "C"), "player_exp_prev"]
    assert f.loc[("g4", "C"), "player_exp"] != f2.loc[("g4", "C"), "player_exp"]
    team, _ = run_elo(games, EloConfig(k=20))
    cfg = PlayerEloConfig(k=20, carryover_shrink=0.0, k_league=0.0)
    a = run_player_elo(team, lu, cfg).set_index("source_game_id")
    b = run_player_elo(team, lu2, cfg).set_index("source_game_id")
    assert a.loc["g4", "player_elo_prev_diff"] == b.loc["g4", "player_elo_prev_diff"]
