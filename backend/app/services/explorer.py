"""Data explorer: curated, documented views of the public analytical tables.
Internal tables (ingestion logs, raw file paths, artifacts) are not exposed."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, aliased

from backend.app.models import (Game, LolPlayerMatchStats, LolTeamMatchStats, Match, Player, PlayerMatchStatistic,
                                Team, TeamMatchStatistic, Tournament)

B, R, W, T2, O = aliased(Team), aliased(Team), aliased(Team), aliased(Team), aliased(Team)


def _matches(gid):
    return (select(Match.source_match_id.label("game_id"), Match.match_date.label("date"),
                   Tournament.year.label("season"), Tournament.league.label("league"),
                   Tournament.name.label("tournament"), Match.playoffs.label("playoffs"), Match.game_in_series.label("game_in_series"),
                   Match.patch.label("patch"), B.name.label("blue_team"), R.name.label("red_team"),
                   W.name.label("winner"), Match.duration_seconds.label("duration_seconds"),
                   Match.data_completeness.label("data_completeness"))
            .join(Tournament, Tournament.id == Match.tournament_id).join(B, B.id == Match.blue_team_id)
            .join(R, R.id == Match.red_team_id).join(W, W.id == Match.winner_team_id).where(Match.game_id == gid))


def _team_games(gid):
    S, L = TeamMatchStatistic, LolTeamMatchStats
    return (select(Match.source_match_id.label("game_id"), Match.match_date.label("date"),
                   Tournament.year.label("season"), Tournament.league.label("league"), Tournament.name.label("tournament"), T2.name.label("team"),
                   O.name.label("opponent"), S.side.label("side"), S.result.label("result"), S.kills.label("kills"),
                   S.deaths.label("deaths"), L.dragons.label("dragons"), L.barons.label("barons"),
                   L.towers.label("towers"), L.golddiff_at_15.label("golddiff_at_15"), L.dpm.label("dpm"),
                   L.earned_gpm.label("earned_gpm"), L.vspm.label("vspm"))
            .select_from(S).join(Match, Match.id == S.match_id).join(Tournament, Tournament.id == Match.tournament_id)
            .join(T2, T2.id == S.team_id).join(O, O.id == S.opponent_team_id)
            .outerjoin(L, L.team_match_statistic_id == S.id).where(Match.game_id == gid))


def _player_games(gid):
    S, L = PlayerMatchStatistic, LolPlayerMatchStats
    return (select(Match.source_match_id.label("game_id"), Match.match_date.label("date"),
                   Tournament.year.label("season"), Tournament.league.label("league"), Tournament.name.label("tournament"), Player.name.label("player"),
                   T2.name.label("team"), S.position.label("position"), S.side.label("side"), S.result.label("result"),
                   L.champion.label("champion"), S.kills.label("kills"), S.deaths.label("deaths"),
                   S.assists.label("assists"), L.kda.label("kda"), L.dpm.label("dpm"),
                   L.damage_share.label("damage_share"), L.cspm.label("cspm"), L.earned_gpm.label("earned_gpm"),
                   L.vspm.label("vspm"), L.golddiff_at_15.label("golddiff_at_15"))
            .select_from(S).join(Match, Match.id == S.match_id).join(Tournament, Tournament.id == Match.tournament_id)
            .join(Player, Player.id == S.player_id).join(T2, T2.id == S.team_id)
            .outerjoin(L, L.player_match_statistic_id == S.id).where(Match.game_id == gid))


def _teams(gid):
    return select(Team.name.label("team"), Team.primary_league.label("primary_league"),
                  Team.n_matches.label("games"), Team.n_wins.label("wins"), Team.current_elo.label("current_elo"),
                  Team.first_match_date.label("first_game"), Team.last_match_date.label("last_game"),
                  Team.id_from_name.label("id_from_name")).where(Team.game_id == gid)


def _tournaments(gid):
    return (select(Tournament.name.label("tournament"), Tournament.league.label("league"),
                   Tournament.year.label("year"), Tournament.split.label("split"),
                   Tournament.start_date.label("start_date"), Tournament.end_date.label("end_date"),
                   Tournament.n_matches.label("games"), Tournament.n_teams.label("teams"),
                   Tournament.has_playoffs.label("has_playoffs"), W.name.label("derived_champion"))
            .outerjoin(W, W.id == Tournament.derived_champion_team_id).where(Tournament.game_id == gid))


DICTIONARY = {
    "game_id": "Source game identifier (Oracle's Elixir gameid). One row of 'matches' = one game.",
    "date": "Game timestamp (UTC) from the source.",
    "league": "League code as recorded in the source (a competitive region or event, not a country).",
    "tournament": "League + year + split from the source.",
    "playoffs": "Source playoffs flag.", "game_in_series": "Game number within the series (source field 'game').",
    "patch": "Game patch.", "blue_team": "Team on the blue side.", "red_team": "Team on the red side.",
    "winner": "Winning team.", "duration_seconds": "Game length in seconds.",
    "data_completeness": "Source flag: 'complete' or 'partial' (partial games lack some detailed stats).",
    "team": "Team name (latest name for the source team id).", "opponent": "Opponent team.",
    "side": "Blue or Red.", "result": "1 = win, 0 = loss.", "kills": "Kills.", "deaths": "Deaths.",
    "assists": "Assists.", "dragons": "Dragons taken.", "barons": "Barons taken.", "towers": "Towers destroyed.",
    "golddiff_at_15": "Gold difference at 15:00 (team: vs opponent team; player: vs lane opponent).",
    "dpm": "Damage to champions per minute.", "earned_gpm": "Earned gold per minute.", "vspm": "Vision score per minute.",
    "player": "Player name (latest name for the source player id).", "position": "top, jng, mid, bot, sup.",
    "champion": "Champion played.", "kda": "(kills + assists) / deaths; kills + assists when deaths = 0.",
    "damage_share": "Share of team damage to champions.", "cspm": "Creep score per minute.",
    "primary_league": "Most frequent domestic league.", "games": "Number of games recorded.", "wins": "Games won.",
    "current_elo": "Elo after the last recorded game.", "first_game": "First recorded game.",
    "last_game": "Last recorded game.", "id_from_name": "True if the source had no team id and the name was used.",
    "year": "Season year.", "season": "Season year as labelled in the source (can differ from the calendar year).", "split": "Split name.", "start_date": "First game.", "end_date": "Last game.",
    "teams": "Number of teams.", "has_playoffs": "Whether playoff games are present.",
    "derived_champion": "Winner of the last playoff game in the data (derived, not official).",
}

DATASETS = {
    "matches": {"label": "Matches (one row per game)", "builder": _matches, "search": ["blue_team", "red_team", "tournament"]},
    "team_games": {"label": "Team game statistics", "builder": _team_games, "search": ["team", "opponent", "tournament"]},
    "player_games": {"label": "Player game statistics", "builder": _player_games, "search": ["player", "team", "tournament"]},
    "teams": {"label": "Teams", "builder": _teams, "search": ["team"]},
    "tournaments": {"label": "Tournaments", "builder": _tournaments, "search": ["tournament", "league"]},
}


def describe() -> list[dict]:
    out = []
    for key, d in DATASETS.items():
        cols = [c.name for c in d["builder"](0).selected_columns]
        out.append({"key": key, "label": d["label"],
                    "columns": [{"name": c, "description": DICTIONARY.get(c, "")} for c in cols]})
    return out


def query(db: Session, game: Game, dataset: str, page: int, page_size: int, columns: list[str] | None,
          q: str | None, league: str | None, date_from: datetime | None, date_to: datetime | None,
          sort: str | None, order: str, season: int | None = None, tournament: str | None = None,
          team: str | None = None, player: str | None = None,
          position: str | None = None) -> tuple[list[str], list[dict], int]:
    if dataset not in DATASETS:
        raise HTTPException(404, f"Unknown dataset '{dataset}'. Options: {', '.join(DATASETS)}")
    sub = DATASETS[dataset]["builder"](game.id).subquery()
    all_cols = [c.name for c in sub.columns]
    cols = [c for c in (columns or all_cols) if c in all_cols] or all_cols
    stmt = select(*[sub.c[c] for c in cols])
    conds = []
    if q:
        conds.append(or_(*[sub.c[c].ilike(f"%{q}%") for c in DATASETS[dataset]["search"]]))
    if league and "league" in all_cols:
        conds.append(sub.c["league"] == league)
    if season is not None:
        for c in ("season", "year"):
            if c in all_cols:
                conds.append(sub.c[c] == season)
                break
    if tournament and "tournament" in all_cols:
        conds.append(sub.c["tournament"] == tournament)
    if team:
        team_cols = [c for c in ("team", "blue_team", "red_team") if c in all_cols]
        if team_cols:
            conds.append(or_(*[sub.c[c] == team for c in team_cols]))
    if player and "player" in all_cols:
        conds.append(sub.c["player"] == player)
    if position and "position" in all_cols:
        conds.append(sub.c["position"] == position)
    date_col = "date" if "date" in all_cols else ("start_date" if "start_date" in all_cols else None)
    if date_col and date_from:
        conds.append(sub.c[date_col] >= date_from)
    if date_col and date_to:
        conds.append(sub.c[date_col] <= date_to)
    for c in conds:
        stmt = stmt.where(c)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    if sort and sort in all_cols:
        stmt = stmt.order_by((desc if order == "desc" else asc)(sub.c[sort]).nulls_last())
    elif date_col:
        stmt = stmt.order_by(desc(sub.c[date_col]))
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return cols, [dict(zip(cols, r)) for r in rows], total


def to_csv(cols: list[str], rows: list[dict], attribution: str) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    return buf.getvalue()
