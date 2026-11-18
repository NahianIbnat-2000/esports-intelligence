"""Game-agnostic relational model.

Terminology used throughout the project:
- "match" = one single game (one map) identified by the provider's game id.
  For League of Legends this is Oracle's Elixir `gameid`. Best-of series are
  NOT reconstructed in Version 1.0.
- "tournament" = one league season split (league + year + split) as recorded
  in the source. The source has no separate tournament-name field.

Game-specific statistics live in their own extension tables (see lol.py), so
VALORANT or CS2 can add their own tables without changing these ones.
"""
from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String,
                        Text, UniqueConstraint, func, text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class Game(Base, TimestampMixin):
    __tablename__ = "games"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    # active | historical | integration_pending | unavailable | demo
    status: Mapped[str] = mapped_column(String(32))
    status_note: Mapped[str | None] = mapped_column(Text)


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(512))
    data_type: Mapped[str] = mapped_column(String(32))  # historical | live | demo
    license_note: Mapped[str | None] = mapped_column(Text)
    attribution: Mapped[str | None] = mapped_column(Text)


class DatasetVersion(Base, TimestampMixin):
    __tablename__ = "dataset_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    filename: Mapped[str] = mapped_column(String(256))
    sha256: Mapped[str] = mapped_column(String(64))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    original_location: Mapped[str | None] = mapped_column(String(512))
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coverage_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_raw: Mapped[int | None] = mapped_column(Integer)
    rows_accepted: Mapped[int | None] = mapped_column(Integer)
    rows_excluded: Mapped[int | None] = mapped_column(Integer)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending")
    cleaning_procedure: Mapped[dict | None] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("source_id", "sha256", name="uq_dataset_file"),)


class DataIngestionLog(Base, TimestampMixin):
    __tablename__ = "data_ingestion_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"))
    stage: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))  # ok | warning | error
    message: Mapped[str] = mapped_column(Text)
    counts: Mapped[dict | None] = mapped_column(JSON)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class Tournament(Base, TimestampMixin):
    __tablename__ = "tournaments"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    league: Mapped[str] = mapped_column(String(64), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    split: Mapped[str | None] = mapped_column(String(64))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    n_matches: Mapped[int] = mapped_column(Integer, default=0)
    n_teams: Mapped[int] = mapped_column(Integer, default=0)
    has_playoffs: Mapped[bool] = mapped_column(Boolean, default=False)
    # Derived: winner of the chronologically last playoff game. Null when the
    # tournament has no playoff games in the data.
    derived_champion_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    dataset_version_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_versions.id"))
    __table_args__ = (UniqueConstraint("game_id", "source_key", name="uq_tournament_source"),)


class Team(Base, TimestampMixin):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    source_team_id: Mapped[str] = mapped_column(String(128))
    # True when the source had no team id and the team name was used instead.
    id_from_name: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str] = mapped_column(String(128), index=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    primary_league: Mapped[str | None] = mapped_column(String(64))
    first_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    n_matches: Mapped[int] = mapped_column(Integer, default=0)
    n_wins: Mapped[int] = mapped_column(Integer, default=0)
    current_elo: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("game_id", "source_team_id", name="uq_team_source"),)


class Player(Base, TimestampMixin):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    source_player_id: Mapped[str] = mapped_column(String(128))
    id_from_name: Mapped[bool] = mapped_column(Boolean, default=False)
    name: Mapped[str] = mapped_column(String(128), index=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    primary_position: Mapped[str | None] = mapped_column(String(16))
    first_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    n_matches: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("game_id", "source_player_id", name="uq_player_source"),)


class TeamRoster(Base):
    """Observed appearances of a player for a team in a tournament (derived
    from match rows, not from an official roster register)."""
    __tablename__ = "team_rosters"
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), index=True)
    position: Mapped[str | None] = mapped_column(String(16))
    games_played: Mapped[int] = mapped_column(Integer)
    first_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("team_id", "player_id", "tournament_id", "position",
                                       name="uq_roster_entry"),)


class Match(Base, TimestampMixin):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    source_match_id: Mapped[str] = mapped_column(String(128))
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), index=True)
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    game_in_series: Mapped[int | None] = mapped_column(Integer)
    patch: Mapped[str | None] = mapped_column(String(16))
    playoffs: Mapped[bool | None] = mapped_column(Boolean)
    blue_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    red_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    winner_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    data_completeness: Mapped[str | None] = mapped_column(String(16))
    source_url: Mapped[str | None] = mapped_column(String(512))
    dataset_version_id: Mapped[int | None] = mapped_column(ForeignKey("dataset_versions.id"))
    tournament = relationship("Tournament")
    __table_args__ = (UniqueConstraint("game_id", "source_match_id", name="uq_match_source"),)


class TeamMatchStatistic(Base):
    """Game-agnostic team result for one match (one row per team)."""
    __tablename__ = "team_match_statistics"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    opponent_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    side: Mapped[str] = mapped_column(String(8))
    result: Mapped[int] = mapped_column(Integer)  # 1 win, 0 loss
    kills: Mapped[int | None] = mapped_column(Integer)
    deaths: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("match_id", "team_id", name="uq_team_match"),)


class PlayerMatchStatistic(Base):
    """Game-agnostic player line for one match."""
    __tablename__ = "player_match_statistics"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    side: Mapped[str] = mapped_column(String(8))
    position: Mapped[str | None] = mapped_column(String(16))
    result: Mapped[int] = mapped_column(Integer)
    kills: Mapped[int | None] = mapped_column(Integer)
    deaths: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_player_match"),)


class EloRating(Base):
    """Pre- and post-match Elo for each team in each match, for the selected
    Elo configuration (see model_versions with model_key='elo')."""
    __tablename__ = "elo_ratings"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id", ondelete="CASCADE"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rating_before: Mapped[float] = mapped_column(Float)
    rating_after: Mapped[float] = mapped_column(Float)
    # League level of the team's home league after the game (league-offset
    # Elo); equals the initial rating for flat Elo. Null for older rows.
    league_rating: Mapped[float | None] = mapped_column(Float)
    expected_score: Mapped[float] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("model_version_id", "match_id", "team_id", name="uq_elo_row"),
                      Index("ix_elo_team_date", "team_id", "match_date"))


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    model_key: Mapped[str] = mapped_column(String(32))  # elo | elo_logit | logreg
    version: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))  # trained | unavailable | retired
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    periods: Mapped[dict | None] = mapped_column(JSON)
    hyperparameters: Mapped[dict | None] = mapped_column(JSON)
    feature_definitions: Mapped[list | None] = mapped_column(JSON)
    metrics: Mapped[dict | None] = mapped_column(JSON)
    artifact_path: Mapped[str | None] = mapped_column(String(512))
    dataset_version_ids: Mapped[list | None] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("game_id", "model_key", "version", name="uq_model_version"),)


class ModelPrediction(Base):
    """Out-of-sample predictions stored at evaluation time (test period)."""
    __tablename__ = "model_predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    split: Mapped[str] = mapped_column(String(16))  # validation | test
    prob_blue_win: Mapped[float] = mapped_column(Float)
    blue_won: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("model_version_id", "match_id", name="uq_prediction"),)


class AnalysisOutput(Base, TimestampMixin):
    """Computed research outputs (JSON), regenerated by the analytics jobs."""
    __tablename__ = "analysis_outputs"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    key: Mapped[str] = mapped_column(String(64))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("game_id", "key", name="uq_analysis_key"),)
