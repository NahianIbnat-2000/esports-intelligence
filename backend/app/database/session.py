"""Database engine and session management."""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("postgresql"):
        # Always talk to the database in UTC, whatever the server default is.
        kwargs["connect_args"] = {"options": "-c timezone=UTC"}
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    return create_engine(url, **kwargs)


def get_sessionmaker(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
