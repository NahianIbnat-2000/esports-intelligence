# API reference

Base path `/api/v1`. Interactive OpenAPI docs at `/docs` (Swagger) and `/redoc`.

## Envelope

```json
{
  "data": "... or null",
  "meta": {
    "game": "lol",
    "data_status": "available | empty | integration_pending | unavailable | insufficient_data",
    "data_type": "historical | live | demo | none",
    "source": "Oracle's Elixir",
    "attribution": "...",
    "sample_period": {"start": "...", "end": "..."},
    "pagination": {"page": 1, "page_size": 25, "total": 812, "pages": 33},
    "generated_at": "...",
    "notes": []
  }
}
```

`data` is `null` when information is not available; the reason is in `meta`.
Errors: `{"detail": "..."}` with 404 (unknown item), 409 (unavailable, e.g.
untrained model or pending game), 422 (invalid input or in-sample prediction
date), 429 (rate limit).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | database check |
| GET | `/games` | games, status, coverage |
| GET | `/data-status` | per game: files, last ingestion, freshness |
| GET | `/data-provenance` | sources, files, cleaning procedure, quality report, providers |
| GET | `/providers` | adapter status (key set yes/no; never the key) |
| GET | `/overview?game&league` | KPIs, top teams by Elo, recent games, trends, research highlight |
| GET | `/tournaments?game&q&league&year&sort&page&page_size` | directory |
| GET | `/tournaments/filters` | leagues and years |
| GET | `/tournaments/{slug}` | standings (regular/playoffs/all), games, stats |
| GET | `/teams?q&league&min_matches&sort&page` | `sort` = elo, matches, win_rate, name, recent |
| GET | `/teams/{slug}` | profile, Elo history, form, tournaments, head-to-head, roster |
| GET | `/teams/compare?a&b` | head-to-head and Elo paths |
| GET | `/players?q&position&min_matches&sort&page` | |
| GET | `/players/{slug}` | career, by year, team history, recent games, metric definitions |
| GET | `/players/compare?a&b` | warns when positions differ |
| GET | `/matches?team&tournament&league&date_from&date_to&page` | |
| GET | `/analytics/team-performance?league&min_matches` | Elo ranking and distribution |
| GET | `/analytics/player-performance?metric&position&min_matches&year` | distribution, percentiles, leaders |
| GET | `/analytics/competitive-balance` | balance, title concentration, persistence, upset rate |
| GET | `/analytics/historical` | side advantage, game length, per year, per month |
| GET | `/analytics/regional` | league coverage, international results by home league |
| GET | `/predictions/models` | model versions with periods and metrics |
| GET | `/predictions/test-matches?team&limit` | stored out-of-sample predictions with outcomes |
| POST | `/predictions` | body below |
| GET | `/research` | report list and status |
| GET | `/research/{slug}` | full report |
| GET | `/data-explorer/datasets` | datasets and data dictionary |
| GET | `/data-explorer?dataset&columns&q&league&date_from&date_to&sort&order&page` | |
| GET | `/data-explorer/export?...` | CSV (max 5,000 rows; `ALLOW_CSV_EXPORT`) |

### POST /predictions

```json
{"game": "lol", "team_a": "t1", "team_b": "gen-g", "as_of": "2025-11-10",
 "team_a_side": "unknown", "context": "international"}
```

Rules: `as_of` must be after the end of the validation period; both teams need
5 earlier games; only games before `as_of` are used. The response lists each
model's probability, version, the inputs and the caveats.
