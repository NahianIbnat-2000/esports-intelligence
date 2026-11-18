"""Series list: games grouped into approximate series.

The source has no series id, so a series is approximated as consecutive games between the same two
teams in the same tournament, each less than SERIES_GAP after the previous one (same rule as the
match centre). The series score counts game wins; "best of" is not known and is not shown.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import Game, Match, Team, Tournament

SERIES_GAP = timedelta(hours=3)
LONG_GAP = timedelta(hours=12)


def continues(last_date, last_no, date, no) -> bool:
    """True if a game continues the open series of the same pairing in the same tournament.

    Under 3 hours apart, unless the source numbers this game 1 (a new series); or up to 12 hours apart
    when the source's game number is exactly one higher (long pauses inside a best-of-5).
    """
    gap = date - last_date
    if no == 1 and last_no is not None:
        return False
    if gap <= SERIES_GAP:
        return True
    return gap <= LONG_GAP and no is not None and last_no is not None and no == last_no + 1
NOTE = ("Series are approximated: games between the same two teams in the same tournament, less than "
        "3 hours apart (or up to 12 hours when the source's game number continues). The score counts game wins; the series format (best of 1, 3 or 5) is not in the source.")

_cache: dict[tuple, list[dict]] = {}


def _build(db: Session, game: Game) -> list[dict]:
    key = (game.id,) + tuple(db.execute(select(func.count(Match.id), func.max(Match.id))
                                        .where(Match.game_id == game.id)).one())
    if key in _cache:
        return _cache[key]
    rows = db.execute(select(Match.id, Match.tournament_id, Match.blue_team_id, Match.red_team_id,
                             Match.winner_team_id, Match.match_date, Match.playoffs, Match.game_in_series)
                      .where(Match.game_id == game.id).order_by(Match.match_date, Match.id)).all()
    tours = {t.id: t for t in db.scalars(select(Tournament).where(Tournament.game_id == game.id))}
    teams = {t.id: t for t in db.scalars(select(Team).where(Team.game_id == game.id))}

    open_series: dict[tuple, dict] = {}   # (tournament, team pair) -> series still open
    out: list[dict] = []
    for mid, tid, blue, red, win, date, po, no in rows:
        pair = (tid, min(blue, red), max(blue, red))
        s = open_series.get(pair)
        if s is None or not continues(s["_last"], s["_no"], date, no):
            t = tours[tid]
            s = {"_last": date, "_no": None, "_a": blue, "_b": red, "games": [], "wins": {blue: 0, red: 0},
                 "tournament": t.name, "tournament_slug": t.slug, "league": t.league, "playoffs": bool(po),
                 "start": date}
            open_series[pair] = s
            out.append(s)
        s["games"].append({"id": mid, "winner_slug": teams[win].slug if win in teams else None})
        s["wins"][win] = s["wins"].get(win, 0) + 1
        s["_last"] = date
        s["_no"] = no
        s["playoffs"] = s["playoffs"] or bool(po)

    result = []
    for s in out:
        a, b = teams[s["_a"]], teams[s["_b"]]
        wa, wb = s["wins"].get(a.id, 0), s["wins"].get(b.id, 0)
        result.append({
            "id": s["games"][0]["id"], "start": s["start"], "end": s["_last"],
            "tournament": s["tournament"], "tournament_slug": s["tournament_slug"], "league": s["league"],
            "playoffs": s["playoffs"],
            "team_a": a.name, "team_a_slug": a.slug, "team_b": b.name, "team_b_slug": b.slug,
            "wins_a": wa, "wins_b": wb, "n_games": len(s["games"]),
            "winner_slug": a.slug if wa > wb else b.slug if wb > wa else None,
            "games": s["games"],
        })
    result.sort(key=lambda r: (r["end"], r["id"]), reverse=True)
    _cache.clear()
    _cache[key] = result
    return result


def list_series(db: Session, game: Game, page: int, page_size: int, league: str | None = None,
                team: str | None = None) -> tuple[list[dict], int]:
    rows = _build(db, game)
    if league:
        rows = [r for r in rows if r["league"] == league]
    if team:
        rows = [r for r in rows if team in (r["team_a_slug"], r["team_b_slug"])]
    total = len(rows)
    start = (page - 1) * page_size
    return rows[start:start + page_size], total
