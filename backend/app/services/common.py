"""Shared helpers for services: game lookup, metadata, pagination, caching."""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from functools import wraps

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import DataSource, Game, Match
from backend.app.schemas.common import Meta, Pagination, SamplePeriod

SOURCE_BY_GAME = {"lol": "oracles_elixir"}


def get_game(db: Session, slug: str) -> Game:
    g = db.scalar(select(Game).where(Game.slug == slug))
    if g is None:
        raise HTTPException(status_code=404, detail=f"Unknown game '{slug}'. Use lol, valorant or cs2.")
    return g


def coverage(db: Session, game: Game) -> SamplePeriod:
    lo, hi = db.execute(select(func.min(Match.match_date), func.max(Match.match_date))
                        .where(Match.game_id == game.id)).one()
    return SamplePeriod(start=lo, end=hi)


def meta_for(db: Session, game: Game, **kw) -> Meta:
    """Metadata for a game. data_status reflects whether any data is loaded."""
    if game.status == "integration_pending":
        return Meta(game=game.slug, data_status="integration_pending", data_type="none",
                    notes=[game.status_note or "Provider integration pending."], **kw)
    period = coverage(db, game)
    src = None
    if game.slug in SOURCE_BY_GAME:
        src = db.scalar(select(DataSource).where(DataSource.key == SOURCE_BY_GAME[game.slug]))
    status = kw.pop("data_status", "available" if period.start else "empty")
    notes = kw.pop("notes", [])
    if status == "empty":
        notes = notes + ["No historical data has been imported yet. Run the Oracle's Elixir pipeline "
                         "(see docs/runbook.md)."]
    return Meta(game=game.slug, data_status=status, data_type="historical" if period.start else "none",
                source=src.name if src else None, attribution=src.attribution if src else None,
                sample_period=period, notes=notes, **kw)


def paginate(total: int, page: int, page_size: int) -> Pagination:
    return Pagination(page=page, page_size=page_size, total=total, pages=max(1, math.ceil(total / page_size)))


def ttl_cache(seconds: int = 300) -> Callable:
    """Small in-process cache for read-only queries. Keys exclude the DB
    session. Data only changes when pipeline jobs run; clear() on demand."""
    def deco(fn):
        store: dict = {}
        lock = threading.Lock()

        @wraps(fn)
        def wrapper(db, *args, **kwargs):
            norm = lambda v: ("game", v.slug) if isinstance(v, Game) else v  # noqa: E731
            key = (str(db.get_bind().url), tuple(norm(a) for a in args),
                   tuple(sorted((k, norm(v)) for k, v in kwargs.items())))
            now = time.monotonic()
            with lock:
                hit = store.get(key)
                if hit and now - hit[0] < seconds:
                    return hit[1]
            val = fn(db, *args, **kwargs)
            with lock:
                store[key] = (now, val)
            return val
        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        _CACHES.append(store)
        return wrapper
    return deco


_CACHES: list[dict] = []


def clear_all_caches() -> None:
    for c in _CACHES:
        c.clear()
