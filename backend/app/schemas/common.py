"""Response schemas. Every response uses the same envelope:

  { "data": ..., "meta": { game, data_status, data_type, source, sample_period,
                           pagination?, generated_at, notes[] } }

`data` is null (never an invented placeholder) when the information is not
available, and meta.data_status says why.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

DataStatus = Literal["available", "empty", "integration_pending", "unavailable", "insufficient_data"]


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class SamplePeriod(BaseModel):
    start: datetime | None = None
    end: datetime | None = None


class Meta(BaseModel):
    game: str | None = None
    data_status: DataStatus = "available"
    data_type: Literal["historical", "live", "demo", "none"] = "historical"
    source: str | None = None
    attribution: str | None = None
    sample_period: SamplePeriod | None = None
    pagination: Pagination | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: list[str] = []


class Envelope(BaseModel, Generic[T]):
    data: T | None
    meta: Meta


class GameInfo(BaseModel):
    slug: str
    name: str
    status: str
    status_note: str | None
    n_matches: int | None
    coverage_start: datetime | None
    coverage_end: datetime | None


class TeamSummary(BaseModel):
    slug: str
    name: str
    primary_league: str | None
    n_matches: int
    n_wins: int
    win_rate: float | None
    current_elo: float | None
    first_match_date: datetime | None
    last_match_date: datetime | None
    id_from_name: bool


class PlayerSummary(BaseModel):
    slug: str
    name: str
    primary_position: str | None
    n_matches: int
    first_match_date: datetime | None
    last_match_date: datetime | None
    latest_team: str | None = None
    latest_team_slug: str | None = None


class TournamentSummary(BaseModel):
    slug: str
    name: str
    league: str
    year: int | None
    split: str | None
    start_date: datetime | None
    end_date: datetime | None
    n_matches: int
    n_teams: int
    has_playoffs: bool
    derived_champion: str | None
    derived_champion_slug: str | None


class MatchSummary(BaseModel):
    id: int
    source_match_id: str
    match_date: datetime
    tournament: str
    tournament_slug: str
    league: str
    playoffs: bool | None
    game_in_series: int | None
    blue_team: str
    blue_team_slug: str
    red_team: str
    red_team_slug: str
    winner: str
    winner_slug: str
    duration_seconds: int | None
    patch: str | None
    data_completeness: str | None


class PredictionRequest(BaseModel):
    game: str = "lol"
    team_a: str = Field(..., description="team slug")
    team_b: str = Field(..., description="team slug")
    as_of: date = Field(..., description="prediction date; only games before this date are used")
    team_a_side: Literal["blue", "red", "unknown"] = "unknown"
    context: Literal["domestic", "international"] = "domestic"


class ModelProbability(BaseModel):
    model_key: str
    display_name: str
    version: str
    status: str
    prob_team_a: float | None
    prob_team_b: float | None
    reason: str | None = None


class PredictionResponse(BaseModel):
    team_a: dict[str, Any]
    team_b: dict[str, Any]
    as_of: date
    team_a_side: str
    context: str
    predictions: list[ModelProbability]
    inputs: dict[str, Any]
    generated_at: datetime
    caveats: list[str]
    explanation: dict[str, Any] | None = None
