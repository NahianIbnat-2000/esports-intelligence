"""Ticker strip: a few headline indicators computed from the stored data.

Every value is a query on loaded games, Elo ratings or stored model metrics. Year-on-year
changes compare the latest calendar year in the data with the year before; the game count
compares the same date range in both years, because the latest year is not complete.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, case, desc, extract, func, select
from sqlalchemy.orm import Session

from backend.app.models import EloRating, Game, Match, ModelVersion, TeamMatchStatistic
from backend.app.services import overview as overview_svc
from backend.app.services.common import ttl_cache
from backend.app.services import series as series_svc


def _year_stats(db: Session, game: Game, year: int, until: datetime | None = None) -> dict:
    cond = [Match.game_id == game.id, extract("year", Match.match_date) == year]
    if until is not None:
        cond.append(Match.match_date <= until)
    n, blue_wins, dur = db.execute(
        select(func.count(Match.id),
               func.sum(case((Match.winner_team_id == Match.blue_team_id, 1), else_=0)),
               func.avg(Match.duration_seconds)).where(*cond)).one()
    kills = db.scalar(select(func.sum(TeamMatchStatistic.kills) / func.count(func.distinct(Match.id)))
                      .join(Match, Match.id == TeamMatchStatistic.match_id).where(*cond))
    return {"n": n or 0, "blue": (blue_wins or 0) / n if n else None,
            "dur": float(dur) if dur is not None else None, "kills": float(kills) if kills is not None else None}


def _upset_rate(db: Session, game: Game, mv_id: int, year: int) -> float | None:
    """Share of games in which the team with the lower pre-game Elo expectation won."""
    won = db.execute(
        select(func.count(EloRating.id),
               func.sum(case((EloRating.expected_score < 0.5, 1), else_=0)))
        .join(Match, and_(Match.id == EloRating.match_id, Match.winner_team_id == EloRating.team_id))
        .where(EloRating.model_version_id == mv_id, extract("year", EloRating.match_date) == year,
               EloRating.expected_score != 0.5)).one()
    n, upsets = won
    return (upsets or 0) / n if n else None


def _item(key, label, value, display, delta=None, delta_display=None, good=None, note=""):
    return {"key": key, "label": label, "value": value, "display": display, "delta": delta,
            "delta_display": delta_display, "direction": None if delta in (None, 0) else ("up" if delta > 0 else "down"),
            "good_when": good, "definition": note}


@ttl_cache(600)
def ticker(db: Session, game: Game) -> dict:
    last = db.scalar(select(func.max(Match.match_date)).where(Match.game_id == game.id))
    if last is None:
        return {"as_of": None, "items": []}
    y = last.year
    cur = _year_stats(db, game, y)
    prev = _year_stats(db, game, y - 1)
    same_date_prev = last.replace(year=y - 1)
    prev_ytd = _year_stats(db, game, y - 1, until=same_date_prev)
    items = []

    if prev_ytd["n"]:
        d = cur["n"] / prev_ytd["n"] - 1
        items.append(_item("games_ytd", f"GAMES {y} YTD", cur["n"], f"{cur['n']:,}", d, f"{d:+.1%}", None,
                           f"Games recorded from 1 January to {last:%d %b} {y}, against the same dates in {y - 1}."))
    if cur["blue"] is not None and prev["blue"] is not None:
        d = cur["blue"] - prev["blue"]
        items.append(_item("blue_win", f"BLUE SIDE WIN {y}", cur["blue"], f"{cur['blue']:.1%}", d,
                           f"{d * 100:+.1f} pp", None, f"Share of {y} games won by the blue side; change against {y - 1}."))
    if cur["dur"] and prev["dur"]:
        d = cur["dur"] - prev["dur"]
        m, s = divmod(round(cur["dur"]), 60)
        items.append(_item("avg_length", f"AVG GAME {y}", cur["dur"], f"{m}:{s:02d}", d, f"{d:+.0f} s", None,
                           f"Mean game length in {y}; change in seconds against {y - 1}."))
    if cur["kills"] and prev["kills"]:
        d = cur["kills"] - prev["kills"]
        items.append(_item("kills", f"KILLS / GAME {y}", cur["kills"], f"{cur['kills']:.1f}", d, f"{d:+.1f}", None,
                           f"Mean total kills per game (both teams) in {y}; change against {y - 1}."))

    elo_mv = db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == "elo",
                                                  ModelVersion.status == "trained").order_by(desc(ModelVersion.id)))
    if elo_mv:
        u, up = _upset_rate(db, game, elo_mv.id, y), _upset_rate(db, game, elo_mv.id, y - 1)
        if u is not None:
            d = u - up if up is not None else None
            items.append(_item("upset_rate", f"UPSET RATE {y}", u, f"{u:.1%}", d,
                               f"{d * 100:+.1f} pp" if d is not None else None, None,
                               f"Share of {y} games won by the team with the lower pre-game Elo win probability."))
        top = (overview_svc.overview(db, game, None).get("top_teams") or [])[:1]
        if top:
            t = top[0]
            elo = getattr(t, "current_elo", None) if not isinstance(t, dict) else t.get("current_elo")
            name = t.name if not isinstance(t, dict) else t["name"]
            if elo is not None:
                items.append(_item("elo_leader", "ELO #1", elo, f"{name} {elo:,.0f}", None, None, None,
                                   "Highest current Elo among active teams from internationally linked leagues."))

    wlds, _ = series_svc.list_series(db, game, 1, 1, league="WLDs")
    if wlds:
        s = wlds[0]
        winner, loser = (s["team_a"], s["team_b"]) if s["wins_a"] >= s["wins_b"] else (s["team_b"], s["team_a"])
        hi, lo = max(s["wins_a"], s["wins_b"]), min(s["wins_a"], s["wins_b"])
        items.append(_item("worlds_final", f"WORLDS {s['end'].year} FINAL", hi, f"{winner} {hi}–{lo} {loser}",
                           None, None, None, "Latest World Championship series in the data (series approximated)."))

    lr = db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id, ModelVersion.model_key == "logreg",
                                              ModelVersion.status == "trained").order_by(desc(ModelVersion.id)))
    base = db.scalar(select(ModelVersion).where(ModelVersion.game_id == game.id,
                                                ModelVersion.model_key == "baseline_prevalence",
                                                ModelVersion.status == "trained").order_by(desc(ModelVersion.id)))
    if lr and (lr.metrics or {}).get("test"):
        t = lr.metrics["test"]
        items.append(_item("model_acc", "MODEL ACCURACY", t.get("accuracy"), f"{t['accuracy']:.1%}", None, None, None,
                           "Logistic regression, share of test-period games with the winner predicted correctly."))
        if base and (base.metrics or {}).get("test"):
            b = base.metrics["test"]
            d = t["brier"] - b["brier"]
            items.append(_item("model_brier", "MODEL BRIER", t["brier"], f"{t['brier']:.4f}", d, f"{d:+.4f} vs base",
                               "down", "Logistic regression Brier score on the test period, against the "
                                       "blue-side-rate baseline (lower is better)."))

    return {"as_of": last, "items": items,
            "note": "Computed from the loaded archive. Year-on-year changes compare full calendar years, "
                    "except game counts, which compare the same dates."}

