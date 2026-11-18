"""Provider adapter interface for live or API-based esports data.

Version 1.0 has NO verified live provider. The adapters below provide the
plumbing (authentication from environment variables, retries with
exponential backoff, a client-side rate limit, response caching) and a fixed
method interface. A method only returns data when its endpoint has been
verified against the provider's official documentation with a working key
and added to `verified_endpoints`. Otherwise it returns a structured
`UnsupportedData` response. Nothing is ever fabricated.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx


@dataclass
class UnsupportedData:
    provider: str
    method: str
    status: str  # not_configured | not_verified | unsupported
    reason: str
    documentation: str | None = None
    data: None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProviderResult:
    provider: str
    method: str
    status: str
    data: Any
    fetched_at: float = field(default_factory=time.time)


class RateLimiter:
    """Simple minimum-interval limiter (requests per second)."""

    def __init__(self, per_second: float):
        self.min_interval = 1.0 / per_second if per_second > 0 else 0
        self._last = 0.0

    def wait(self) -> None:
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


class BaseProvider:
    name = "base"
    games: tuple[str, ...] = ()
    documentation_url: str | None = None
    base_url: str | None = None
    env_key: str | None = None
    # method name -> endpoint path, filled only after verification.
    verified_endpoints: dict[str, str] = {}
    requests_per_second: float = 1.0
    max_retries: int = 4
    cache_seconds: int = 300

    def __init__(self, api_key: str | None, client: httpx.Client | None = None):
        self.api_key = api_key or None
        self._client = client
        self._limiter = RateLimiter(self.requests_per_second)
        self._cache: dict[str, tuple[float, Any]] = {}

    # -------------------------------------------------------------- status
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict:
        return {"provider": self.name, "games": list(self.games), "configured": self.is_configured(),
                "verified_endpoints": sorted(self.verified_endpoints), "documentation": self.documentation_url,
                "env_var": self.env_key,
                "state": "integration_pending" if not self.verified_endpoints else
                ("active" if self.is_configured() else "not_configured")}

    def _unsupported(self, method: str) -> UnsupportedData:
        if not self.is_configured():
            return UnsupportedData(self.name, method, "not_configured",
                                   f"{self.env_key} is not set. Provider access has not been configured.",
                                   self.documentation_url)
        if method not in self.verified_endpoints:
            return UnsupportedData(self.name, method, "not_verified",
                                   "This endpoint has not been verified against the provider's current "
                                   "documentation and plan, so it is not called.", self.documentation_url)
        return UnsupportedData(self.name, method, "unsupported", "Not supported.", self.documentation_url)

    # ---------------------------------------------------------------- http
    def _headers(self) -> dict:
        return {}

    def _get(self, path: str, params: dict | None = None) -> Any:
        key = f"{path}?{sorted((params or {}).items())}"
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.cache_seconds:
            return hit[1]
        client = self._client or httpx.Client(base_url=self.base_url, timeout=30)
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            self._limiter.wait()
            try:
                r = client.get(path, params=params, headers=self._headers())
                if r.status_code == 429 or r.status_code >= 500:
                    raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
                r.raise_for_status()
                data = r.json()
                self._cache[key] = (time.time(), data)
                return data
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                retryable = isinstance(exc, httpx.TransportError) or (
                    exc.response is not None and (exc.response.status_code == 429 or exc.response.status_code >= 500))
                if not retryable or attempt == self.max_retries:
                    raise
                retry_after = None
                if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                    retry_after = exc.response.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else delay)
                delay *= 2

    def _call(self, method: str, params: dict | None = None):
        if not self.is_configured() or method not in self.verified_endpoints:
            return self._unsupported(method)
        return ProviderResult(self.name, method, "ok", self._get(self.verified_endpoints[method], params))

    # ----------------------------------------------------------- interface
    def get_tournaments(self, **params):
        return self._call("get_tournaments", params)

    def get_matches(self, **params):
        return self._call("get_matches", params)

    def get_teams(self, **params):
        return self._call("get_teams", params)

    def get_players(self, **params):
        return self._call("get_players", params)

    def get_match_statistics(self, **params):
        return self._call("get_match_statistics", params)
