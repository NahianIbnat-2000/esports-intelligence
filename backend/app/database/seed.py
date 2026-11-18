"""Idempotent reference data: games and known data sources.

These rows describe integration status. They are not statistics.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import DataSource, Game

GAMES = [
    {"slug": "lol", "name": "League of Legends", "status": "historical",
     "status_note": "Historical professional match data imported from Oracle's Elixir CSV files. "
                    "Not live data."},
    {"slug": "valorant", "name": "VALORANT", "status": "integration_pending",
     "status_note": "Provider adapter for Riot Games Open Access / GRID is built but no verified "
                    "credentials or data access are configured."},
    {"slug": "cs2", "name": "Counter-Strike 2", "status": "integration_pending",
     "status_note": "Provider adapters for GRID and PandaScore are built but no verified "
                    "credentials or data access are configured."},
]

SOURCES = [
    {"key": "oracles_elixir", "name": "Oracle's Elixir", "url": "https://oracleselixir.com/tools/downloads",
     "data_type": "historical",
     "license_note": "Match data is aggregated and released by Tim Sevenhuysen of OraclesElixir.com, "
                     "provided free of charge for analysts, commentators and fans, for non-commercial use. "
                     "Game statistics are the property of Riot Games and their use must follow Riot "
                     "Games' terms and policies. Raw files are not redistributed with this project.",
     "attribution": "Data: Oracle's Elixir (oracleselixir.com), Tim Sevenhuysen. Game statistics © Riot Games."},
    {"key": "grid", "name": "GRID (Riot Games Open Access)", "url": "https://grid.gg/open-access/",
     "data_type": "live", "license_note": "Not connected. Access requires an approved GRID account.",
     "attribution": None},
    {"key": "pandascore", "name": "PandaScore", "url": "https://developers.pandascore.co/",
     "data_type": "live", "license_note": "Not connected. Plan coverage must be verified on the "
                                          "PandaScore dashboard.", "attribution": None},
]


def seed_reference_data(db: Session) -> None:
    for g in GAMES:
        row = db.scalar(select(Game).where(Game.slug == g["slug"]))
        if row is None:
            db.add(Game(**g))
        else:
            # Status may have been upgraded (e.g. to "active") by an operator;
            # only the descriptive note is refreshed here.
            row.name = g["name"]
    for s in SOURCES:
        row = db.scalar(select(DataSource).where(DataSource.key == s["key"]))
        if row is None:
            db.add(DataSource(**s))
        else:
            for k, v in s.items():
                setattr(row, k, v)
    db.commit()
