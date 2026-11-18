"""PandaScore adapter. See adapters.py for access notes."""
from backend.app.providers.base_provider import BaseProvider


class PandaScoreProvider(BaseProvider):
    name = "pandascore"
    games = ("cs2", "lol", "valorant")
    documentation_url = "https://developers.pandascore.co/"
    env_key = "PANDASCORE_API_KEY"
    base_url = "https://api.pandascore.co"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
