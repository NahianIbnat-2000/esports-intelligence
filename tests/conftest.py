"""Test configuration.

Tests never call external APIs and never touch data/ in the repository:
DATA_DIR, MODELS_DIR and DATABASE_URL point to a temporary directory and an
SQLite file before any project module is imported. The fixture data are
SYNTHETIC (tests/fixtures/make_oe_fixture.py) and only exist inside tests.

Set TEST_POSTGRES_URL (e.g. postgresql+psycopg://postgres@localhost:5432/ei_test)
to also run the PostgreSQL migration test.
"""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ei-tests-"))
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["MODELS_DIR"] = str(_TMP / "models")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
for k in ("RIOT_API_KEY", "GRID_API_KEY", "PANDASCORE_API_KEY"):
    os.environ.pop(k, None)

import pytest  # noqa: E402

from tests.fixtures.make_oe_fixture import make_fixture  # noqa: E402


@pytest.fixture(scope="session")
def tmp_root() -> Path:
    return _TMP


@pytest.fixture(scope="session")
def fixture_csv(tmp_root) -> Path:
    path = tmp_root / "SYNTHETIC_oe_fixture.csv"
    make_fixture(n_days=500).to_csv(path, index=False)
    return path


@pytest.fixture(scope="session")
def fresh_db():
    """Create the schema in the SQLite test database (empty)."""
    from backend.app.database.seed import seed_reference_data
    from backend.app.database.session import Base, get_engine, get_sessionmaker
    import backend.app.models  # noqa: F401
    Base.metadata.create_all(get_engine())
    with get_sessionmaker()() as db:
        seed_reference_data(db)
    return True
