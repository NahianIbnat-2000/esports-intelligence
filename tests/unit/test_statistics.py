import math

import numpy as np
import pandas as pd
import pytest

from analytics.economics.concentration import gini, hhi, hhi_normalised, lorenz_curve, noll_scully, wilson_interval
from machine_learning.elo.elo import EloConfig, expected_score, run_elo
from machine_learning.evaluation import metrics as M


# ------------------------------------------------------------------ Elo
def test_expected_score_formula():
    assert expected_score(1500, 1500) == pytest.approx(0.5)
    assert expected_score(1900, 1500) == pytest.approx(1 / (1 + 10 ** (-1)))
    assert expected_score(1600, 1500) + expected_score(1500, 1600) == pytest.approx(1.0)


def _games(rows):
    return pd.DataFrame(rows, columns=["source_game_id", "match_date", "blue_team_key", "red_team_key",
                                       "winner_team_key"]).assign(match_date=lambda d: pd.to_datetime(d["match_date"], utc=True))


def test_elo_update_is_zero_sum_and_uses_pre_ratings():
    g = _games([("g1", "2024-01-01 10:00", "A", "B", "A"), ("g2", "2024-01-02 10:00", "A", "B", "B")])
    res, state = run_elo(g, EloConfig(k=20))
    assert res.loc[0, "blue_elo_pre"] == 1500 and res.loc[0, "red_elo_pre"] == 1500
    assert res.loc[0, "blue_elo_post"] == pytest.approx(1510)
    assert res.loc[1, "blue_elo_pre"] == pytest.approx(1510)  # uses result of g1 only
    assert sum(state.ratings.values()) == pytest.approx(3000)


def test_elo_same_timestamp_games_do_not_see_each_other():
    g = _games([("g1", "2024-01-01 10:00", "A", "B", "A"), ("g2", "2024-01-01 10:00", "A", "C", "A")])
    res, _ = run_elo(g, EloConfig(k=20))
    assert (res["blue_elo_pre"] == 1500).all()


def test_elo_carryover_shrinks_toward_initial():
    g = _games([("g1", "2024-12-30 10:00", "A", "B", "A"), ("g2", "2025-01-05 10:00", "A", "B", "A")])
    res, _ = run_elo(g, EloConfig(k=20, carryover_shrink=0.5))
    assert res.loc[1, "blue_elo_pre"] == pytest.approx(1505)


# --------------------------------------------------------- concentration
def test_hhi_and_normalised():
    assert hhi([1, 1, 1, 1]) == pytest.approx(0.25)
    assert hhi_normalised([1, 1, 1, 1]) == pytest.approx(0.0)
    assert hhi([5, 0, 0]) == pytest.approx(1.0)
    assert hhi_normalised([5, 0, 0]) == pytest.approx(1.0)
    assert hhi([]) is None and hhi([0, 0]) is None


def test_gini_known_values():
    assert gini([1, 1, 1, 1]) == pytest.approx(0.0)
    assert gini([0, 0, 0, 1]) == pytest.approx(0.75)  # (n-1)/n for one holder
    x = np.array([1, 2, 3, 4, 10])
    brute = np.abs(x[:, None] - x[None, :]).sum() / (2 * len(x) ** 2 * x.mean())
    assert gini(x) == pytest.approx(brute)


def test_lorenz_curve_endpoints():
    c = lorenz_curve([1, 3])
    assert c[0]["cumulative_share"] == 0 and c[-1]["cumulative_share"] == pytest.approx(1)
    assert c[1]["cumulative_share"] == pytest.approx(0.25)


def test_noll_scully_coin_flip_reference():
    # sd of win% equal to 0.5/sqrt(G) gives exactly 1
    G = 16
    ideal = 0.5 / math.sqrt(G)
    w = [0.5 + ideal, 0.5 - ideal]
    assert noll_scully(w, [G, G]) == pytest.approx(1.0)


def test_wilson_interval_contains_p():
    lo, hi = wilson_interval(55, 100)
    assert lo < 0.55 < hi
    assert wilson_interval(0, 0) == (None, None)


def test_negative_values_rejected():
    with pytest.raises(ValueError):
        hhi([1, -1])


# --------------------------------------------------------------- metrics
def test_brier_and_summary():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.9, 0.1, 0.6, 0.4])
    assert M.brier(y, p) == pytest.approx(np.mean((p - y) ** 2))
    s = M.summary(y, p)
    assert s["accuracy"] == 1.0 and s["roc_auc"] == 1.0 and s["n"] == 4


def test_calibration_bins_cover_all_and_report_empty_as_null():
    y = np.array([1, 0, 1, 1])
    p = np.array([0.05, 0.15, 0.95, 0.99])
    t = M.calibration_table(y, p, 10)
    assert sum(b["n"] for b in t) == 4
    assert t[5]["n"] == 0 and t[5]["mean_predicted"] is None


def test_paired_bootstrap_sign():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 500)
    good = np.where(y == 1, 0.8, 0.2)
    bad = np.full(500, 0.5)
    r = M.paired_bootstrap_diff(y, good, bad, "brier", n_boot=300)
    assert r["difference"] < 0 and r["ci95_high"] < 0


# --------------------------------------------------- Elo league offsets
def _two_league_games(seed=3, n_days=300):
    """Two closed leagues (strong S, weak W) that meet only at an
    international event every 30 days. SYNTHETIC."""
    rng = np.random.default_rng(seed)
    rows, gid = [], 0
    strength = {f"S{i}": 1.0 for i in range(4)} | {f"W{i}": 0.0 for i in range(4)}
    start = pd.Timestamp("2024-01-01", tz="UTC")
    for d in range(n_days):
        for lg in ("S", "W"):
            a, b = rng.choice(4, 2, replace=False)
            ta, tb = f"{lg}{a}", f"{lg}{b}"
            gid += 1
            rows.append((f"g{gid}", start + pd.Timedelta(days=d, hours=1 if lg == "S" else 2), ta, tb,
                         ta if rng.random() < 0.5 else tb, lg, False))
        if d % 30 == 15:
            for _ in range(6):
                ta, tb = f"S{rng.integers(4)}", f"W{rng.integers(4)}"
                p = 1 / (1 + np.exp(-(strength[ta] - strength[tb]) * 2))
                gid += 1
                rows.append((f"g{gid}", start + pd.Timedelta(days=d, hours=5, minutes=gid % 50), ta, tb,
                             ta if rng.random() < p else tb, "WLDs", True))
    return pd.DataFrame(rows, columns=["source_game_id", "match_date", "blue_team_key", "red_team_key",
                                       "winner_team_key", "league", "international"])


def test_league_offsets_learn_the_gap_between_leagues():
    from machine_learning.elo.elo import league_table
    g = _two_league_games()
    _, st = run_elo(g, EloConfig(k=20, k_league=16))
    assert st.L("S") > 1500 > st.L("W")
    levels = {r["league"]: r for r in league_table(st, min_cross_games=10)}
    assert levels["S"]["level"] > levels["W"]["level"]
    # flat Elo cannot separate the leagues' averages much: within-league games are zero-sum
    _, flat = run_elo(g, EloConfig(k=20, k_league=0))
    gap_flat = np.mean([flat.total(f"S{i}") - flat.total(f"W{i}") for i in range(4)])
    gap_lo = np.mean([st.total(f"S{i}") - st.total(f"W{i}") for i in range(4)])
    assert gap_lo > gap_flat


def test_k_league_zero_equals_flat_elo():
    g = _two_league_games(n_days=60)
    a, _ = run_elo(g, EloConfig(k=24, carryover_shrink=0.25, k_league=0))
    b, _ = run_elo(g.drop(columns=["league", "international"]), EloConfig(k=24, carryover_shrink=0.25))
    np.testing.assert_allclose(a["blue_elo_pre"], b["blue_elo_pre"])
    np.testing.assert_allclose(a["red_elo_post"], b["red_elo_post"])


def test_home_league_change_keeps_total_rating():
    from machine_learning.elo.elo import EloState
    st = EloState(EloConfig(k_league=8))
    st.league = {"A": 1600.0, "B": 1400.0}
    st.home["t"] = "A"
    st.team["t"] = 50.0
    st.counts["t"]["B"] = 3  # team now plays mostly in B
    before = st.total("t")
    st.set_home("t", "B")
    assert st.home["t"] == "B" and st.total("t") == pytest.approx(before)



def test_ece_f1_and_histogram():
    y = np.array([1, 1, 0, 0])
    p = np.array([0.9, 0.9, 0.1, 0.1])
    assert M.expected_calibration_error(y, p) == pytest.approx(0.1)
    assert M.summary(y, p)["f1"] == pytest.approx(1.0)
    h = M.probability_histogram(p, 10)
    assert sum(b["n"] for b in h) == 4 and h[1]["n"] == 2 and h[-1]["n"] == 2  # 0.1 falls in [0.1, 0.2)


def test_constant_prediction_has_no_auc():
    y = np.array([1, 0, 1, 1])
    assert M.summary(y, np.full(4, 0.6))["roc_auc"] is None


def test_cluster_bootstrap_identical_models_and_units():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 400)
    p = rng.uniform(0.2, 0.8, 400)
    r = M.paired_bootstrap_diff(y, p, p, "brier", n_boot=200, clusters=np.repeat(np.arange(100), 4))
    assert r["difference"] == 0 and r["ci95_low"] == 0 and r["ci95_high"] == 0 and r["n_units"] == 100
    assert r["resampling_unit"].startswith("series")


def test_cluster_bootstrap_is_wider_when_errors_are_clustered():
    rng = np.random.default_rng(1)
    n_clusters, size = 200, 5
    shock = np.repeat(rng.normal(0, 0.1, n_clusters), size)  # model difference correlated inside a cluster
    y = rng.integers(0, 2, n_clusters * size)
    base = np.full(len(y), 0.5)
    model = np.clip(0.5 + shock, 0.01, 0.99)
    single = M.paired_bootstrap_diff(y, model, base, n_boot=400)
    clustered = M.paired_bootstrap_diff(y, model, base, n_boot=400, clusters=np.repeat(np.arange(n_clusters), size))
    assert (clustered["ci95_high"] - clustered["ci95_low"]) > (single["ci95_high"] - single["ci95_low"])
