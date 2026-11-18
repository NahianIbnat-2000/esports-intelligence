"""Grid adapter. See adapters.py for access notes."""
from backend.app.providers.base_provider import BaseProvider


class GridProvider(BaseProvider):
    name = "grid"
    games = ("valorant", "lol", "cs2")
    documentation_url = "https://grid.gg/open-access/"
    env_key = "GRID_API_KEY"
    base_url = None  # GRID uses GraphQL endpoints issued with the account

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key} if self.api_key else {}
