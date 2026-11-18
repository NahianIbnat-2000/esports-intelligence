"""Alembic migrations: the migration must create exactly the tables defined
by the models. Runs on SQLite always, and on PostgreSQL when
TEST_POSTGRES_URL is set."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

import backend.app.models  # noqa: F401
from backend.app.database.session import Base

ROOT = Path(__file__).resolve().parents[2]


def _upgrade(url: str) -> None:
    env = {**os.environ, "DATABASE_URL": url}
    r = subprocess.run([sys.executable, "-m", "alembic", "-c", str(ROOT / "backend" / "alembic.ini"), "upgrade", "head"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def _check(url: str) -> None:
    _upgrade(url)
    tables = set(inspect(create_engine(url)).get_table_names())
    assert set(Base.metadata.tables) <= tables


def test_sqlite_migration(tmp_path):
    _check(f"sqlite:///{tmp_path / 'm.db'}")


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set")
def test_postgres_migration():
    url = os.environ["TEST_POSTGRES_URL"]
    eng = create_engine(url)
    with eng.begin() as c:
        c.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    _check(url)
