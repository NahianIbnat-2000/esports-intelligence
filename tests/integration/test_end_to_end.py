"""End-to-end: empty database states, pipeline load (twice, idempotent),
model training, analytics, and every API endpoint. SQLite test database;
SYNTHETIC fixture data only."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.database.session import get_sessionmaker
from backend.app.main import create_app
from backend.app.models import LolPlayerMatchStats, Match, PlayerMatchStatistic, Team
from backend.app.services.common import clear_all_caches


@pytest.fixture(scope="module")
def client(fresh_db):
    with TestClient(create_app()) as c:
        yield c


# ------------------------------------------------------- before any data
def test_empty_database_shows_unavailable_not_zero(client):
    clear_all_caches()
    r = client.get("/api/v1/overview?game=lol").json()
    assert r["meta"]["data_status"] == "empty"
    assert r["data"]["kpis"]["matches"] is None and r["data"]["kpis"]["prize_money"] is None
    g = {x["slug"]: x for x in client.get("/api/v1/games").json()["data"]}
    assert g["lol"]["status"] == "unavailable"
    assert g["valorant"]["status"] == "integration_pending" and g["cs2"]["status"] == "integration_pending"


def test_predictions_unavailable_before_training(client):
    r = client.post("/api/v1/predictions", json={"team_a": "x", "team_b": "y", "as_of": "2030-01-01"})
    assert r.status_code == 409
    assert "unavailable" in r.json()["detail"].lower()


def test_research_is_proposed_before_data(client):
    rows = client.get("/api/v1/research").json()["data"]
    assert rows and all(r["status"] == "proposed" for r in rows)


def test_pending_games_return_no_data(client):
    for path in ("/overview", "/tournaments", "/teams", "/players", "/matches", "/analytics/competitive-balance",
                 "/predictions/models", "/research", "/data-explorer"):
        r = client.get(f"/api/v1{path}?game=valorant").json()
        assert r["data"] is None and r["meta"]["data_status"] == "integration_pending", path
    assert client.post("/api/v1/predictions", json={"game": "cs2", "team_a": "a", "team_b": "b",
                                                    "as_of": "2030-01-01"}).status_code == 409


# ------------------------------------------------------------ load data
@pytest.fixture(scope="module")
def loaded(client, fixture_csv):
    from analytics.run_all import run as run_analytics
    from machine_learning.training.persist import persist
    from machine_learning.training.train import train
    from pipelines.oracle_elixir.config import PROCESSED_DIR
    from pipelines.oracle_elixir.download import registered_files
    from pipelines.oracle_elixir.run import run as run_pipeline
    res = run_pipeline([str(fixture_csv)])
    assert res["status"] == "ok"
    first = res["quality"]["loaded"]
    res2 = run_pipeline([str(fixture_csv)])  # same file again: idempotent
    out = train(PROCESSED_DIR, __import__("pathlib").Path(os.environ["MODELS_DIR"]), registered_files())
    assert out["result"]["status"] == "trained"
    persist(out)
    assert run_analytics()["status"] == "ok"
    clear_all_caches()
    return first, res2["quality"]["loaded"], out["result"]


def test_pipeline_is_idempotent(loaded):
    first, second, _ = loaded
    assert first == second
    with get_sessionmaker()() as db:
        assert db.scalar(select(func.count(Match.id))) == first["matches"]


def test_raw_file_preserved_once(loaded, fixture_csv):
    from pipelines.oracle_elixir.download import load_manifest
    assert len(load_manifest()["files"]) == 1


def test_null_statistics_stored_as_null(loaded):
    with get_sessionmaker()() as db:
        n_null = db.scalar(select(func.count()).select_from(LolPlayerMatchStats).where(LolPlayerMatchStats.dpm.is_(None)))
        n_zero = db.scalar(select(func.count()).select_from(LolPlayerMatchStats).where(LolPlayerMatchStats.dpm == 0))
        assert n_null > 0 and n_zero == 0
        assert db.scalar(select(func.count(PlayerMatchStatistic.id))) > 0


def test_models_are_evaluated_on_identical_test_games(loaded):
    r = loaded[2]
    ns = {k: v["test"]["n"] for k, v in r["evaluation"].items()}
    assert len(set(ns.values())) == 1
    assert r["split"]["train_end"] < r["split"]["validation_end"]


def test_overview_with_data(client, loaded):
    r = client.get("/api/v1/overview?game=lol").json()
    assert r["meta"]["data_status"] == "available" and r["meta"]["data_type"] == "historical"
    k = r["data"]["kpis"]
    assert k["matches"] == loaded[0]["matches"] and k["teams"] == loaded[0]["teams"]
    assert k["prize_money"] is None
    assert r["data"]["research"] is not None


@pytest.mark.parametrize("path", [
    "/health", "/games", "/data-status", "/data-provenance", "/providers", "/tournaments", "/tournaments/filters",
    "/teams?sort=elo", "/players?position=mid", "/matches?page_size=5", "/analytics/team-performance",
    "/analytics/player-performance?metric=cspm&position=mid&min_matches=5", "/analytics/competitive-balance",
    "/analytics/historical", "/analytics/regional", "/predictions/models", "/predictions/test-matches",
    "/research", "/research/can-machine-learning-beat-elo", "/research/competitive-balance",
    "/research/evolution-of-team-performance", "/research/concentration-of-tournament-success",
    "/data-explorer/datasets", "/data-explorer?dataset=player_games&columns=player,kda&sort=kda",
    "/data-explorer?dataset=teams", "/data-explorer?dataset=tournaments", "/data-explorer?dataset=team_games&q=SYNTH",
    "/data-quality", "/predictions/history?split=test&page_size=5", "/analytics/team-trajectories?teams=synth-team-01",
    "/analytics/player-performance?metric=kill_participation&position=sup&min_matches=5",
    "/data-explorer?dataset=player_games&position=mid&season=2023&page_size=3",
])
def test_endpoints_ok(client, loaded, path):
    r = client.get(f"/api/v1{path}")
    assert r.status_code == 200, r.text


def test_detail_endpoints(client, loaded):
    team = client.get("/api/v1/teams?sort=elo&page_size=2").json()["data"]
    a, b = team[0]["slug"], team[1]["slug"]
    d = client.get(f"/api/v1/teams/{a}").json()["data"]
    assert d["elo_history"] and len(d["recent_form"]) == 10
    assert client.get(f"/api/v1/teams/compare?a={a}&b={b}").json()["data"]["games"] > 0
    t = client.get("/api/v1/tournaments").json()["data"][0]["slug"]
    assert client.get(f"/api/v1/tournaments/{t}").json()["data"]["standings_all"]
    p = client.get("/api/v1/players?page_size=2").json()["data"]
    assert client.get(f"/api/v1/players/{p[0]['slug']}").json()["data"]["career"]["games"] > 0
    cmp = client.get(f"/api/v1/players/compare?a={p[0]['slug']}&b={p[1]['slug']}").json()["data"]
    assert "metric_definitions" in cmp
    assert client.get("/api/v1/teams/does-not-exist").status_code == 404


def test_prediction_rules(client, loaded):
    r = loaded[2]
    teams = client.get("/api/v1/teams?sort=elo&page_size=2").json()["data"]
    a, b = teams[0]["slug"], teams[1]["slug"]
    in_sample = r["split"]["train_end"][:10]
    assert client.post("/api/v1/predictions", json={"team_a": a, "team_b": b, "as_of": in_sample}).status_code == 422
    assert client.post("/api/v1/predictions", json={"team_a": a, "team_b": a, "as_of": "2030-01-01"}).status_code == 422
    ok = client.post("/api/v1/predictions", json={"team_a": a, "team_b": b, "as_of": r["split"]["data_end"][:10],
                                                  "team_a_side": "unknown"})
    assert ok.status_code == 200, ok.text
    body = ok.json()
    for p in body["predictions"]:
        assert p["status"] == "trained"
        assert 0 < p["prob_team_a"] < 1 and p["prob_team_a"] + p["prob_team_b"] == pytest.approx(1)
    assert body["team_a"]["elo"] > body["team_b"]["elo"]
    assert body["predictions"][0]["prob_team_a"] > 0.5  # higher Elo -> favoured by Elo
    # side symmetry: A blue vs A red average equals 'unknown'
    pb = client.post("/api/v1/predictions", json={"team_a": a, "team_b": b, "as_of": r["split"]["data_end"][:10],
                                                  "team_a_side": "blue"}).json()["predictions"][0]["prob_team_a"]
    assert pb == pytest.approx(body["predictions"][0]["prob_team_a"])  # pure Elo has no side term
    assert any("guarantee" in c for c in body["caveats"])


def test_csv_export(client, loaded):
    r = client.get("/api/v1/data-explorer/export?dataset=matches&columns=game_id,winner")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0] == "game_id,winner" and len(lines) > 1
    assert "Oracle" in r.headers["x-data-attribution"]


def test_validation_errors(client, loaded):
    assert client.get("/api/v1/teams?page_size=1000").status_code == 422
    assert client.get("/api/v1/players?position=goalkeeper").status_code == 422
    assert client.get("/api/v1/analytics/player-performance?metric=bogus").status_code == 422
    assert client.get("/api/v1/data-explorer?dataset=secrets").status_code == 404
    assert client.get("/api/v1/overview?game=fifa").status_code == 404


def test_no_credentials_in_responses(client, loaded):
    body = client.get("/api/v1/data-provenance").text + client.get("/api/v1/providers").text
    assert "bearer" not in body.lower() and "x-riot-token" not in body.lower()
    assert '"configured":false' in body.replace(" ", "")
    assert "sqlite:///" not in body and "postgresql" not in body


def test_baselines_and_new_metrics(client, loaded):
    models = {m["model_key"]: m for m in client.get("/api/v1/predictions/models").json()["data"]}
    assert {"baseline_50", "baseline_prevalence", "elo", "elo_logit", "logreg"} <= set(models)
    b50 = models["baseline_50"]["metrics"]["test"]
    assert b50["brier"] == pytest.approx(0.25) and b50["roc_auc"] is None
    for k in ("elo", "logreg"):
        t = models[k]["metrics"]["test"]
        assert 0 <= t["ece"] < 0.5 and 0 <= t["f1"] <= 1
        assert sum(b["n"] for b in models[k]["metrics"]["probability_histogram"]) == t["n"]
    comps = models["logreg"]["metrics"]["comparisons"]
    assert comps["logreg_vs_elo_brier"]["resampling_unit"].startswith("series")
    assert "logreg_vs_elo_logit_brier_tournament_clusters" in comps
    ov = client.get("/api/v1/overview").json()["data"]
    assert ov["research"]["best_by_brier"] in models and ov["coverage"]["by_calendar_year"]
    assert ov["data_quality"]["duplicate_rows_exact"] == 1  # the fixture injects one duplicate row
    assert ov["data_quality"]["invalid_game_ids"] == 1      # and one game with a missing team row
    assert ov["elo_method"]["k"] is not None


def test_prediction_explanation_adds_up(client, loaded):
    r = loaded[2]
    teams = client.get("/api/v1/teams?sort=elo&page_size=2").json()["data"]
    body = client.post("/api/v1/predictions", json={"team_a": teams[0]["slug"], "team_b": teams[1]["slug"],
                                                     "as_of": r["split"]["data_end"][:10]}).json()
    e = body["explanation"]
    c = e["logreg_contributions"]
    assert c["intercept"] + sum(f["contribution_log_odds"] for f in c["features"]) == pytest.approx(c["logit"])
    assert e["head_to_head_before_date"]["games"] >= 0 and e["summary"]
    assert e["elo_difference_a_minus_b"] == pytest.approx(body["team_a"]["elo"] - body["team_b"]["elo"])


def test_history_only_out_of_sample(client, loaded):
    d = client.get("/api/v1/predictions/history?page_size=200").json()
    assert {r["split"] for r in d["data"]["rows"]} <= {"validation", "test"}
    assert set(d["data"]["versions"]) == {"elo", "elo_logit", "logreg"}


def test_explorer_filters_apply(client, loaded):
    d = client.get("/api/v1/data-explorer?dataset=player_games&position=mid&page_size=50").json()["data"]
    assert d["rows"] and all(r["position"] == "mid" for r in d["rows"])
    d = client.get("/api/v1/data-explorer?dataset=matches&team=SYNTH Team 01&page_size=50").json()["data"]
    assert all("SYNTH Team 01" in (r["blue_team"], r["red_team"]) for r in d["rows"])


def test_match_centre(client, loaded):
    rows = client.get("/api/v1/matches?game=lol&page_size=5").json()["data"]
    d = client.get(f"/api/v1/matches/{rows[0]['id']}?game=lol").json()["data"]
    blue, red = d["blue"], d["red"]
    assert blue["won"] != red["won"]
    # Elo points exchanged add up to zero and expected scores to one
    assert abs(blue["elo"]["change"] + red["elo"]["change"]) < 1e-6
    assert abs(blue["elo"]["expected_score"] + red["elo"]["expected_score"] - 1) < 1e-6
    # current game is in its own series; series wins match the listed games
    assert any(g["current"] for g in d["series"])
    assert blue["series_wins"] + red["series_wins"] == len(d["series"])
    # form uses only earlier games
    assert all(f["date"] <= d["match_date"] for f in blue["form"] + red["form"])
    assert d["match_date"] not in [f["date"] for f in blue["form"] if f["match_id"] == d["id"]]
    # top performer comes from the winning team
    win = blue if blue["won"] else red
    if d["top_performer"]:
        assert d["top_performer"]["slug"] in {p["slug"] for p in win["players"]}
    assert client.get("/api/v1/matches/999999999?game=lol").status_code == 404


def test_health_accepts_head(client):
    assert client.head("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").json()["database"] == "ok"


def test_series_grouping(client, loaded):
    body = client.get("/api/v1/series?game=lol&page_size=200").json()
    rows = body["data"]
    assert rows and body["meta"]["pagination"]["total"] >= len(rows)
    total_games = client.get("/api/v1/matches?game=lol&page_size=1").json()["meta"]["pagination"]["total"]
    all_rows = client.get(f"/api/v1/series?game=lol&page_size=200").json()["meta"]["pagination"]["total"]
    assert all_rows <= total_games
    for r in rows:
        assert r["wins_a"] + r["wins_b"] == r["n_games"] == len(r["games"])
        if r["winner_slug"]:
            assert r["winner_slug"] in (r["team_a_slug"], r["team_b_slug"])
    ends = [r["end"] for r in rows]
    assert ends == sorted(ends, reverse=True)
    # the match centre groups a game into the same series
    r = next(r for r in rows if r["n_games"] > 1) if any(r["n_games"] > 1 for r in rows) else rows[0]
    d = client.get(f"/api/v1/matches/{r['games'][0]['id']}?game=lol").json()["data"]
    assert [g["id"] for g in d["series"]] == [g["id"] for g in r["games"]]


def test_trajectory_defaults(client, loaded):
    d = client.get("/api/v1/analytics/team-performance?game=lol&min_matches=1&scope=all").json()["data"]
    assert 0 < len(d["default_trajectory_teams"]) <= 5
    assert set(d["default_trajectory_teams"]) <= {t["slug"] for t in d["teams"]}
    linked = client.get("/api/v1/analytics/team-performance?game=lol&min_matches=1").json()["data"]
    assert linked["n_ranked"] <= d["n_ranked"]
    assert all(t["primary_league"] in linked["linked_leagues"] for t in linked["teams"]) or not linked["linked_leagues"]
