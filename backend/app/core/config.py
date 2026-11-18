"""Application settings, loaded from environment variables.

No credential has a default value. Provider keys stay on the server and are
never sent to the frontend.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_name: str = "Esports Intelligence API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres@localhost:5432/esports"

    # Comma separated list of allowed browser origins.
    cors_origins: str = "http://localhost:3000"

    @field_validator("cors_origins")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return ",".join(o.strip().rstrip("/") for o in v.split(","))

    # Provider credentials (server side only). Empty means "not configured".
    riot_api_key: str = ""
    grid_api_key: str = ""
    pandascore_api_key: str = ""

    # Data locations
    data_dir: Path = REPO_ROOT / "data"
    models_dir: Path = REPO_ROOT / "machine_learning" / "models" / "artifacts"

    # Data explorer export. Oracle's Elixir data is free for non-commercial
    # use and game statistics belong to Riot Games. Keep exports small and
    # attributed. Set to false if your use is not covered by those terms.
    allow_csv_export: bool = True
    max_export_rows: int = 5000

    # Simple in-process rate limit (requests per minute per client IP).
    rate_limit_per_minute: int = 120

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        """Accept the plain connection strings that Supabase, Render and Neon
        show (postgres:// or postgresql://) and use the psycopg 3 driver."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
