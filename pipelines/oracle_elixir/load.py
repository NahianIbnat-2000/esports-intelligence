"""Step 6: load processed tables into the database.

Loading is a full, transactional rebuild of the League of Legends scope:
existing LoL rows (and LoL model outputs that depend on them) are removed and
the processed tables are inserted again. Running the job twice with the same
source files therefore gives the same database (idempotent), and a failure
leaves the previous state untouched (rollback).
"""
from __future__ import annotations

import math
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from backend.app.models import (AnalysisOutput, DatasetVersion, DataSource, EloRating, Game, LolPlayerMatchStats,
                                LolTeamMatchStats, Match, ModelPrediction, ModelVersion, Player,
                                PlayerMatchStatistic, Team, TeamMatchStatistic, TeamRoster, Tournament)
from pipelines.oracle_elixir.config import PLAYER_LOL_METRICS, SOURCE_KEY, TEAM_LOL_METRICS


def records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of dicts of plain Python values; NaN/NaT -> None."""
    cols = {}
    for c in df.columns:
        col = df[c]
        if pd.api.types.is_datetime64_dtype(col) and getattr(col.dt, "tz", None) is None:
            col = col.dt.tz_localize("UTC")  # naive timestamps in this project are UTC
        vals = col.tolist()
        cols[c] = [None if (v is None or v is pd.NaT or (isinstance(v, float) and math.isnan(v))
                            or v is pd.NA) else v for v in vals]
    n = len(df)
    return [{c: cols[c][i] for c in cols} for i in range(n)]


def _int_or_none(v):
    return None if v is None else int(v)


def clear_lol_scope(db: Session, game_id: int) -> None:
    mv_ids = select(ModelVersion.id).where(ModelVersion.game_id == game_id)
    db.execute(delete(ModelPrediction).where(ModelPrediction.model_version_id.in_(mv_ids)))
    db.execute(delete(EloRating).where(EloRating.model_version_id.in_(mv_ids)))
    db.execute(delete(ModelVersion).where(ModelVersion.game_id == game_id))
    db.execute(delete(AnalysisOutput).where(AnalysisOutput.game_id == game_id))
    match_ids = select(Match.id).where(Match.game_id == game_id)
    tms_ids = select(TeamMatchStatistic.id).where(TeamMatchStatistic.match_id.in_(match_ids))
    pms_ids = select(PlayerMatchStatistic.id).where(PlayerMatchStatistic.match_id.in_(match_ids))
    db.execute(delete(LolTeamMatchStats).where(LolTeamMatchStats.team_match_statistic_id.in_(tms_ids)))
    db.execute(delete(LolPlayerMatchStats).where(LolPlayerMatchStats.player_match_statistic_id.in_(pms_ids)))
    db.execute(delete(TeamMatchStatistic).where(TeamMatchStatistic.match_id.in_(match_ids)))
    db.execute(delete(PlayerMatchStatistic).where(PlayerMatchStatistic.match_id.in_(match_ids)))
    t_ids = select(Tournament.id).where(Tournament.game_id == game_id)
    db.execute(delete(TeamRoster).where(TeamRoster.tournament_id.in_(t_ids)))
    db.execute(delete(Match).where(Match.game_id == game_id))
    db.execute(update(Tournament).where(Tournament.game_id == game_id).values(derived_champion_team_id=None))
    db.execute(delete(Tournament).where(Tournament.game_id == game_id))
    db.execute(delete(Player).where(Player.game_id == game_id))
    db.execute(delete(Team).where(Team.game_id == game_id))
    db.execute(delete(DatasetVersion).where(DatasetVersion.game_id == game_id))


def load(db: Session, tables: dict[str, pd.DataFrame], files: list[dict], counts: dict,
         cleaning_procedure: dict) -> dict:
    game = db.scalar(select(Game).where(Game.slug == "lol"))
    source = db.scalar(select(DataSource).where(DataSource.key == SOURCE_KEY))
    if game is None or source is None:
        raise RuntimeError("Reference data missing; run seed_reference_data first.")
    clear_lol_scope(db, game.id)
    now = datetime.now(UTC)
    m = tables["matches"]

    # Dataset versions (one per raw file)
    file_ids = {}
    for f in files:
        sub = m[m["source_file"] == f["filename"]]
        dv = DatasetVersion(
            source_id=source.id, game_id=game.id, filename=f["filename"], sha256=f["sha256"],
            file_size_bytes=f.get("size_bytes"), original_location=f.get("original_location"),
            collected_at=datetime.fromisoformat(f["collected_at"]), processed_at=now,
            coverage_start=sub["match_date"].min() if len(sub) else None,
            coverage_end=sub["match_date"].max() if len(sub) else None,
            rows_raw=counts.get("per_file_rows", {}).get(f["filename"]),
            rows_accepted=counts.get("per_file_accepted", {}).get(f["filename"]),
            rows_excluded=counts.get("per_file_excluded", {}).get(f["filename"]),
            validation_status=counts.get("validation_status", "passed"),
            cleaning_procedure=cleaning_procedure)
        db.add(dv)
        db.flush()
        file_ids[f["filename"]] = dv.id

    # Teams
    t = tables["teams"].rename(columns={"team_key": "source_team_id"})
    t["game_id"] = game.id
    db.execute(insert(Team), records(t[["game_id", "source_team_id", "id_from_name", "name", "slug",
                                        "primary_league", "first_match_date", "last_match_date",
                                        "n_matches", "n_wins"]]))
    team_id = dict(db.execute(select(Team.source_team_id, Team.id).where(Team.game_id == game.id)).all())

    # Players
    p = tables["players"].rename(columns={"player_key": "source_player_id"})
    p["game_id"] = game.id
    db.execute(insert(Player), records(p[["game_id", "source_player_id", "id_from_name", "name", "slug",
                                          "primary_position", "first_match_date", "last_match_date",
                                          "n_matches"]]))
    player_id = dict(db.execute(select(Player.source_player_id, Player.id).where(Player.game_id == game.id)).all())

    # Tournaments
    tr = tables["tournaments"].copy()
    tr["game_id"] = game.id
    tr["source_key"] = tr["tournament_key"]
    tr["derived_champion_team_id"] = tr["derived_champion_team_key"].map(team_id)
    tr["year"] = tr["year"].astype(int)
    db.execute(insert(Tournament), records(tr[["game_id", "source_key", "slug", "name", "league", "year", "split",
                                               "start_date", "end_date", "n_matches", "n_teams", "has_playoffs",
                                               "derived_champion_team_id"]]))
    tour_id = dict(db.execute(select(Tournament.source_key, Tournament.id)
                              .where(Tournament.game_id == game.id)).all())

    # Matches
    mm = m.copy()
    mm["game_id"] = game.id
    mm["source_match_id"] = mm["source_game_id"]
    mm["tournament_id"] = mm["tournament_key"].map(tour_id)
    mm["blue_team_id"] = mm["blue_team_key"].map(team_id)
    mm["red_team_id"] = mm["red_team_key"].map(team_id)
    mm["winner_team_id"] = mm["winner_team_key"].map(team_id)
    mm["dataset_version_id"] = mm["source_file"].map(file_ids)
    recs = records(mm[["game_id", "source_match_id", "tournament_id", "match_date", "game_in_series", "patch",
                       "playoffs", "blue_team_id", "red_team_id", "winner_team_id", "duration_seconds",
                       "data_completeness", "source_url", "dataset_version_id"]])
    for r in recs:
        r["game_in_series"] = _int_or_none(r["game_in_series"])
        r["duration_seconds"] = _int_or_none(r["duration_seconds"])
        r["patch"] = None if r["patch"] is None else str(r["patch"])
    db.execute(insert(Match), recs)
    match_id = dict(db.execute(select(Match.source_match_id, Match.id).where(Match.game_id == game.id)).all())

    # Team match statistics (+ LoL extension)
    tr_rows = tables["team_rows"].copy()
    tr_rows["match_id"] = tr_rows["source_game_id"].map(match_id)
    tr_rows["team_id"] = tr_rows["team_key"].map(team_id)
    tr_rows["opponent_team_id"] = tr_rows["opponent_team_key"].map(team_id)
    base = records(tr_rows[["match_id", "team_id", "opponent_team_id", "side", "result", "kills", "deaths",
                            "assists"]])
    for r in base:
        for k in ("result", "kills", "deaths", "assists"):
            r[k] = _int_or_none(r[k])
    db.execute(insert(TeamMatchStatistic), base)
    tms = pd.DataFrame(db.execute(select(TeamMatchStatistic.id, TeamMatchStatistic.match_id,
                                         TeamMatchStatistic.team_id)
                                  .join(Match, Match.id == TeamMatchStatistic.match_id)
                                  .where(Match.game_id == game.id)).all(),
                       columns=["team_match_statistic_id", "match_id", "team_id"])
    ext = tr_rows.merge(tms, on=["match_id", "team_id"])
    ext_recs = records(ext[["team_match_statistic_id"] + TEAM_LOL_METRICS])
    int_cols = ["dragons", "barons", "towers", "heralds", "inhibitors", "first_blood", "first_dragon",
                "first_baron", "first_tower"]
    for r in ext_recs:
        for k in int_cols:
            r[k] = _int_or_none(r[k])
    db.execute(insert(LolTeamMatchStats), ext_recs)

    # Player match statistics (+ LoL extension)
    pr = tables["player_rows"].copy()
    pr = pr[pr["player_key"].isin(player_id)]
    pr["match_id"] = pr["source_game_id"].map(match_id)
    pr["player_id"] = pr["player_key"].map(player_id)
    pr["team_id"] = pr["team_key"].map(team_id)
    pbase = records(pr[["match_id", "player_id", "team_id", "side", "position", "result", "kills", "deaths",
                        "assists"]])
    for r in pbase:
        for k in ("result", "kills", "deaths", "assists"):
            r[k] = _int_or_none(r[k])
    if pbase:
        db.execute(insert(PlayerMatchStatistic), pbase)
        pms = pd.DataFrame(db.execute(select(PlayerMatchStatistic.id, PlayerMatchStatistic.match_id,
                                             PlayerMatchStatistic.player_id)
                                      .join(Match, Match.id == PlayerMatchStatistic.match_id)
                                      .where(Match.game_id == game.id)).all(),
                           columns=["player_match_statistic_id", "match_id", "player_id"])
        pext = pr.merge(pms, on=["match_id", "player_id"])
        db.execute(insert(LolPlayerMatchStats),
                   records(pext[["player_match_statistic_id", "kda"]
                                + [c for c in PLAYER_LOL_METRICS]]))

    # Rosters
    ro = tables["rosters"].copy()
    ro["team_id"] = ro["team_key"].map(team_id)
    ro["player_id"] = ro["player_key"].map(player_id)
    ro["tournament_id"] = ro["tournament_key"].map(tour_id)
    if len(ro):
        db.execute(insert(TeamRoster), records(ro[["team_id", "player_id", "tournament_id", "position",
                                                   "games_played", "first_match_date", "last_match_date"]]))

    return {"teams": len(team_id), "players": len(player_id), "tournaments": len(tour_id),
            "matches": len(match_id), "team_match_rows": len(base), "player_match_rows": len(pbase),
            "roster_rows": int(len(ro))}
