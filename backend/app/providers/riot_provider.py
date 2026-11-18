"""Riot adapter. See adapters.py for access notes."""
from backend.app.providers.base_provider import BaseProvider


class RiotProvider(BaseProvider):
    name = "riot"
    games = ("lol", "valorant")
    documentation_url = "https://developer.riotgames.com/"
    env_key = "RIOT_API_KEY"
    base_url = None  # regional hosts; set when an endpoint is verified

    def _headers(self) -> dict:
        return {"X-Riot-Token": self.api_key} if self.api_key else {}
