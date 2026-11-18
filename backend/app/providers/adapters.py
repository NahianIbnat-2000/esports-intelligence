"""Concrete adapters. None has verified endpoints in Version 1.0.

Notes from the providers' public pages (checked November 2026; re-check
before enabling anything):
- Riot Games Open Access powered by GRID: official LoL and VALORANT esports
  data for students, researchers, hobbyists and early-stage developers
  (Central Data Feed, Series State API). Requires an approved account.
- GRID Open Access: CS2 and Dota 2 esports data via API; approved account
  and daily rate limits.
- PandaScore: API key with plan-dependent coverage and rate limits; check
  which historical and post-match data your plan includes on its dashboard.
- Riot Developer API (developer.riotgames.com) covers ranked player data,
  not professional esports results.
"""
from __future__ import annotations

from backend.app.core.config import get_settings
from backend.app.providers.base_provider import BaseProvider
from backend.app.providers.grid_provider import GridProvider
from backend.app.providers.pandascore_provider import PandaScoreProvider
from backend.app.providers.riot_provider import RiotProvider

__all__ = ["GridProvider", "PandaScoreProvider", "RiotProvider"]


def all_providers() -> list[BaseProvider]:
    s = get_settings()
    return [RiotProvider(s.riot_api_key), GridProvider(s.grid_api_key), PandaScoreProvider(s.pandascore_api_key)]


def providers_for_game(game: str) -> list[BaseProvider]:
    return [p for p in all_providers() if game in p.games]
