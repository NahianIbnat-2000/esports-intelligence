"""Static snapshot of the API for the website (hybrid hosting).

Calls the API in-process for a fixed list of GET requests (the default views of every page,
filter variants of the summary pages, and detail pages of the most-viewed entities) and writes
each response to frontend/public/snapshot/<hash>.json, plus manifest.json with the list of keys.

The website reads a snapshot file when one exists for the exact request and calls the live API
otherwise. Responses are the API's own output; nothing is computed here.

Run after every data reload, from the project root:
    python -m backend.app.snapshot            (or: make snapshot)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app

log = logging.getLogger("snapshot")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend" / "public" / "snapshot"

GAMES = ["lol", "valorant", "cs2"]
PLAYER_METRICS = ["kda", "kill_participation", "dpm", "damage_share", "cspm", "earned_gpm", "gold_share", "vspm",
                  "golddiff_at_15", "csdiff_at_15", "kills", "deaths", "assists"]
POSITIONS = ["", "top", "jng", "mid", "bot", "sup"]
N_TEAMS, N_PLAYERS, N_MATCHES, N_TOURNAMENTS = 150, 250, 400, 120
LIST_PAGES = 4


def canonical(path: str, params: dict | None) -> str:
    """Same rule as frontend/lib/snapshot.ts: drop empty values, sort keys, String() the values."""
    items = []
    for k, v in sorted((params or {}).items()):
        if v is None or v == "":
            continue
        items.append(f"{k}={str(v).lower() if isinstance(v, bool) else v}")
    return path + ("?" + "&".join(items) if items else "")


def fnv1a(s: str) -> str:
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


class Snap:
    def __init__(self, client: TestClient, stamp: str):
        self.c, self.stamp, self.keys, self.bytes = client, stamp, [], 0

    def get(self, path: str, params: dict | None = None) -> dict | None:
        key = canonical(path, params)
        if key in self.keys:
            return None
        r = self.c.get("/api/v1" + path, params={k: v for k, v in (params or {}).items() if v not in (None, "")})
        if r.status_code != 200:
            log.warning("skip %s (%s)", key, r.status_code)
            return None
        body = r.json()
        if isinstance(body, dict) and isinstance(body.get("meta"), dict):
            body["meta"]["snapshot_generated_at"] = self.stamp
        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        (OUT / f"{fnv1a(key)}.json").write_text(raw, encoding="utf-8")
        self.keys.append(key)
        self.bytes += len(raw.encode("utf-8"))
        return body


def build() -> dict:
    # in-process export: switch the per-client rate limit off for this run only
    os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
    from backend.app.core.config import get_settings
    get_settings.cache_clear()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.json"):   # clear old files but keep the folder (it is a Docker mount)
        f.unlink()
    with TestClient(create_app()) as client:
        s = Snap(client, stamp)
        s.get("/games")
        s.get("/data-provenance")
        s.get("/data-explorer/datasets")
        for g in GAMES:
            for p in ["/overview", "/tournaments/filters", "/research", "/predictions/models", "/analytics/team-performance"]:
                s.get(p, {"game": g})
            s.get("/teams", {"game": g, "sort": "matches", "min_matches": "10", "page": 1, "page_size": 25})
            s.get("/players", {"game": g, "sort": "matches", "min_matches": "10", "page": 1, "page_size": 25})
            s.get("/tournaments", {"game": g, "sort": "recent", "page": 1, "page_size": 25})

        filters = s.get("/tournaments/filters", {"game": "lol"}) or client.get("/api/v1/tournaments/filters?game=lol").json()
        leagues = [x["league"] for x in (filters.get("data") or {}).get("leagues", [])]
        for lg in leagues:
            s.get("/overview", {"game": "lol", "league": lg})
        s.get("/data-quality", {"game": "lol"})
        s.get("/ticker", {"game": "lol"})

        # research reports
        reports = (client.get("/api/v1/research?game=lol").json().get("data") or [])
        for r in reports:
            s.get(f"/research/{r['slug']}", {"game": "lol"})

        # analytics modules (default views and their filter options)
        for p in ["/analytics/competitive-balance", "/analytics/historical", "/analytics/regional"]:
            s.get(p, {"game": "lol"})
        def team_perf(params: dict):
            # the page also draws Elo trajectories of the first five teams in the ranking
            body = s.get("/analytics/team-performance", params)
            data = (body or {}).get("data") or {}
            slugs = data.get("default_trajectory_teams") or [t["slug"] for t in (data.get("teams") or [])[:5]]
            if slugs:
                s.get("/analytics/team-trajectories", {"game": "lol", "teams": ",".join(slugs)})

        for mm in ["10", "30", "60", "100"]:
            for scope in ["", "all"]:
                team_perf({"game": "lol", "min_matches": mm, "scope": scope})
        for lg in leagues[:40]:
            team_perf({"game": "lol", "league": lg, "min_matches": "30"})
        for m in PLAYER_METRICS:
            for pos in POSITIONS:
                s.get("/analytics/player-performance", {"game": "lol", "metric": m, "position": pos, "min_matches": "20"})

        # predictions: historical predictions (no team selected)
        for split in ["test", "validation", ""]:
            for page in range(1, LIST_PAGES + 1):
                s.get("/predictions/history", {"game": "lol", "split": split, "page": page, "page_size": 25})

        # list pages (default sort, first pages)
        for page in range(1, LIST_PAGES + 1):
            for sort in ["matches", "elo", "win_rate"]:
                s.get("/teams", {"game": "lol", "sort": sort, "min_matches": "10", "page": page, "page_size": 25})
            s.get("/players", {"game": "lol", "sort": "matches", "min_matches": "10", "page": page, "page_size": 25})
            s.get("/tournaments", {"game": "lol", "sort": "recent", "page": page, "page_size": 25})
            s.get("/series", {"game": "lol", "page": page, "page_size": 30})
        for lg in leagues[:40]:
            s.get("/series", {"game": "lol", "league": lg, "page": 1, "page_size": 30})

        # detail pages of the most-viewed entities
        top_teams = client.get("/api/v1/teams", params={"game": "lol", "sort": "elo", "min_matches": 10,
                                                        "page_size": N_TEAMS}).json().get("data") or []
        for t in top_teams:
            s.get(f"/teams/{t['slug']}", {"game": "lol"})
        top_players = client.get("/api/v1/players", params={"game": "lol", "sort": "matches", "min_matches": 10,
                                                            "page_size": N_PLAYERS}).json().get("data") or []
        for p in top_players:
            s.get(f"/players/{p['slug']}", {"game": "lol"})
        tours = client.get("/api/v1/tournaments", params={"game": "lol", "sort": "recent",
                                                          "page_size": N_TOURNAMENTS}).json().get("data") or []
        for t in tours:
            s.get(f"/tournaments/{t['slug']}", {"game": "lol"})
        recent = []
        for page in range(1, N_MATCHES // 100 + 1):
            recent += client.get("/api/v1/matches", params={"game": "lol", "page": page,
                                                            "page_size": 100}).json().get("data") or []
        for m in recent:
            s.get(f"/matches/{m['id']}", {"game": "lol"})

    manifest = {"generated_at": stamp, "n_files": len(s.keys), "bytes": s.bytes, "keys": sorted(s.keys)}
    (OUT / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    log.info("snapshot: %d files, %.1f MB -> %s", len(s.keys), s.bytes / 1e6, OUT)
    return manifest


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build()
