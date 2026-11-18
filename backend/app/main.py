"""FastAPI application.

Run locally (from the repository root):
    uvicorn backend.app.main:app --reload
Interactive API docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes.v1 import router
from backend.app.core.config import get_settings
from backend.app.database.seed import seed_reference_data
from backend.app.database.session import get_sessionmaker

log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with get_sessionmaker()() as db:
            seed_reference_data(db)
    except Exception as exc:  # the API still starts; /health reports the database state
        log.error("Could not seed reference data: %s", exc)
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="1.0.0", lifespan=lifespan,
                  description="Research-driven esports analytics API. Historical League of Legends data from "
                              "Oracle's Elixir; VALORANT and CS2 integrations pending. Every response carries "
                              "its data status, source and sample period.")
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
                       expose_headers=["X-Data-Attribution", "X-Rows-Exported", "X-Rows-Matching"])

    hits: dict[str, deque] = defaultdict(deque)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        limit = s.rate_limit_per_minute
        if limit > 0 and request.url.path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            q = hits[ip]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= limit:
                return JSONResponse({"detail": "Rate limit exceeded. Try again in a minute."}, status_code=429,
                                    headers={"Retry-After": "60"})
            q.append(now)
        return await call_next(request)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "Internal error. The incident has been logged."}, status_code=500)

    app.include_router(router)
    return app


app = create_app()
