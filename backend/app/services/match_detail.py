"""Single-game page ("match centre").

Everything comes from stored rows: the two team lines, the ten player lines, the Elo ratings before and
after the game, stored out-of-sample model predictions (only for validation and test games), the
approximate series (same teams, same tournament, same UTC day), each team's last results before the
game, and role medians of the same tournament for comparison.
"""
from __future__ import annotations

from datetime import timedelta
from statistics import median

from fastapi import HTTPException
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from backend.app.models import (EloRating, Game, LolPlayerMatchStats, LolTeamMatchStats, Match, ModelPrediction,
                                ModelVersion, Player, PlayerMatchStatistic, Team, TeamMatchStatistic, Tournament)

TEAM_FIELDS = ["dragons", "barons", "towers", "heralds", "inhibitors", "first_blood", "first_dragon", "first_baron",
               "first_tower", "damage_to_champions", "dpm", "vision_score", "vspm", "total_gold", "earned_gpm",
               "total_cs", "cspm", "golddiff_at_15", "xpdiff_at_15", "csdiff_at_15"]
PLAYER_FIELDS = ["champion", "kda", "damage_to_champions", "dpm", "damage_share", "vision_score", "vspm",
                 "wards_placed", "control_wards_bought", "earned_gpm", "gold_share", "total_cs", "cspm",
                 "golddiff_at_15", "csdiff_at_15"]
ROLE_ORDER = {"top": 0, "jng": 1, "mid": 2, "bot": 3, "sup": 4}
TOP_RULE = ("Top performer = player on the winning team with the highest KDA ((kills + assists) / max(deaths, 1)); "
            "ties broken by damage share. A simple descriptive rule, not an official MVP award.")
FORM_GAMES = 10
SERIES_GAP = timedelta(hours=3)


def _kda(k, d, a):
    if k is None or a is None:
        return None
    return (k + a) / max(d or 0, 1)


def _elo_mv(db: Session, game: Game) -> ModelVersion | None:
    return db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == "elo",
                                                ModelVersion.status == "trained").order_by(desc(ModelVersion.id)))


def match_detail(db: Session, game: Game, match_id: int) -> dict:
    m = db.scalar(select(Match).where(Match.id == match_id, Match.game_id == game.id))
    if m is None:
        raise HTTPException(404, f"match {match_id} not found")
    t = db.get(Tournament, m.tournament_id)
    teams = {x.id: x for x in db.scalars(select(Team).where(Team.id.in_([m.blue_team_id, m.red_team_id])))}

    # ---- team lines
    team_rows = db.execute(select(TeamMatchStatistic, LolTeamMatchStats)
                           .outerjoin(LolTeamMatchStats,
                                      LolTeamMatchStats.team_match_statistic_id == TeamMatchStatistic.id)
                           .where(TeamMatchStatistic.match_id == m.id)).all()
    team_lines = {}
    for ts, lol in team_rows:
        d = {"kills": ts.kills, "deaths": ts.deaths, "assists": ts.assists, "result": ts.result, "side": ts.side}
        for f in TEAM_FIELDS:
            d[f] = getattr(lol, f) if lol is not None else None
        team_lines[ts.team_id] = d

    # ---- player lines
    prow = db.execute(select(PlayerMatchStatistic, LolPlayerMatchStats, Player.name, Player.slug)
                      .join(Player, Player.id == PlayerMatchStatistic.player_id)
                      .outerjoin(LolPlayerMatchStats,
                                 LolPlayerMatchStats.player_match_statistic_id == PlayerMatchStatistic.id)
                      .where(PlayerMatchStatistic.match_id == m.id)).all()
    players: dict[int, list] = {m.blue_team_id: [], m.red_team_id: []}
    for ps, lol, name, slug in prow:
        tk = team_lines.get(ps.team_id, {}).get("kills")
        kp = (ps.kills + ps.assists) / tk if tk and ps.kills is not None and ps.assists is not None else None
        d = {"player": name, "slug": slug, "position": ps.position, "kills": ps.kills, "deaths": ps.deaths,
             "assists": ps.assists, "kill_participation": kp, "result": ps.result}
        for f in PLAYER_FIELDS:
            d[f] = getattr(lol, f) if lol is not None else None
        if d["kda"] is None:
            d["kda"] = _kda(ps.kills, ps.deaths, ps.assists)
        players.setdefault(ps.team_id, []).append(d)
    for lst in players.values():
        lst.sort(key=lambda p: ROLE_ORDER.get((p["position"] or "").lower(), 9))

    # ---- top performer (documented rule) and role medians in this tournament
    winners = players.get(m.winner_team_id, [])
    top = None
    if winners:
        top = max(winners, key=lambda p: ((p["kda"] if p["kda"] is not None else -1),
                                          (p["damage_share"] if p["damage_share"] is not None else -1)))
    top_cmp = None
    if top and top["position"]:
        rows = db.execute(select(PlayerMatchStatistic.kills, PlayerMatchStatistic.deaths, PlayerMatchStatistic.assists,
                                 LolPlayerMatchStats.dpm, LolPlayerMatchStats.damage_share, LolPlayerMatchStats.cspm,
                                 LolPlayerMatchStats.golddiff_at_15, TeamMatchStatistic.kills)
                          .join(Match, Match.id == PlayerMatchStatistic.match_id)
                          .join(TeamMatchStatistic, and_(TeamMatchStatistic.match_id == PlayerMatchStatistic.match_id,
                                                         TeamMatchStatistic.team_id == PlayerMatchStatistic.team_id))
                          .outerjoin(LolPlayerMatchStats,
                                     LolPlayerMatchStats.player_match_statistic_id == PlayerMatchStatistic.id)
                          .where(Match.tournament_id == m.tournament_id,
                                 PlayerMatchStatistic.position == top["position"])).all()

        def med(vals):
            v = [x for x in vals if x is not None]
            return median(v) if v else None
        top_cmp = {
            "n_player_games": len(rows),
            "kda": med([_kda(k, d, a) for k, d, a, *_ in rows]),
            "kill_participation": med([(k + a) / tk if tk and k is not None and a is not None else None
                                       for k, d, a, _, _, _, _, tk in rows]),
            "dpm": med([r[3] for r in rows]), "damage_share": med([r[4] for r in rows]),
            "cspm": med([r[5] for r in rows]), "golddiff_at_15": med([r[6] for r in rows]),
        }

    # ---- Elo before and after
    mv = _elo_mv(db, game)
    elo = {}
    trend: dict[int, list] = {}
    if mv:
        for r in db.scalars(select(EloRating).where(EloRating.model_version_id == mv.id, EloRating.match_id == m.id)):
            elo[r.team_id] = {"before": r.rating_before, "after": r.rating_after,
                              "change": r.rating_after - r.rating_before, "expected_score": r.expected_score,
                              "league_rating": r.league_rating}
        for tid in (m.blue_team_id, m.red_team_id):
            rs = db.execute(select(EloRating.match_date, EloRating.rating_after, EloRating.match_id)
                            .where(EloRating.model_version_id == mv.id, EloRating.team_id == tid,
                                   EloRating.match_date <= m.match_date)
                            .order_by(desc(EloRating.match_date), desc(EloRating.match_id)).limit(21)).all()
            trend[tid] = [{"date": d, "elo": float(e), "match_id": mid} for d, e, mid in reversed(rs)]

    # ---- stored out-of-sample predictions (validation/test games only)
    preds = db.execute(select(ModelVersion.model_key, ModelVersion.display_name, ModelVersion.version,
                              ModelPrediction.prob_blue_win, ModelPrediction.split)
                       .join(ModelVersion, ModelVersion.id == ModelPrediction.model_version_id)
                       .where(ModelPrediction.match_id == m.id, ModelVersion.game_id == game.id)).all()
    predictions = [{"model_key": k, "display_name": n, "version": v, "prob_blue_win": p, "split": s}
                   for k, n, v, p, s in preds]

    # ---- approximate series: same two teams and tournament, games chained while gaps are under 3 hours
    pair = or_(and_(Match.blue_team_id == m.blue_team_id, Match.red_team_id == m.red_team_id),
               and_(Match.blue_team_id == m.red_team_id, Match.red_team_id == m.blue_team_id))
    near = db.scalars(select(Match).where(Match.tournament_id == m.tournament_id, pair,
                                          Match.match_date >= m.match_date - timedelta(hours=18),
                                          Match.match_date <= m.match_date + timedelta(hours=18))
                      .order_by(Match.match_date, Match.id)).all()
    idx = next(i for i, g in enumerate(near) if g.id == m.id)
    lo = hi = idx
    while lo > 0 and near[lo].match_date - near[lo - 1].match_date <= SERIES_GAP:
        lo -= 1
    while hi < len(near) - 1 and near[hi + 1].match_date - near[hi].match_date <= SERIES_GAP:
        hi += 1
    series_games = near[lo:hi + 1]
    series = []
    score = {m.blue_team_id: 0, m.red_team_id: 0}
    for i, g in enumerate(series_games, 1):
        score[g.winner_team_id] = score.get(g.winner_team_id, 0) + 1
        series.append({"id": g.id, "number": g.game_in_series or i, "winner_slug": teams[g.winner_team_id].slug,
                       "winner": teams[g.winner_team_id].name, "duration_seconds": g.duration_seconds,
                       "blue_slug": teams[g.blue_team_id].slug, "current": g.id == m.id})

    # ---- last results before this game
    def form(tid: int):
        rs = db.execute(select(TeamMatchStatistic.result, Match.id, Match.match_date)
                        .join(Match, Match.id == TeamMatchStatistic.match_id)
                        .where(TeamMatchStatistic.team_id == tid,
                               or_(Match.match_date < m.match_date,
                                   and_(Match.match_date == m.match_date, Match.id < m.id)))
                        .order_by(desc(Match.match_date), desc(Match.id)).limit(FORM_GAMES)).all()
        return [{"result": r, "match_id": i, "date": d} for r, i, d in reversed(rs)]

    def side(tid: int) -> dict:
        tm = teams[tid]
        return {"name": tm.name, "slug": tm.slug, "side": "Blue" if tid == m.blue_team_id else "Red",
                "won": tid == m.winner_team_id, "series_wins": score.get(tid, 0), "stats": team_lines.get(tid),
                "players": players.get(tid, []), "elo": elo.get(tid), "elo_trend": trend.get(tid, []),
                "form": form(tid)}

    return {
        "id": m.id, "source_match_id": m.source_match_id, "match_date": m.match_date, "patch": m.patch,
        "playoffs": m.playoffs, "game_in_series": m.game_in_series, "duration_seconds": m.duration_seconds,
        "data_completeness": m.data_completeness,
        "tournament": {"name": t.name, "slug": t.slug, "league": t.league, "year": t.year, "split": t.split},
        "blue": side(m.blue_team_id), "red": side(m.red_team_id),
        "series": series, "series_note": "Series are approximated: games between the same two teams in the same tournament, less than 3 hours apart.",
        "top_performer": top and {**top, "team_slug": teams[m.winner_team_id].slug,
                                  "tournament_role_median": top_cmp},
        "top_performer_rule": TOP_RULE,
        "predictions": predictions,
        "elo_model_version": mv.version if mv else None,
    }
