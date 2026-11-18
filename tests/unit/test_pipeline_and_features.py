"""Cleaning, validation, transformation, leakage and split tests on the
SYNTHETIC fixture (see tests/fixtures/make_oe_fixture.py)."""
import numpy as np
import pandas as pd
import pytest

from machine_learning.data_preparation.splits import SplitConfig, assign_splits
from machine_learning.elo.elo import EloConfig, run_elo
from machine_learning.feature_engineering.features import build_feature_matrix
from machine_learning.inference.predict import feature_row, team_state
from pipelines.oracle_elixir import clean, transform, validate
from pipelines.oracle_elixir.inspect import inspect_frame, normalise_columns
from tests.fixtures.make_oe_fixture import make_fixture


@pytest.fixture(scope="module")
def raw():
    return normalise_columns(make_fixture(n_days=200))


@pytest.fixture(scope="module")
def built(raw):
    rows, excl, counts = clean.clean([clean.standardise(raw, "fixture.csv")])
    status, game_excl = validate.validate_games(rows)
    tables = transform.build_tables(rows, status, set())
    return rows, excl, counts, status, game_excl, tables


def test_inspection_identifies_row_types(raw):
    rep = inspect_frame(raw, "fixture.csv")
    assert rep["missing_required_columns"] == []
    assert rep["row_types"]["team_rows (participantid 100/200)"] > 0
    # 10 player rows per game, plus the one injected duplicate player row
    assert rep["row_types"]["player_rows (participantid 1-10)"] == 10 * rep["n_unique_gameid"] + 1
    # 2 team rows per game, minus the one removed red team row
    assert rep["row_types"]["team_rows (participantid 100/200)"] == 2 * rep["n_unique_gameid"] - 1


def test_duplicate_row_detected(built):
    _, excl, counts, *_ = built
    assert counts["rows_duplicate_exact"] == 1
    assert (excl["reason"] == "exact duplicate row").sum() == 1


def test_game_missing_team_row_is_excluded(built):
    *_, status, game_excl, tables = built
    assert len(game_excl) == 1
    assert game_excl.iloc[0]["reason"] == "expected 2 team rows"
    assert game_excl.iloc[0]["source_game_id"] not in set(tables["matches"]["source_game_id"])


def test_player_rows_are_not_counted_as_matches(built, raw):
    *_, tables = built
    m = tables["matches"]
    assert m["source_game_id"].is_unique
    assert len(m) == raw["gameid"].nunique() - 1  # one invalid game
    assert len(tables["team_rows"]) == 2 * len(m)


def test_missing_values_stay_missing(built):
    *_, tables = built
    partial = tables["matches"].loc[tables["matches"]["data_completeness"] == "partial", "source_game_id"]
    assert len(partial) > 0
    pr = tables["player_rows"]
    assert pr.loc[pr["source_game_id"].isin(partial), "dpm"].isna().all()
    assert not (pr.loc[pr["source_game_id"].isin(partial), "dpm"] == 0).any()


def test_team_without_source_id_is_flagged(built):
    *_, tables = built
    t = tables["teams"].set_index("name")
    assert bool(t.loc["SYNTH Team 07", "id_from_name"]) is True
    assert t.loc["SYNTH Team 07"].name == "SYNTH Team 07"
    assert str(tables["teams"].loc[tables["teams"]["name"] == "SYNTH Team 07", "team_key"].iloc[0]).startswith("name:")


def test_dates_keep_utc(built):
    *_, tables = built
    assert str(tables["matches"]["match_date"].dt.tz) == "UTC"


def test_winner_matches_result(built):
    rows, *_, tables = built
    m = tables["matches"].set_index("source_game_id")
    blue_rows = rows[(rows["row_type"] == "team") & (rows["side"] == "Blue")].set_index("source_game_id")
    common = m.index.intersection(blue_rows.index)
    won = blue_rows.loc[common, "result"] == 1
    assert ((m.loc[common, "winner_team_key"] == m.loc[common, "blue_team_key"]) == won).all()


# ------------------------------------------------------------- leakage
def _features(matches):
    games, _ = run_elo(matches, EloConfig(k=20))
    return build_feature_matrix(games, matches)


def test_features_do_not_change_when_future_results_change(built):
    *_, tables = built
    m = tables["matches"].copy()
    f1 = _features(m)
    cut = m["match_date"].quantile(0.5)
    m2 = m.copy()
    future = m2["match_date"] > cut
    # flip every future result
    m2.loc[future, "winner_team_key"] = np.where(m2.loc[future, "winner_team_key"] == m2.loc[future, "blue_team_key"],
                                                 m2.loc[future, "red_team_key"], m2.loc[future, "blue_team_key"])
    f2 = _features(m2)
    cols = ["elo_diff", "recent_wr_diff", "hist_wr_diff", "opp_strength_diff", "experience_diff"]
    a = f1.set_index("source_game_id")[cols]
    b = f2.set_index("source_game_id")[cols]
    upto = f1.loc[f1["match_date"] <= cut, "source_game_id"]
    pd.testing.assert_frame_equal(a.loc[upto], b.loc[upto])
    # the first game after the cut still sees only the past
    first_future = f1.loc[f1["match_date"] > cut].sort_values("match_date")["source_game_id"].iloc[0]
    pd.testing.assert_series_equal(a.loc[first_future], b.loc[first_future])


def test_first_game_has_no_history(built):
    *_, tables = built
    f = _features(tables["matches"]).sort_values("match_date")
    first = f.iloc[0]
    assert first["blue_n_prior"] == 0 and first["red_n_prior"] == 0 and first["elo_diff"] == 0


def test_chronological_split_has_no_overlap(built):
    *_, tables = built
    f, info = assign_splits(_features(tables["matches"]), SplitConfig(burn_in_days=30))
    tr, va, te = (f[f["split"] == s]["match_date"] for s in ("train", "validation", "test"))
    assert tr.max() < va.min() and va.max() < te.min()
    assert (f.loc[f["split"] != "excluded", "min_prior_games"] >= 5).all()
    assert info["train"]["n"] > info["test"]["n"] > 0


def test_inference_features_match_training_features(built):
    """The backend inference path must rebuild the same features as training."""
    *_, tables = built
    m = tables["matches"]
    games, _ = run_elo(m, EloConfig(k=20))
    f = build_feature_matrix(games, m).sort_values("match_date")
    target = f.iloc[len(f) // 2]
    as_of = target["match_date"]

    def history(team):
        rows = []
        for _, g in games[games["match_date"] < as_of].iterrows():
            if team not in (g["blue_team_key"], g["red_team_key"]):
                continue
            blue = g["blue_team_key"] == team
            rows.append({"date": g["match_date"], "won": int(g["blue_won"] if blue else 1 - g["blue_won"]),
                         "rating_after": g["blue_elo_post"] if blue else g["red_elo_post"],
                         "opp_rating_before": g["red_elo_pre"] if blue else g["blue_elo_pre"]})
        return rows
    cfg = {"initial": 1500.0, "carryover_shrink": 0.0, "k": 20}
    sb = team_state(history(target["blue_team_key"]), as_of.to_pydatetime(), cfg)
    sr = team_state(history(target["red_team_key"]), as_of.to_pydatetime(), cfg)
    row = feature_row(sb, sr, False)
    for k in ("elo_diff", "recent_wr_diff", "hist_wr_diff", "opp_strength_diff", "experience_diff"):
        assert row[k] == pytest.approx(target[k], abs=1e-9), k
