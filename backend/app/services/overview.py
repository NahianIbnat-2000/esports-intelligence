"""Overview dashboard and analytics endpoints."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import case, desc, func, select
from sqlalchemy.orm import Session

from backend.app.models import (AnalysisOutput, DataIngestionLog, DatasetVersion, Game, LolPlayerMatchStats,  # noqa: F401
                                LolTeamMatchStats, Match, ModelVersion, Player, PlayerMatchStatistic, Team,
                                TeamMatchStatistic, Tournament)
from backend.app.services.common import ttl_cache
from backend.app.services.entities import PLAYER_METRICS, list_matches, list_teams


def kpis(db: Session, game: Game) -> dict:
    """Counts straight from the database. Null when nothing is loaded."""
    n_matches = db.scalar(select(func.count()).where(Match.game_id == game.id)) or 0
    if n_matches == 0:
        return {"matches": None, "teams": None, "players": None, "tournaments": None, "leagues": None,
                "coverage_start": None, "coverage_end": None, "prize_money": None}
    lo, hi = db.execute(select(func.min(Match.match_date), func.max(Match.match_date))
                        .where(Match.game_id == game.id)).one()
    return {
        "matches": n_matches,
        "teams": db.scalar(select(func.count()).where(Team.game_id == game.id)),
        "players": db.scalar(select(func.count()).where(Player.game_id == game.id)),
        "tournaments": db.scalar(select(func.count()).where(Tournament.game_id == game.id)),
        "leagues": db.scalar(select(func.count(func.distinct(Tournament.league))).where(Tournament.game_id == game.id)),
        "coverage_start": lo, "coverage_end": hi,
        # Oracle's Elixir has no prize money field. Never estimated.
        "prize_money": None,
    }


def matches_per_month(db: Session, game: Game, league: str | None = None) -> list[dict]:
    month = func.date_trunc("month", Match.match_date) if db.bind.dialect.name == "postgresql" \
        else func.strftime("%Y-%m-01", Match.match_date)
    q = select(month.label("m"), func.count()).where(Match.game_id == game.id)
    if league:
        q = q.join(Tournament, Tournament.id == Match.tournament_id).where(Tournament.league == league)
    rows = db.execute(q.group_by(month).order_by(month)).all()
    return [{"month": str(m)[:7], "matches": int(n)} for m, n in rows]


def matches_by_league(db: Session, game: Game, limit: int = 12) -> list[dict]:
    rows = db.execute(select(Tournament.league, func.count(Match.id)).join(Match, Match.tournament_id == Tournament.id)
                      .where(Tournament.game_id == game.id).group_by(Tournament.league)
                      .order_by(desc(func.count(Match.id))).limit(limit)).all()
    return [{"league": l, "matches": int(n)} for l, n in rows]


def research_highlights(db: Session, game: Game) -> dict | None:
    mvs = {m.model_key: m for m in db.scalars(select(ModelVersion).where(ModelVersion.game_id == game.id))}
    if not mvs or any(m.status != "trained" for m in mvs.values()):
        return None
    out = {k: {"display_name": m.display_name, "brier": m.metrics["test"]["brier"],
               "accuracy": m.metrics["test"]["accuracy"], "log_loss": m.metrics["test"]["log_loss"],
               "f1": m.metrics["test"].get("f1"), "n_test": m.metrics["test"]["n"]} for k, m in mvs.items()}
    comps = {}
    for m in mvs.values():
        comps.update((m.metrics or {}).get("comparisons", {}))
    best_brier = min(out, key=lambda k: out[k]["brier"])
    best_acc = max(out, key=lambda k: out[k]["accuracy"])
    best_f1 = max(out, key=lambda k: out[k]["f1"] or 0)
    vs_elo = {k: comps.get(f"{k}_vs_elo_brier") for k in ("elo_logit", "logreg")}
    return {"models": out, "best_by_brier": best_brier, "best_by_accuracy": best_acc, "best_by_f1": best_f1,
            "vs_elo_brier": vs_elo, "logreg_vs_elo_brier": comps.get("logreg_vs_elo_brier"),
            "test_period": mvs["elo"].periods.get("test"), "version": mvs["elo"].version,
            "note": "The best model by accuracy is not necessarily the best probabilistic model: accuracy only "
                    "checks which side of 50% a probability falls on, while Brier score and log loss judge the "
                    "probability itself."}


def coverage(db: Session, game: Game) -> dict:
    year = func.extract("year", Match.match_date)
    by_year = db.execute(select(year, func.count(Match.id)).where(Match.game_id == game.id)
                         .group_by(year).order_by(year)).all()
    by_league = db.execute(select(Tournament.league, func.count(Match.id))
                           .join(Match, Match.tournament_id == Tournament.id).where(Tournament.game_id == game.id)
                           .group_by(Tournament.league).order_by(desc(func.count(Match.id)))).all()
    top = [{"league": l, "games": int(n)} for l, n in by_league[:15]]
    rest = sum(int(n) for _, n in by_league[15:])
    return {"by_calendar_year": [{"year": int(y), "games": int(n)} for y, n in by_year],
            "by_league": top, "other_leagues": {"leagues": max(0, len(by_league) - 15), "games": rest},
            "definition": "Calendar year of the game date. League = competitive region or event code from the source."}


def data_quality(db: Session, game: Game) -> dict:
    """Headline data-quality figures from the last pipeline run and the database."""
    import json

    from pipelines.oracle_elixir.config import REPORTS_DIR
    q = {}
    path = REPORTS_DIR / "data_quality_report.json"
    if path.exists():
        q = json.loads(path.read_text()).get("counts", {})
    n_games = db.scalar(select(func.count()).where(Match.game_id == game.id)) or 0
    last = db.execute(select(DataIngestionLog.run_id, DataIngestionLog.stage, DataIngestionLog.status,
                             DataIngestionLog.logged_at)
                      .where(DataIngestionLog.game_id == game.id).order_by(desc(DataIngestionLog.logged_at))
                      .limit(1)).first()
    stages = []
    if last:
        stages = [{"stage": st, "status": stt, "at": at} for st, stt, at in db.execute(
            select(DataIngestionLog.stage, DataIngestionLog.status, DataIngestionLog.logged_at)
            .where(DataIngestionLog.run_id == last[0]).order_by(DataIngestionLog.logged_at)).all()]
    missing_15 = db.scalar(select(func.avg(case((LolTeamMatchStats.golddiff_at_15.is_(None), 1.0), else_=0.0))))
    partial = db.scalar(select(func.count()).where(Match.game_id == game.id, Match.data_completeness == "partial"))
    return {
        "games_loaded": n_games,
        "duplicate_rows_exact": q.get("rows_duplicate_exact"),
        "duplicate_rows_conflicting": q.get("rows_duplicate_conflicting"),
        "rows_retrieved": q.get("rows_retrieved"),
        "rows_excluded_total": q.get("rows_excluded_total"),
        "games_excluded": q.get("games_excluded"),
        "games_excluded_by_reason": q.get("games_excluded_by_reason"),
        "invalid_game_ids": q.get("games_excluded"),
        "partial_games": partial, "partial_share": partial / n_games if n_games else None,
        "team_games_missing_15min_stats_share": float(missing_15) if missing_15 is not None else None,
        "teams_without_source_id": db.scalar(select(func.count()).where(Team.game_id == game.id, Team.id_from_name)),
        "players_without_source_id": db.scalar(select(func.count()).where(Player.game_id == game.id,
                                                                          Player.id_from_name)),
        "last_run": {"run_id": last[0], "status": "ok" if all(s["status"] != "error" for s in stages) else "error",
                     "stages": stages} if last else None,
        "definitions": {
            "invalid_game_ids": "Games whose rows fail the structure checks (two team rows, Blue + Red, two "
                                "different teams, one winner, one date).",
            "teams_without_source_id": "Teams with no source teamid; identified by name (unmatched identifiers).",
            "partial_games": "Source flag datacompleteness = partial: detailed stats such as 15-minute "
                             "differences are missing and stored as null.",
        },
    }


def elo_method(db: Session, game: Game) -> dict | None:
    mv = db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == "elo"))
    if mv is None:
        return None
    hp = mv.hyperparameters or {}
    el = db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == "elo_logit"))
    return {"version": mv.version, "initial": hp.get("initial"), "k": hp.get("k"),
            "carryover_shrink": hp.get("carryover_shrink"), "k_league": hp.get("k_league"),
            "blue_win_prob_equal_elo": (el.hyperparameters or {}).get("implied_blue_win_prob_equal_elo") if el else None,
            "data_start": (mv.periods or {}).get("data_start"), "data_end": (mv.periods or {}).get("data_end"),
            "train_end": (mv.periods or {}).get("train_end"),
            "validation_end": (mv.periods or {}).get("validation_end"),
            "selection": "K, season shrinkage and k_league chosen by validation log loss; the test period was not "
                         "used."}


def data_quality_report(db: Session, game: Game) -> dict:
    """Detailed report: pipeline counts, exclusions by reason and file,
    missing values in important columns, unmatched identifiers by league."""
    import json

    import pandas as pd

    from pipelines.oracle_elixir.config import REPORTS_DIR
    out = data_quality(db, game)
    path = REPORTS_DIR / "data_quality_report.json"
    q = json.loads(path.read_text()) if path.exists() else {}
    out["pipeline_counts"] = q.get("counts")
    out["inspections"] = q.get("inspections")
    out["cleaning_procedure"] = q.get("cleaning_procedure")
    ex = REPORTS_DIR / "exclusions.csv"
    if ex.exists():
        e = pd.read_csv(ex)
        out["exclusions_by_reason"] = e.groupby("reason").size().sort_values(ascending=False) \
            .rename("rows").reset_index().to_dict("records")
        out["exclusions_by_file"] = e.groupby("source_file").size().rename("rows").reset_index().to_dict("records")
    def share_null(col, model):
        v = db.scalar(select(func.avg(case((col.is_(None), 1.0), else_=0.0))).select_from(model))
        return None if v is None else float(v)
    S, T = LolPlayerMatchStats, LolTeamMatchStats
    out["missing_values"] = [
        {"table": "matches", "column": "duration_seconds", "share_missing": share_null(Match.duration_seconds, Match)},
        {"table": "matches", "column": "patch", "share_missing": share_null(Match.patch, Match)},
        {"table": "matches", "column": "playoffs", "share_missing": share_null(Match.playoffs, Match)},
        {"table": "team stats", "column": "golddiff_at_15", "share_missing": share_null(T.golddiff_at_15, T)},
        {"table": "team stats", "column": "dragons", "share_missing": share_null(T.dragons, T)},
        {"table": "team stats", "column": "vision_score", "share_missing": share_null(T.vision_score, T)},
        {"table": "player stats", "column": "champion", "share_missing": share_null(S.champion, S)},
        {"table": "player stats", "column": "dpm", "share_missing": share_null(S.dpm, S)},
        {"table": "player stats", "column": "golddiff_at_15", "share_missing": share_null(S.golddiff_at_15, S)},
        {"table": "player stats", "column": "vspm", "share_missing": share_null(S.vspm, S)},
    ]
    unspecified = db.scalar(select(func.count()).select_from(Match).join(Tournament, Tournament.id == Match.tournament_id)
                            .where(Tournament.game_id == game.id, Tournament.split == "Unspecified"))
    out["games_without_split"] = unspecified
    out["unmatched_by_league"] = [{"league": l, "teams_without_source_id": int(n)} for l, n in db.execute(
        select(Team.primary_league, func.count()).where(Team.game_id == game.id, Team.id_from_name)
        .group_by(Team.primary_league).order_by(desc(func.count())).limit(12)).all()]
    out["known_limitations"] = [
        "No prize money, country, nationality or tournament-name fields in the source.",
        "The source `year` is a season label; some games carry the next season's year.",
        "Games flagged 'partial' lack time-based stats (e.g. 15-minute differences); they are kept, with nulls.",
        "Teams and players without a source id are matched by name; renamed entities can split into two records.",
        "Best-of series are not identified in the source; series are approximated where needed.",
    ]
    return out


def international_leagues_linked(db: Session, game: Game, min_games: int = 50, years: int = 3) -> list[str]:
    """Domestic leagues whose teams played at least `min_games` games at
    tier-1 international events in the last `years` years of data. Only these
    leagues share a reasonably common Elo scale: Elo points flow between
    leagues only through games between them."""
    from pipelines.oracle_elixir.config import INTERNATIONAL_LEAGUES
    end = db.scalar(select(func.max(Match.match_date)).where(Match.game_id == game.id))
    if end is None:
        return []
    since = end - timedelta(days=365 * years)
    rows = db.execute(
        select(Team.primary_league, func.count())
        .join(TeamMatchStatistic, TeamMatchStatistic.team_id == Team.id)
        .join(Match, Match.id == TeamMatchStatistic.match_id)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .where(Team.game_id == game.id, Tournament.league.in_(INTERNATIONAL_LEAGUES),
               Team.primary_league.is_not(None), Match.match_date >= since)
        .group_by(Team.primary_league)).all()
    return sorted(l for l, n in rows if n >= min_games)


ELO_SCALE_NOTE = ("Ratings include a league level learned from games between leagues, but they are still only "
                  "comparable between leagues that play each other often. Lower-tier leagues mostly meet their "
                  "regional neighbours, so their level against the major leagues is poorly identified and a "
                  "dominant team in a small league can show a higher Elo than a top team in a major league.")


@ttl_cache(300)
def overview(db: Session, game: Game, league: str | None = None) -> dict:
    k = kpis(db, game)
    if k["matches"] is None:
        return {"kpis": k, "top_teams": [], "recent_matches": [], "matches_per_month": [], "matches_by_league": [],
                "research": None, "latest_ingestion": None}
    active_since = k["coverage_end"] - timedelta(days=180)
    linked = international_leagues_linked(db, game)
    top, _ = list_teams(db, game, 1, 10, None, league, 10, "elo", active_since=active_since,
                        leagues=None if league else linked)
    recent, _ = list_matches(db, game, 1, 10, league=league)
    last_log = db.scalar(select(DataIngestionLog).where(DataIngestionLog.stage == "load",
                                                        DataIngestionLog.status == "ok")
                         .order_by(desc(DataIngestionLog.logged_at)).limit(1))
    return {"kpis": k, "top_teams": [t.model_dump() for t in top],
            "coverage": coverage(db, game), "data_quality": data_quality(db, game), "elo_method": elo_method(db, game),
            "top_teams_definition": "Highest current Elo among teams with at least 10 games and a game in the last "
                                    "180 days of the data. Current Elo = rating after the team's last game. "
                                    + ("Without a league filter, only teams from leagues with at least 50 games at "
                                       "Worlds, MSI, First Stand or the Esports World Cup in the last three years "
                                       f"are ranked ({', '.join(linked)}). " if not league else "")
                                    + ELO_SCALE_NOTE,
            "top_teams_scope": None if league else linked,
            "recent_matches": [m.model_dump() for m in recent],
            "matches_per_month": matches_per_month(db, game, league),
            "matches_by_league": matches_by_league(db, game),
            "research": research_highlights(db, game),
            "latest_ingestion": last_log.logged_at if last_log else None}


def analysis(db: Session, game: Game, key: str) -> tuple[dict | None, object]:
    row = db.scalar(select(AnalysisOutput).where(AnalysisOutput.game_id == game.id, AnalysisOutput.key == key))
    return (row.payload, row.generated_at) if row else (None, None)


TRAJECTORY_LEAGUES = ("LCK", "LPL")


@ttl_cache(300)
def team_performance(db: Session, game: Game, league: str | None, min_matches: int, scope: str = "linked") -> dict:
    teams, total = list_teams(db, game, 1, 200, None, league, min_matches, "elo")
    elos = [t.current_elo for t in teams if t.current_elo is not None]
    hist = []
    if elos:
        lo, hi = int(min(elos) // 25 * 25), int(max(elos) // 25 * 25 + 25)
        for b in range(lo, hi, 25):
            hist.append({"bin": f"{b}-{b + 25}", "lower": b, "teams": sum(1 for e in elos if b <= e < b + 25)})
    # Default teams for the Elo-trajectory chart. Without a league filter: the five highest-rated teams
    # of LCK and LPL that played in the last 180 days of data, because ratings are best identified for
    # leagues that meet each other often (see ELO_SCALE_NOTE). With a league filter: that league's top five.
    last = max((t.last_match_date for t in teams if t.last_match_date), default=None)
    recent = [t for t in teams if last and t.last_match_date and (last - t.last_match_date).days <= 180]
    linked = international_leagues_linked(db, game)
    # Ranking: without a league filter and with the default scope, only teams active in the last 180 days
    # from leagues linked through international play (the same rule as the Overview ranking).
    if not league and scope != "all" and linked:
        ranked = [t for t in recent if t.primary_league in linked]
        scope_note = ("Ranking shows teams active in the last 180 days of data from leagues linked through "
                      f"international play ({', '.join(linked)}). Choose 'All teams' to include every league "
                      "and inactive teams.")
    else:
        ranked = teams
        scope_note = None
    if league:
        pick, note = (recent or teams)[:5], f"Five highest-rated {league} teams active in the last 180 days of data."
    else:
        major = [t for t in recent if t.primary_league in TRAJECTORY_LEAGUES]
        pick = (major or recent or teams)[:5]
        note = ("Default: five highest-rated LCK and LPL teams active in the last 180 days of data "
                "(the leagues whose ratings are best linked through international games).")
    return {"teams": [t.model_dump() for t in ranked], "n_teams": total, "n_ranked": len(ranked),
            "ranking_scope_note": scope_note, "linked_leagues": linked, "elo_histogram": hist,
            "default_trajectory_teams": [t.slug for t in pick], "default_trajectory_note": note,
            "definition": f"Teams with at least {min_matches} games. Win rate = wins / games over all recorded "
                          "games. Elo = rating after the team's last recorded game (inactive teams keep their "
                          "last rating). " + ELO_SCALE_NOTE + " Filter by league to compare like with like."}


@ttl_cache(300)
def player_performance(db: Session, game: Game, metric: str, position: str | None, min_matches: int,
                       year: int | None) -> dict:
    if metric not in PLAYER_METRICS:
        metric = "dpm"
    from sqlalchemy import and_
    from sqlalchemy.orm import aliased
    S, L = PlayerMatchStatistic, LolPlayerMatchStats
    TS = aliased(TeamMatchStatistic)
    if metric in ("kills", "deaths", "assists"):
        col = getattr(S, metric)
    elif metric == "kda":
        col = L.kda
    elif metric == "kill_participation":
        col = case((TS.kills > 0, (S.kills + S.assists) * 1.0 / TS.kills), else_=None)
    else:
        col = getattr(L, metric)
    q = (select(Player.slug, Player.name, Player.primary_position, func.count(col).label("n"),
                func.avg(col).label("v"))
         .join(S, S.player_id == Player.id).outerjoin(L, L.player_match_statistic_id == S.id)
         .join(TS, and_(TS.match_id == S.match_id, TS.team_id == S.team_id))
         .join(Match, Match.id == S.match_id).where(Player.game_id == game.id))
    if position:
        q = q.where(S.position == position)
    if year:
        q = q.where(func.extract("year", Match.match_date) == year)
    rows = db.execute(q.group_by(Player.slug, Player.name, Player.primary_position)
                      .having(func.count(col) >= min_matches)).all()
    vals = sorted(float(r.v) for r in rows if r.v is not None)
    hist = []
    if vals:
        lo, hi = vals[0], vals[-1]
        nb = 20
        w = (hi - lo) / nb or 1
        for i in range(nb):
            a = lo + i * w
            hist.append({"lower": a, "upper": a + w,
                         "players": sum(1 for v in vals if a <= v < a + w or (i == nb - 1 and v == hi))})
    q = lambda p: vals[int(p * (len(vals) - 1))] if vals else None  # noqa: E731
    top = sorted(rows, key=lambda r: -(r.v or -1e9))[:25]
    # Season trend for the metric, per role (median of per-player season averages)
    yr = func.extract("year", Match.match_date)
    tq = (select(yr.label("y"), S.position, Player.id, func.count(col).label("n"), func.avg(col).label("v"))
          .join(S, S.player_id == Player.id).outerjoin(L, L.player_match_statistic_id == S.id)
          .join(TS, and_(TS.match_id == S.match_id, TS.team_id == S.team_id))
          .join(Match, Match.id == S.match_id).where(Player.game_id == game.id)
          .group_by(yr, S.position, Player.id).having(func.count(col) >= 10))
    trows = db.execute(tq).all()
    by_year: dict = {}
    for y, pos, _pid, _n, v in trows:
        if v is not None:
            by_year.setdefault(int(y), {}).setdefault(pos, []).append(float(v))
    import statistics
    season_role = [{"year": y, **{pos: statistics.median(vs) for pos, vs in d.items() if len(vs) >= 10}}
                   for y, d in sorted(by_year.items())]
    return {"metric": metric, "definition": PLAYER_METRICS[metric], "position": position, "year": year,
            "min_games": min_matches, "n_players": len(vals),
            "summary": {"p10": q(0.1), "p25": q(0.25), "median": q(0.5), "p75": q(0.75), "p90": q(0.9)},
            "histogram": hist, "season_role_medians": season_role,
            "season_role_definition": "Median across players (10+ games in the year in that role) of each "
                                      "player's season average. Compare lines within a role, not across roles.",
            "top": [{"slug": r.slug, "name": r.name, "position": r.primary_position, "games": int(r.n),
                     "value": float(r.v)} for r in top],
            "notes": ["Players are compared within the selected position; comparing across positions mixes "
                      "different roles."] if not position else []}


def historical(db: Session, game: Game) -> dict:
    side, _ = analysis(db, game, "side_advantage")
    dur, _ = analysis(db, game, "duration_trend")
    year = func.extract("year", Match.match_date)
    per_year = db.execute(select(year, func.count(Match.id), func.count(func.distinct(Match.tournament_id)))
                          .where(Match.game_id == game.id).group_by(year).order_by(year)).all()
    return {"side_advantage": side, "duration_trend": dur,
            "per_year": [{"year": int(y), "matches": int(n), "tournaments": int(t)} for y, n, t in per_year],
            "matches_per_month": matches_per_month(db, game)}


def data_status(db: Session) -> list[dict]:
    out = []
    for g in db.scalars(select(Game).order_by(Game.id)):
        dvs = db.scalars(select(DatasetVersion).where(DatasetVersion.game_id == g.id)).all()
        last = db.scalar(select(DataIngestionLog).where(DataIngestionLog.game_id == g.id)
                         .order_by(desc(DataIngestionLog.logged_at)).limit(1))
        n = db.scalar(select(func.count()).where(Match.game_id == g.id)) or 0
        cov = db.execute(select(func.min(Match.match_date), func.max(Match.match_date))
                         .where(Match.game_id == g.id)).one()
        out.append({"game": g.slug, "name": g.name, "status": g.status if n or g.status != "historical" else "unavailable",
                    "status_note": g.status_note if n or g.status != "historical"
                    else "No historical files imported yet.",
                    "n_matches": n, "coverage_start": cov[0], "coverage_end": cov[1],
                    "dataset_files": [{"filename": d.filename, "processed_at": d.processed_at,
                                       "validation_status": d.validation_status} for d in dvs],
                    "last_ingestion": {"stage": last.stage, "status": last.status, "message": last.message,
                                       "at": last.logged_at} if last else None,
                    "freshness_note": "Historical archive. Not updated in real time; freshness depends on when the "
                                      "source files were last imported." if n else None})
    return out
