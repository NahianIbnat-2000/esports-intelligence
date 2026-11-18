"""Tournaments, teams, players and matches."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session, aliased

from backend.app.models import (EloRating, Game, LolPlayerMatchStats, LolTeamMatchStats, Match, ModelVersion,
                                Player, PlayerMatchStatistic, Team, TeamMatchStatistic, TeamRoster, Tournament)
from backend.app.schemas.common import MatchSummary, PlayerSummary, TeamSummary, TournamentSummary

Blue, Red, Win = aliased(Team), aliased(Team), aliased(Team)


# ---------------------------------------------------------------- matches
def _match_select():
    return (select(Match, Tournament.name, Tournament.slug, Tournament.league, Blue.name, Blue.slug, Red.name,
                   Red.slug, Win.name, Win.slug)
            .join(Tournament, Tournament.id == Match.tournament_id)
            .join(Blue, Blue.id == Match.blue_team_id).join(Red, Red.id == Match.red_team_id)
            .join(Win, Win.id == Match.winner_team_id))


def _match_row(r) -> MatchSummary:
    m = r[0]
    return MatchSummary(id=m.id, source_match_id=m.source_match_id, match_date=m.match_date, tournament=r[1],
                        tournament_slug=r[2], league=r[3], playoffs=m.playoffs, game_in_series=m.game_in_series,
                        blue_team=r[4], blue_team_slug=r[5], red_team=r[6], red_team_slug=r[7], winner=r[8],
                        winner_slug=r[9], duration_seconds=m.duration_seconds, patch=m.patch,
                        data_completeness=m.data_completeness)


def list_matches(db: Session, game: Game, page: int, page_size: int, team: str | None = None,
                 tournament: str | None = None, league: str | None = None, date_from: datetime | None = None,
                 date_to: datetime | None = None) -> tuple[list[MatchSummary], int]:
    q = _match_select().where(Match.game_id == game.id)
    if team:
        t = db.scalar(select(Team.id).where(Team.slug == team, Team.game_id == game.id))
        if t is None:
            raise HTTPException(404, f"team '{team}' not found")
        q = q.where(or_(Match.blue_team_id == t, Match.red_team_id == t))
    if tournament:
        q = q.where(Tournament.slug == tournament)
    if league:
        q = q.where(Tournament.league == league)
    if date_from:
        q = q.where(Match.match_date >= date_from)
    if date_to:
        q = q.where(Match.match_date <= date_to)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(desc(Match.match_date), desc(Match.id))
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return [_match_row(r) for r in rows], total


# ------------------------------------------------------------ tournaments
def _tournament_summary(t: Tournament, champ: Team | None) -> TournamentSummary:
    return TournamentSummary(slug=t.slug, name=t.name, league=t.league, year=t.year, split=t.split,
                             start_date=t.start_date, end_date=t.end_date, n_matches=t.n_matches, n_teams=t.n_teams,
                             has_playoffs=t.has_playoffs, derived_champion=champ.name if champ else None,
                             derived_champion_slug=champ.slug if champ else None)


def list_tournaments(db: Session, game: Game, page: int, page_size: int, q: str | None, league: str | None,
                     year: int | None, sort: str) -> tuple[list[TournamentSummary], int]:
    Champ = aliased(Team)
    stmt = select(Tournament, Champ).outerjoin(Champ, Champ.id == Tournament.derived_champion_team_id) \
        .where(Tournament.game_id == game.id)
    if q:
        stmt = stmt.where(Tournament.name.ilike(f"%{q}%"))
    if league:
        stmt = stmt.where(Tournament.league == league)
    if year:
        stmt = stmt.where(Tournament.year == year)
    order = {"recent": desc(Tournament.start_date), "matches": desc(Tournament.n_matches),
             "name": Tournament.name}.get(sort, desc(Tournament.start_date))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    return [_tournament_summary(t, c) for t, c in rows], total


def tournament_filters(db: Session, game: Game) -> dict:
    leagues = db.execute(select(Tournament.league, func.count()).where(Tournament.game_id == game.id)
                         .group_by(Tournament.league).order_by(desc(func.count()))).all()
    years = db.scalars(select(Tournament.year).where(Tournament.game_id == game.id).distinct()
                       .order_by(desc(Tournament.year))).all()
    return {"leagues": [{"league": l, "n_tournaments": n} for l, n in leagues], "years": years}


def standings(db: Session, tournament_id: int, playoffs: bool | None = None) -> list[dict]:
    q = (select(Team.slug, Team.name, func.count().label("games"), func.sum(TeamMatchStatistic.result).label("wins"))
         .join(TeamMatchStatistic, TeamMatchStatistic.team_id == Team.id)
         .join(Match, Match.id == TeamMatchStatistic.match_id)
         .where(Match.tournament_id == tournament_id))
    if playoffs is not None:
        q = q.where(func.coalesce(Match.playoffs, False) == playoffs)
    rows = db.execute(q.group_by(Team.slug, Team.name)).all()
    out = [{"team_slug": s, "team": n, "games": int(g), "wins": int(w), "losses": int(g - w),
            "win_rate": w / g if g else None} for s, n, g, w in rows]
    return sorted(out, key=lambda r: (-r["wins"], r["losses"], r["team"]))


def tournament_detail(db: Session, game: Game, slug: str) -> dict:
    Champ = aliased(Team)
    row = db.execute(select(Tournament, Champ).outerjoin(Champ, Champ.id == Tournament.derived_champion_team_id)
                     .where(Tournament.slug == slug, Tournament.game_id == game.id)).first()
    if row is None:
        raise HTTPException(404, f"tournament '{slug}' not found")
    t, champ = row
    matches = db.execute(_match_select().where(Match.tournament_id == t.id)
                         .order_by(desc(Match.match_date), desc(Match.id)).limit(500)).all()
    avg_len = db.scalar(select(func.avg(Match.duration_seconds)).where(Match.tournament_id == t.id))
    blue_wins = db.scalar(select(func.count()).where(Match.tournament_id == t.id,
                                                     Match.winner_team_id == Match.blue_team_id))
    return {"tournament": _tournament_summary(t, champ).model_dump(),
            "standings_regular_season": standings(db, t.id, playoffs=False),
            "standings_playoffs": standings(db, t.id, playoffs=True) if t.has_playoffs else [],
            "standings_all": standings(db, t.id),
            "matches": [_match_row(r).model_dump() for r in matches],
            "matches_truncated": t.n_matches > 500,
            "stats": {"avg_duration_minutes": float(avg_len) / 60 if avg_len else None,
                      "blue_win_rate": blue_wins / t.n_matches if t.n_matches else None},
            "champion_note": "Derived champion = winner of the chronologically last playoff game in the data. "
                             "It is not taken from an official title register."}


# ------------------------------------------------------------------ teams
def _team_summary(t: Team) -> TeamSummary:
    return TeamSummary(slug=t.slug, name=t.name, primary_league=t.primary_league, n_matches=t.n_matches,
                       n_wins=t.n_wins, win_rate=t.n_wins / t.n_matches if t.n_matches else None,
                       current_elo=t.current_elo, first_match_date=t.first_match_date,
                       last_match_date=t.last_match_date, id_from_name=t.id_from_name)


def list_teams(db: Session, game: Game, page: int, page_size: int, q: str | None, league: str | None,
               min_matches: int, sort: str, active_since: datetime | None = None,
               leagues: list[str] | None = None) -> tuple[list[TeamSummary], int]:
    stmt = select(Team).where(Team.game_id == game.id, Team.n_matches >= min_matches)
    if leagues:
        stmt = stmt.where(Team.primary_league.in_(leagues))
    if q:
        stmt = stmt.where(Team.name.ilike(f"%{q}%"))
    if league:
        stmt = stmt.where(Team.primary_league == league)
    if active_since:
        stmt = stmt.where(Team.last_match_date >= active_since)
    order = {"elo": desc(func.coalesce(Team.current_elo, -1)), "matches": desc(Team.n_matches),
             "win_rate": desc(Team.n_wins * 1.0 / func.nullif(Team.n_matches, 0)), "name": Team.name,
             "recent": desc(Team.last_match_date)}.get(sort, desc(Team.n_matches))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(order, Team.name).offset((page - 1) * page_size).limit(page_size)).all()
    return [_team_summary(t) for t in rows], total


def _elo_version(db: Session, game: Game) -> ModelVersion | None:
    return db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == "elo"))


def _team(db: Session, game: Game, slug: str) -> Team:
    t = db.scalar(select(Team).where(Team.slug == slug, Team.game_id == game.id))
    if t is None:
        raise HTTPException(404, f"team '{slug}' not found")
    return t


def elo_history(db: Session, game: Game, team_id: int, max_points: int = 400) -> list[dict]:
    mv = _elo_version(db, game)
    if mv is None:
        return []
    rows = db.execute(select(EloRating.match_date, EloRating.rating_after).where(
        EloRating.model_version_id == mv.id, EloRating.team_id == team_id).order_by(EloRating.match_date)).all()
    step = max(1, len(rows) // max_points)
    pts = rows[::step]
    if rows and pts[-1] != rows[-1]:
        pts.append(rows[-1])
    return [{"date": d, "elo": float(r)} for d, r in pts]


def team_detail(db: Session, game: Game, slug: str) -> dict:
    t = _team(db, game, slug)
    recent, _ = list_matches(db, game, 1, 20, team=slug)
    by_tour = db.execute(
        select(Tournament.slug, Tournament.name, Tournament.year, Tournament.start_date, func.count(),
               func.sum(TeamMatchStatistic.result))
        .join(Match, Match.tournament_id == Tournament.id)
        .join(TeamMatchStatistic, TeamMatchStatistic.match_id == Match.id)
        .where(TeamMatchStatistic.team_id == t.id)
        .group_by(Tournament.slug, Tournament.name, Tournament.year, Tournament.start_date)
        .order_by(desc(Tournament.start_date))).all()
    Opp = aliased(Team)
    h2h = db.execute(select(Opp.slug, Opp.name, func.count(), func.sum(TeamMatchStatistic.result))
                     .join(Opp, Opp.id == TeamMatchStatistic.opponent_team_id)
                     .where(TeamMatchStatistic.team_id == t.id).group_by(Opp.slug, Opp.name)
                     .order_by(desc(func.count())).limit(12)).all()
    # Observed roster: players in this team's most recent tournament
    last_tour = db.scalar(select(TeamRoster.tournament_id).join(Tournament, Tournament.id == TeamRoster.tournament_id)
                          .where(TeamRoster.team_id == t.id).order_by(desc(Tournament.start_date)).limit(1))
    roster = []
    if last_tour:
        roster = [{"player_slug": s, "player": n, "position": p, "games_played": g}
                  for s, n, p, g in db.execute(
                      select(Player.slug, Player.name, TeamRoster.position, TeamRoster.games_played)
                      .join(Player, Player.id == TeamRoster.player_id)
                      .where(TeamRoster.team_id == t.id, TeamRoster.tournament_id == last_tour)
                      .order_by(TeamRoster.position, desc(TeamRoster.games_played))).all()]
    # Side split and average LoL team metrics
    side = db.execute(select(TeamMatchStatistic.side, func.count(), func.sum(TeamMatchStatistic.result))
                      .where(TeamMatchStatistic.team_id == t.id).group_by(TeamMatchStatistic.side)).all()
    avgs = db.execute(select(func.avg(LolTeamMatchStats.golddiff_at_15), func.avg(LolTeamMatchStats.dragons),
                             func.avg(LolTeamMatchStats.barons), func.avg(LolTeamMatchStats.towers),
                             func.avg(Match.duration_seconds),
                             func.count(LolTeamMatchStats.golddiff_at_15))
                      .join(TeamMatchStatistic,
                            TeamMatchStatistic.id == LolTeamMatchStats.team_match_statistic_id)
                      .join(Match, Match.id == TeamMatchStatistic.match_id)
                      .where(TeamMatchStatistic.team_id == t.id)).one()
    # Rolling form: last 10 results, oldest first
    last10 = db.scalars(select(TeamMatchStatistic.result).join(Match, Match.id == TeamMatchStatistic.match_id)
                        .where(TeamMatchStatistic.team_id == t.id)
                        .order_by(desc(Match.match_date)).limit(10)).all()[::-1]
    return {
        "team": _team_summary(t).model_dump(),
        "elo_history": elo_history(db, game, t.id),
        "recent_matches": [m.model_dump() for m in recent],
        "recent_form": last10,
        "tournaments": [{"slug": s, "name": n, "year": y, "start_date": d, "games": int(g), "wins": int(w),
                         "win_rate": w / g if g else None} for s, n, y, d, g, w in by_tour],
        "head_to_head": [{"opponent_slug": s, "opponent": n, "games": int(g), "wins": int(w), "losses": int(g - w)}
                         for s, n, g, w in h2h],
        "roster_latest_tournament": roster,
        "side_split": [{"side": s, "games": int(g), "wins": int(w), "win_rate": w / g if g else None}
                       for s, g, w in side],
        "averages": {"golddiff_at_15": avgs[0], "dragons": avgs[1], "barons": avgs[2], "towers": avgs[3],
                     "duration_minutes": float(avgs[4]) / 60 if avgs[4] else None,
                     "n_games_with_15min_data": int(avgs[5] or 0)},
        "notes": ["Roster = players observed in the team's most recent tournament in the data, not an official "
                  "roster register."] + (["This team had no source team id; it is identified by name, so name "
                                          "changes or shared names can split or merge records."]
                                         if t.id_from_name else []),
    }


def head_to_head(db: Session, game: Game, a: str, b: str) -> dict:
    ta, tb = _team(db, game, a), _team(db, game, b)
    rows = db.execute(_match_select().where(
        or_(and_(Match.blue_team_id == ta.id, Match.red_team_id == tb.id),
            and_(Match.blue_team_id == tb.id, Match.red_team_id == ta.id)))
        .order_by(desc(Match.match_date))).all()
    games = [_match_row(r) for r in rows]
    wins_a = sum(1 for g in games if g.winner_slug == ta.slug)
    return {"team_a": _team_summary(ta).model_dump(), "team_b": _team_summary(tb).model_dump(),
            "games": len(games), "wins_a": wins_a, "wins_b": len(games) - wins_a,
            "matches": [g.model_dump() for g in games[:50]],
            "elo_history_a": elo_history(db, game, ta.id, 200), "elo_history_b": elo_history(db, game, tb.id, 200)}


# ---------------------------------------------------------------- players
PLAYER_METRICS = {
    "kills": "Kills per game", "deaths": "Deaths per game", "assists": "Assists per game",
    "kda": "KDA = (total kills + total assists) / max(total deaths, 1) over the games",
    "dpm": "Damage to champions per minute", "damage_share": "Share of team damage to champions",
    "cspm": "Creep score per minute", "earned_gpm": "Earned gold per minute (excludes starting/passive gold)",
    "gold_share": "Share of team earned gold", "vspm": "Vision score per minute",
    "golddiff_at_15": "Gold difference vs lane opponent at 15:00", "csdiff_at_15": "CS difference vs lane opponent at 15:00",
    "kill_participation": "(kills + assists) / team kills in the same game; games where the team had 0 kills are "
                          "left out",
}


def _player_agg_columns():
    S, L = PlayerMatchStatistic, LolPlayerMatchStats
    return [func.count(S.id).label("games"), func.sum(S.result).label("wins"),
            func.avg(S.kills).label("kills"), func.avg(S.deaths).label("deaths"), func.avg(S.assists).label("assists"),
            ((func.sum(S.kills) + func.sum(S.assists)) * 1.0 /
             case((func.sum(S.deaths) > 0, func.sum(S.deaths)), else_=1)).label("kda"),
            func.avg(L.dpm).label("dpm"), func.avg(L.damage_share).label("damage_share"),
            func.avg(L.cspm).label("cspm"), func.avg(L.earned_gpm).label("earned_gpm"),
            func.avg(L.gold_share).label("gold_share"), func.avg(L.vspm).label("vspm"),
            func.avg(L.golddiff_at_15).label("golddiff_at_15"), func.avg(L.csdiff_at_15).label("csdiff_at_15"),
            func.count(L.dpm).label("games_with_detailed_stats")]


def _player(db: Session, game: Game, slug: str) -> Player:
    p = db.scalar(select(Player).where(Player.slug == slug, Player.game_id == game.id))
    if p is None:
        raise HTTPException(404, f"player '{slug}' not found")
    return p


def _latest_team(db: Session, player_id: int) -> tuple[str | None, str | None]:
    r = db.execute(select(Team.name, Team.slug).join(TeamRoster, TeamRoster.team_id == Team.id)
                   .where(TeamRoster.player_id == player_id).order_by(desc(TeamRoster.last_match_date)).limit(1)).first()
    return (r[0], r[1]) if r else (None, None)


def list_players(db: Session, game: Game, page: int, page_size: int, q: str | None, position: str | None,
                 min_matches: int, sort: str) -> tuple[list[PlayerSummary], int]:
    stmt = select(Player).where(Player.game_id == game.id, Player.n_matches >= min_matches)
    if q:
        stmt = stmt.where(Player.name.ilike(f"%{q}%"))
    if position:
        stmt = stmt.where(Player.primary_position == position)
    order = {"matches": desc(Player.n_matches), "name": Player.name, "recent": desc(Player.last_match_date)}.get(
        sort, desc(Player.n_matches))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(order, Player.name).offset((page - 1) * page_size).limit(page_size)).all()
    out = []
    for p in rows:
        tn, ts = _latest_team(db, p.id)
        out.append(PlayerSummary(slug=p.slug, name=p.name, primary_position=p.primary_position, n_matches=p.n_matches,
                                 first_match_date=p.first_match_date, last_match_date=p.last_match_date,
                                 latest_team=tn, latest_team_slug=ts))
    return out, total


def _row_to_dict(r) -> dict:
    d = dict(r._mapping)
    return {k: (float(v) if v is not None and not isinstance(v, (str, int)) else v) for k, v in d.items()}


def player_detail(db: Session, game: Game, slug: str) -> dict:
    p = _player(db, game, slug)
    S, L = PlayerMatchStatistic, LolPlayerMatchStats
    base = select(*_player_agg_columns()).select_from(S).outerjoin(L, L.player_match_statistic_id == S.id) \
        .join(Match, Match.id == S.match_id).where(S.player_id == p.id)
    career = _row_to_dict(db.execute(base).one())
    year_col = func.extract("year", Match.match_date)
    by_year = [_row_to_dict(r) for r in db.execute(base.add_columns(year_col.label("year")).group_by(year_col)
                                                   .order_by(year_col)).all()]
    teams = db.execute(select(Team.slug, Team.name, Tournament.name, Tournament.slug, TeamRoster.position,
                              TeamRoster.games_played, TeamRoster.first_match_date, TeamRoster.last_match_date)
                       .join(Team, Team.id == TeamRoster.team_id).join(Tournament, Tournament.id == TeamRoster.tournament_id)
                       .where(TeamRoster.player_id == p.id).order_by(desc(TeamRoster.last_match_date))).all()
    recent = db.execute(select(Match.match_date, Match.source_match_id, Tournament.name, Team.name, S.result, S.kills,
                               S.deaths, S.assists, L.champion, L.dpm, L.cspm, S.position)
                        .join(Match, Match.id == S.match_id).join(Tournament, Tournament.id == Match.tournament_id)
                        .join(Team, Team.id == S.team_id).outerjoin(L, L.player_match_statistic_id == S.id)
                        .where(S.player_id == p.id).order_by(desc(Match.match_date)).limit(20)).all()
    T = aliased(TeamMatchStatistic)
    kp = db.scalar(select(func.avg((S.kills + S.assists) * 1.0 / T.kills))
                   .select_from(S).join(T, and_(T.match_id == S.match_id, T.team_id == S.team_id))
                   .where(S.player_id == p.id, T.kills > 0))
    career["kill_participation"] = float(kp) if kp is not None else None
    tn, ts = _latest_team(db, p.id)
    return {
        "player": PlayerSummary(slug=p.slug, name=p.name, primary_position=p.primary_position, n_matches=p.n_matches,
                                first_match_date=p.first_match_date, last_match_date=p.last_match_date,
                                latest_team=tn, latest_team_slug=ts).model_dump(),
        "career": career, "by_year": by_year,
        "team_history": [{"team_slug": a, "team": b, "tournament": c, "tournament_slug": d, "position": e,
                          "games_played": f, "first": g, "last": h} for a, b, c, d, e, f, g, h in teams],
        "recent_games": [{"date": a, "source_match_id": b, "tournament": c, "team": d, "result": e, "kills": f,
                          "deaths": g, "assists": h, "champion": i, "dpm": j, "cspm": k, "position": l}
                         for a, b, c, d, e, f, g, h, i, j, k, l in recent],
        "metric_definitions": PLAYER_METRICS,
        "notes": ["Averages use only games where the metric is recorded; games with partial data are not "
                  "counted as zero. 'games_with_detailed_stats' shows how many games have damage/gold detail."],
    }


def compare_players(db: Session, game: Game, a: str, b: str) -> dict:
    pa, pb = _player(db, game, a), _player(db, game, b)
    S, L = PlayerMatchStatistic, LolPlayerMatchStats

    def agg(p):
        return _row_to_dict(db.execute(select(*_player_agg_columns()).select_from(S)
                                       .outerjoin(L, L.player_match_statistic_id == S.id)
                                       .where(S.player_id == p.id)).one())
    notes = ["All metrics are per-game averages over each player's full recorded career in the data."]
    if pa.primary_position != pb.primary_position:
        notes.append(f"The players have different primary positions ({pa.primary_position} vs "
                     f"{pb.primary_position}). Role shapes these metrics (for example supports have low CS and "
                     "damage share by design), so differences mostly reflect role, not skill.")
    return {"player_a": {"slug": pa.slug, "name": pa.name, "position": pa.primary_position, **agg(pa)},
            "player_b": {"slug": pb.slug, "name": pb.name, "position": pb.primary_position, **agg(pb)},
            "metric_definitions": PLAYER_METRICS, "notes": notes}
