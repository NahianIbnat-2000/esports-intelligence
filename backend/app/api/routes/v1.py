"""Version 1 API. All endpoints are read-only except POST /predictions,
which computes a prediction and stores nothing."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.database.session import get_db
from backend.app.models import DatasetVersion, DataSource, Game, Match
from backend.app.providers.adapters import all_providers
from backend.app.schemas.common import (Envelope, GameInfo, MatchSummary, Meta, PlayerSummary, PredictionRequest,
                                        PredictionResponse, TeamSummary, TournamentSummary)
from backend.app.services import entities, explorer, match_detail, overview, predictions, research
from backend.app.services.common import get_game, meta_for, paginate

router = APIRouter(prefix="/api/v1")
DB = Annotated[Session, Depends(get_db)]
GameQ = Annotated[str, Query(description="Game slug: lol, valorant or cs2")]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=200)]


def _pending(db: Session, game: Game) -> Envelope | None:
    """For games without a verified integration, return an explicit empty
    envelope instead of pretending to have data."""
    if game.status == "integration_pending":
        return Envelope(data=None, meta=meta_for(db, game))
    return None


# ---------------------------------------------------------------- system
@router.api_route("/health", methods=["GET", "HEAD"], tags=["system"], summary="Service and database health")
def health(db: DB) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # pragma: no cover - reported, not raised
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unreachable",
            "time": datetime.now(UTC)}


@router.get("/games", tags=["system"], summary="Supported games and their integration status",
            response_model=Envelope[list[GameInfo]])
def games(db: DB):
    out = []
    for g in db.scalars(select(Game).order_by(Game.id)):
        n, lo, hi = db.execute(select(func.count(Match.id), func.min(Match.match_date), func.max(Match.match_date))
                               .where(Match.game_id == g.id)).one()
        status = g.status
        if g.status == "historical" and n == 0:
            status = "unavailable"
        out.append(GameInfo(slug=g.slug, name=g.name, status=status,
                            status_note=g.status_note if status != "unavailable"
                            else "No historical files have been imported yet.",
                            n_matches=n if g.status != "integration_pending" else None,
                            coverage_start=lo, coverage_end=hi))
    return Envelope(data=out, meta=Meta(data_type="none"))


@router.get("/data-status", tags=["system"], summary="Data availability and freshness per game")
def data_status(db: DB) -> Envelope[list[dict]]:
    return Envelope(data=overview.data_status(db), meta=Meta(data_type="none"))


@router.get("/data-provenance", tags=["system"], summary="Sources, files, cleaning procedure and quality report")
def data_provenance(db: DB) -> Envelope[dict]:
    import json
    from pipelines.oracle_elixir.config import REPORTS_DIR
    sources = [{"key": s.key, "name": s.name, "url": s.url, "data_type": s.data_type,
                "license_note": s.license_note, "attribution": s.attribution}
               for s in db.scalars(select(DataSource).order_by(DataSource.id))]
    files = [{"filename": d.filename, "sha256": d.sha256, "size_bytes": d.file_size_bytes,
              "original_location": d.original_location, "collected_at": d.collected_at, "processed_at": d.processed_at,
              "coverage_start": d.coverage_start, "coverage_end": d.coverage_end, "rows_raw": d.rows_raw,
              "rows_accepted": d.rows_accepted, "rows_excluded": d.rows_excluded,
              "validation_status": d.validation_status, "cleaning_procedure": d.cleaning_procedure}
             for d in db.scalars(select(DatasetVersion).order_by(DatasetVersion.id))]
    qpath = REPORTS_DIR / "data_quality_report.json"
    quality = None
    if qpath.exists() and files:
        q = json.loads(qpath.read_text())
        quality = {k: q.get(k) for k in ("run_id", "generated_at", "counts", "coverage", "data_completeness",
                                         "inspections")}
    return Envelope(data={"sources": sources, "dataset_versions": files, "quality_report": quality,
                          "providers": [p.status() for p in all_providers()]},
                    meta=Meta(data_type="none"))


@router.get("/data-quality", tags=["system"], summary="Detailed data quality report for a game")
def data_quality(db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    return Envelope(data=overview.data_quality_report(db, g), meta=meta_for(db, g))


@router.get("/providers", tags=["system"], summary="Provider adapter status (never exposes keys)")
def providers() -> Envelope[list[dict]]:
    return Envelope(data=[p.status() for p in all_providers()], meta=Meta(data_type="none"))


# --------------------------------------------------------------- overview
@router.get("/overview", tags=["overview"], summary="Dashboard KPIs, rankings, recent games and trends")
def get_overview(db: DB, game: GameQ = "lol", league: str | None = None) -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    data = overview.overview(db, g, league)
    return Envelope(data=data, meta=meta_for(db, g))


# ------------------------------------------------------------ tournaments
@router.get("/tournaments", tags=["tournaments"], response_model=Envelope[list[TournamentSummary]])
def list_tournaments(db: DB, game: GameQ = "lol", page: Page = 1, page_size: PageSize = 25, q: str | None = None,
                     league: str | None = None, year: int | None = None,
                     sort: Annotated[str, Query(pattern="^(recent|matches|name)$")] = "recent"):
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    rows, total = entities.list_tournaments(db, g, page, page_size, q, league, year, sort)
    return Envelope(data=rows, meta=meta_for(db, g, pagination=paginate(total, page, page_size)))


@router.get("/tournaments/filters", tags=["tournaments"], summary="Available leagues and years")
def tournament_filters(db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    return Envelope(data=entities.tournament_filters(db, g), meta=meta_for(db, g))


@router.get("/tournaments/{slug}", tags=["tournaments"])
def tournament(slug: str, db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    return Envelope(data=entities.tournament_detail(db, g, slug), meta=meta_for(db, g))


# ------------------------------------------------------------------ teams
@router.get("/teams", tags=["teams"], response_model=Envelope[list[TeamSummary]])
def list_teams(db: DB, game: GameQ = "lol", page: Page = 1, page_size: PageSize = 25, q: str | None = None,
               league: str | None = None, min_matches: Annotated[int, Query(ge=0)] = 1,
               sort: Annotated[str, Query(pattern="^(elo|matches|win_rate|name|recent)$")] = "matches"):
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    rows, total = entities.list_teams(db, g, page, page_size, q, league, min_matches, sort)
    return Envelope(data=rows, meta=meta_for(db, g, pagination=paginate(total, page, page_size)))


@router.get("/teams/compare", tags=["teams"], summary="Head-to-head record and Elo paths of two teams")
def compare_teams(db: DB, a: str, b: str, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    return Envelope(data=entities.head_to_head(db, g, a, b), meta=meta_for(db, g))


@router.get("/teams/{slug}", tags=["teams"])
def team(slug: str, db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    return Envelope(data=entities.team_detail(db, g, slug), meta=meta_for(db, g))


# ---------------------------------------------------------------- players
@router.get("/players", tags=["players"], response_model=Envelope[list[PlayerSummary]])
def list_players(db: DB, game: GameQ = "lol", page: Page = 1, page_size: PageSize = 25, q: str | None = None,
                 position: Annotated[str | None, Query(pattern="^(top|jng|mid|bot|sup)$")] = None,
                 min_matches: Annotated[int, Query(ge=0)] = 1,
                 sort: Annotated[str, Query(pattern="^(matches|name|recent)$")] = "matches"):
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    rows, total = entities.list_players(db, g, page, page_size, q, position, min_matches, sort)
    return Envelope(data=rows, meta=meta_for(db, g, pagination=paginate(total, page, page_size)))


@router.get("/players/compare", tags=["players"], summary="Compare two players on documented metrics")
def compare_players(db: DB, a: str, b: str, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    return Envelope(data=entities.compare_players(db, g, a, b), meta=meta_for(db, g))


@router.get("/players/{slug}", tags=["players"])
def player(slug: str, db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    return Envelope(data=entities.player_detail(db, g, slug), meta=meta_for(db, g))


# ---------------------------------------------------------------- matches
@router.get("/matches", tags=["matches"], response_model=Envelope[list[MatchSummary]])
def list_matches(db: DB, game: GameQ = "lol", page: Page = 1, page_size: PageSize = 25, team: str | None = None,
                 tournament: str | None = None, league: str | None = None, date_from: datetime | None = None,
                 date_to: datetime | None = None):
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    rows, total = entities.list_matches(db, g, page, page_size, team, tournament, league, date_from, date_to)
    return Envelope(data=rows, meta=meta_for(db, g, pagination=paginate(total, page, page_size)))


@router.get("/matches/{match_id}", tags=["matches"], summary="Match centre: one game with team, player, Elo and model data")
def get_match(match_id: int, db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    return Envelope(data=match_detail.match_detail(db, g, match_id), meta=meta_for(db, g))


# -------------------------------------------------------------- analytics
@router.get("/analytics/team-performance", tags=["analytics"])
def team_performance(db: DB, game: GameQ = "lol", league: str | None = None,
                     min_matches: Annotated[int, Query(ge=1)] = 20) -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    return Envelope(data=overview.team_performance(db, g, league, min_matches), meta=meta_for(db, g))


@router.get("/analytics/player-performance", tags=["analytics"])
def player_performance(db: DB, game: GameQ = "lol", metric: str = "dpm",
                       position: Annotated[str | None, Query(pattern="^(top|jng|mid|bot|sup)$")] = None,
                       min_matches: Annotated[int, Query(ge=1)] = 20, year: int | None = None) -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    if metric not in entities.PLAYER_METRICS:
        raise HTTPException(422, f"metric must be one of {sorted(entities.PLAYER_METRICS)}")
    return Envelope(data=overview.player_performance(db, g, metric, position, min_matches, year), meta=meta_for(db, g))


def _analysis_envelope(db: Session, g: Game, keys: list[str]) -> Envelope[dict]:
    data, when = {}, None
    for k in keys:
        payload, gen = overview.analysis(db, g, k)
        data[k] = payload
        when = when or gen
    status = "available" if any(v is not None for v in data.values()) else "empty"
    m = meta_for(db, g, data_status=status)
    if when:
        m.notes.append(f"Computed {when:%Y-%m-%d %H:%M} UTC by analytics.run_all.")
    return Envelope(data=data if status == "available" else None, meta=m)


@router.get("/analytics/competitive-balance", tags=["analytics"])
def competitive_balance(db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    return _analysis_envelope(db, g, ["competitive_balance", "title_concentration", "persistence", "upset_rate",
                                      "placements", "team_consistency"])


@router.get("/analytics/historical", tags=["analytics"])
def historical(db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    data = overview.historical(db, g)
    data["season_trends"], _ = overview.analysis(db, g, "season_trends")
    return Envelope(data=data, meta=meta_for(db, g))


@router.get("/analytics/team-trajectories", tags=["analytics"], summary="Elo histories for up to 6 teams")
def team_trajectories(db: DB, teams: str, game: GameQ = "lol") -> Envelope[list[dict]]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    slugs = [t for t in teams.split(",") if t][:6]
    out = []
    for s in slugs:
        t = entities._team(db, g, s)
        out.append({"slug": t.slug, "name": t.name, "league": t.primary_league,
                    "history": entities.elo_history(db, g, t.id, 250)})
    return Envelope(data=out, meta=meta_for(db, g))


@router.get("/analytics/regional", tags=["analytics"], summary="League-level (competitive region) analysis")
def regional(db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    env = _analysis_envelope(db, g, ["regional"])
    from backend.app.models import ModelVersion
    from backend.app.services.overview import international_leagues_linked
    elo = db.scalar(select(ModelVersion).where(ModelVersion.game_id == g.id, ModelVersion.model_key == "elo"))
    levels = (elo.hyperparameters or {}).get("league_levels") if elo else None
    if env.data is not None and levels:
        linked = set(international_leagues_linked(db, g))
        env.data["league_levels"] = {
            "k_league": elo.hyperparameters.get("k_league"),
            "definition": "League level from Elo with league offsets, as an offset from the 1500 start. Levels are "
                          "only comparable between leagues that play each other often. 'Linked' = leagues with "
                          "50+ games at Worlds, MSI, First Stand or the Esports World Cup in the last three years; "
                          "other leagues are compared mainly with their own regional neighbours (e.g. European "
                          "regional leagues through European Masters).",
            "leagues": [{**r, "linked_to_international": r["league"] in linked} for r in levels]}
    env.meta.notes.append("The source has no country, nationality, or headquarters fields. Geographic (country) "
                          "analysis is therefore not available; leagues are competitive regions.")
    return env


# ------------------------------------------------------------ predictions
@router.get("/predictions/models", tags=["predictions"], summary="Model versions, periods and evaluation metrics")
def prediction_models(db: DB, game: GameQ = "lol") -> Envelope[list[dict]]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    rows = predictions.models_payload(db, g)
    status = "available" if rows and all(r["status"] == "trained" for r in rows) else (
        "insufficient_data" if rows else "unavailable")
    m = meta_for(db, g, data_status=status)
    return Envelope(data=rows or None, meta=m)


@router.get("/predictions/test-matches", tags=["predictions"],
            summary="Stored out-of-sample predictions for test-period games, with outcomes")
def prediction_test_matches(db: DB, game: GameQ = "lol", team: str | None = None,
                            limit: Annotated[int, Query(ge=1, le=200)] = 50) -> Envelope[list[dict]]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    return Envelope(data=predictions.test_predictions(db, g, team, limit), meta=meta_for(db, g))


@router.get("/predictions/history", tags=["predictions"],
            summary="Stored out-of-sample predictions with outcomes, model versions and monthly Brier scores")
def prediction_history(db: DB, game: GameQ = "lol", team: str | None = None, league: str | None = None,
                       date_from: datetime | None = None, date_to: datetime | None = None,
                       split: Annotated[str | None, Query(pattern="^(validation|test)$")] = None,
                       page: Page = 1, page_size: PageSize = 50) -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    rows, total, meta = predictions.history(db, g, team, league, date_from, date_to, split, page, page_size)
    return Envelope(data={"rows": rows, **meta},
                    meta=meta_for(db, g, pagination=paginate(total, page, page_size)))


@router.post("/predictions", tags=["predictions"], response_model=PredictionResponse,
             summary="Out-of-sample win probability for two teams as of a date")
def predict(req: PredictionRequest, db: DB):
    g = get_game(db, req.game)
    return predictions.predict(db, g, req)


# --------------------------------------------------------------- research
@router.get("/research", tags=["research"])
def research_list(db: DB, game: GameQ = "lol") -> Envelope[list[dict]]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    # The report list is shown even without data: unrun reports are labelled "proposed".
    m = meta_for(db, g)
    m.data_status = "available"
    return Envelope(data=research.list_reports(db, g), meta=m)


@router.get("/research/{slug}", tags=["research"])
def research_report(slug: str, db: DB, game: GameQ = "lol") -> Envelope[dict]:
    g = get_game(db, game)
    m = meta_for(db, g)
    m.data_status = "available"
    return Envelope(data=research.get_report(db, g, slug), meta=m)


# ---------------------------------------------------------- data explorer
@router.get("/data-explorer/datasets", tags=["data explorer"], summary="Datasets and data dictionary")
def explorer_datasets() -> Envelope[list[dict]]:
    return Envelope(data=explorer.describe(), meta=Meta(data_type="none"))


def _explorer_args(dataset: str, page: int, page_size: int, columns: str | None, q: str | None,
                   league: str | None, date_from: datetime | None, date_to: datetime | None, sort: str | None,
                   order: str, season: int | None = None, tournament: str | None = None, team: str | None = None,
                   player: str | None = None, position: str | None = None) -> dict[str, Any]:
    return dict(dataset=dataset, page=page, page_size=page_size,
                columns=[c for c in columns.split(",") if c] if columns else None, q=q, league=league,
                date_from=date_from, date_to=date_to, sort=sort, order=order, season=season,
                tournament=tournament, team=team, player=player, position=position)


@router.get("/data-explorer", tags=["data explorer"])
def explorer_query(db: DB, dataset: str = "matches", game: GameQ = "lol", page: Page = 1, page_size: PageSize = 50,
                   columns: str | None = None, q: str | None = None, league: str | None = None,
                   date_from: datetime | None = None, date_to: datetime | None = None, sort: str | None = None,
                   order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc", season: int | None = None,
                   tournament: str | None = None, team: str | None = None, player: str | None = None,
                   position: Annotated[str | None, Query(pattern="^(top|jng|mid|bot|sup)$")] = None
                   ) -> Envelope[dict]:
    g = get_game(db, game)
    if (p := _pending(db, g)):
        return p
    cols, rows, total = explorer.query(db, g, **_explorer_args(dataset, page, page_size, columns, q, league,
                                                                date_from, date_to, sort, order, season,
                                                                tournament, team, player, position))
    return Envelope(data={"columns": cols, "rows": rows},
                    meta=meta_for(db, g, pagination=paginate(total, page, page_size)))


@router.get("/data-explorer/export", tags=["data explorer"], summary="CSV export of the current selection")
def explorer_export(db: DB, dataset: str = "matches", game: GameQ = "lol", columns: str | None = None,
                    q: str | None = None, league: str | None = None, date_from: datetime | None = None,
                    date_to: datetime | None = None, sort: str | None = None,
                    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc", season: int | None = None,
                    tournament: str | None = None, team: str | None = None, player: str | None = None,
                    position: Annotated[str | None, Query(pattern="^(top|jng|mid|bot|sup)$")] = None):
    s = get_settings()
    if not s.allow_csv_export:
        raise HTTPException(403, "CSV export is disabled on this deployment.")
    g = get_game(db, game)
    if g.status == "integration_pending":
        raise HTTPException(409, "No data for this game.")
    cols, rows, total = explorer.query(db, g, **_explorer_args(dataset, 1, s.max_export_rows, columns, q, league,
                                                                date_from, date_to, sort, order, season,
                                                                tournament, team, player, position))
    src = meta_for(db, g).attribution or ""
    body = explorer.to_csv(cols, rows, src)
    return Response(content=body, media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="esports-intelligence_{dataset}.csv"',
        # HTTP headers must be latin-1; the full attribution is also in /data-provenance
        "X-Data-Attribution": src.replace("©", "(c)").encode("ascii", "replace").decode(), "X-Rows-Exported": str(len(rows)), "X-Rows-Matching": str(total)})
