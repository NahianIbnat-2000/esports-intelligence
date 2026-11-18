"""League of Legends specific statistics (one-to-one extensions).

Every metric is nullable. Missing values in the source stay NULL; they are
never converted to zero. Definitions are in docs/data_dictionary.md.
"""
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.session import Base


class LolTeamMatchStats(Base):
    __tablename__ = "lol_team_match_stats"
    team_match_statistic_id: Mapped[int] = mapped_column(
        ForeignKey("team_match_statistics.id", ondelete="CASCADE"), primary_key=True)
    dragons: Mapped[int | None] = mapped_column(Integer)
    barons: Mapped[int | None] = mapped_column(Integer)
    towers: Mapped[int | None] = mapped_column(Integer)
    heralds: Mapped[int | None] = mapped_column(Integer)
    inhibitors: Mapped[int | None] = mapped_column(Integer)
    first_blood: Mapped[int | None] = mapped_column(Integer)
    first_dragon: Mapped[int | None] = mapped_column(Integer)
    first_baron: Mapped[int | None] = mapped_column(Integer)
    first_tower: Mapped[int | None] = mapped_column(Integer)
    damage_to_champions: Mapped[float | None] = mapped_column(Float)
    dpm: Mapped[float | None] = mapped_column(Float)
    vision_score: Mapped[float | None] = mapped_column(Float)
    vspm: Mapped[float | None] = mapped_column(Float)
    total_gold: Mapped[float | None] = mapped_column(Float)
    earned_gpm: Mapped[float | None] = mapped_column(Float)
    total_cs: Mapped[float | None] = mapped_column(Float)
    cspm: Mapped[float | None] = mapped_column(Float)
    golddiff_at_15: Mapped[float | None] = mapped_column(Float)
    xpdiff_at_15: Mapped[float | None] = mapped_column(Float)
    csdiff_at_15: Mapped[float | None] = mapped_column(Float)


class LolPlayerMatchStats(Base):
    __tablename__ = "lol_player_match_stats"
    player_match_statistic_id: Mapped[int] = mapped_column(
        ForeignKey("player_match_statistics.id", ondelete="CASCADE"), primary_key=True)
    champion: Mapped[str | None] = mapped_column(String(64))
    kda: Mapped[float | None] = mapped_column(Float)
    damage_to_champions: Mapped[float | None] = mapped_column(Float)
    dpm: Mapped[float | None] = mapped_column(Float)
    damage_share: Mapped[float | None] = mapped_column(Float)
    vision_score: Mapped[float | None] = mapped_column(Float)
    vspm: Mapped[float | None] = mapped_column(Float)
    wards_placed: Mapped[float | None] = mapped_column(Float)
    control_wards_bought: Mapped[float | None] = mapped_column(Float)
    earned_gpm: Mapped[float | None] = mapped_column(Float)
    gold_share: Mapped[float | None] = mapped_column(Float)
    total_cs: Mapped[float | None] = mapped_column(Float)
    cspm: Mapped[float | None] = mapped_column(Float)
    golddiff_at_15: Mapped[float | None] = mapped_column(Float)
    csdiff_at_15: Mapped[float | None] = mapped_column(Float)
