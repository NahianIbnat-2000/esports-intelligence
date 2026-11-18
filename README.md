# Esports Intelligence

**Beyond the Game. Inside the Data.**

A research-driven esports analytics platform. Version 1.0 analyses professional
League of Legends games from the public historical files of
[Oracle's Elixir](https://oracleselixir.com/tools/downloads). VALORANT and
Counter-Strike 2 have provider adapters but no verified data integration, and
the site says so instead of showing empty or invented numbers.

Central research question: *can machine learning predict professional League of
Legends game outcomes better than an Elo benchmark?*

## What is in the box

| Part | Folder | Stack |
|---|---|---|
| Web app (8 sections) | `frontend/` | Next.js 15 (App Router), React 19, TypeScript, Tailwind, Recharts, React Query |
| API | `backend/app/` | FastAPI, Pydantic, SQLAlchemy 2, Alembic |
| Database | `backend/alembic/` | PostgreSQL (SQLite works for tests) |
| Ingestion pipeline | `pipelines/oracle_elixir/` | pandas: acquire, inspect, clean, validate, transform, load |
| Ratings and models | `machine_learning/` | Elo, calibrated Elo, logistic regression (scikit-learn), evaluation |
| Economics / statistics | `analytics/` | HHI, Gini, Lorenz, Noll-Scully, persistence, upset rate |
| Research reports | `backend/app/services/research.py` | Rule-generated from computed outputs |
| Provider adapters | `backend/app/providers/` | Riot, GRID, PandaScore (pending) |
| Tests | `tests/`, `frontend/tests/` | pytest, Vitest + Testing Library |
| Docs | `docs/` | Architecture, database, API, methodology, deployment, report |

## Quick start (local)

Requirements: Python 3.12+, Node 22+, PostgreSQL 14+ (or Docker).

```bash
cp .env.example .env              # set DATABASE_URL
make install                      # pip + npm
make db                           # create tables (Alembic)

# 1. Download yearly CSV files from https://oracleselixir.com/tools/downloads
# 2. Import, clean, validate and load them; then train models and run analytics
make all FILES="~/Downloads/2024_LoL_esports_match_data_from_OraclesElixir.csv ~/Downloads/2025_LoL_esports_match_data_from_OraclesElixir.csv"

make api                          # http://localhost:8000/docs
make web                          # http://localhost:3000
```

With Docker: `docker compose up --build`, then put the CSV files in
`./data-import/` and run
`docker compose run --rm api make all FILES="/data-import/<file>.csv"`.

Use at least two seasons. Models need 500 training games and 200 test games
after the burn-in, or they stay switched off with an explanation.

## What the platform shows (v1.2)

- Overview: data coverage, data quality indicators, Elo methodology, model comparison against
  prevalence baselines.
- Predictions: five models scored on the same test games (two constant baselines, Elo with league
  offsets, calibrated Elo, logistic regression), calibration, ROC, confusion matrices, probability
  distributions, paired cluster-bootstrap intervals, explained predictions and filterable
  historical predictions.
- Analytics: competitive balance (HHI, Gini, Lorenz, Noll-Scully) by league and season, champion
  placements, Elo trajectories, consistency, player metrics by role and season, season trends.
- Data quality report, data provenance, Data Explorer with research filters, three research reports.

## Data integrity rules (enforced in code)

- Only values computed from imported records are shown. Missing values are
  `null` and display as "n/a" or "Unavailable", never as 0.
- One match = one game. Player rows are never counted as games.
- Every excluded row has a written reason (`data/reports/exclusions.csv`).
- Every API response carries `data_status`, `data_type`, source and sample period.
- Predictions are refused for dates inside the training/validation period and
  for teams with fewer than 5 earlier games.
- Research reports without results are labelled **proposed**.
- No prize money, country, or live data is shown, because the source has none.

## Tests

```bash
make test                                  # pytest + tsc + vitest
TEST_POSTGRES_URL=postgresql+psycopg://... python -m pytest   # adds the Postgres migration test
```

Tests use a clearly labelled SYNTHETIC fixture (`tests/fixtures/make_oe_fixture.py`,
all names start with `SYNTH`). It never enters a production database.

## Licensing of data

Oracle's Elixir data is provided free of charge for non-commercial use by
analysts, commentators and fans; game statistics are the property of Riot
Games. Raw files are **not** redistributed in this repository; the pipeline
re-creates everything from the files you download. See `docs/data_sources.md`.

## Documentation

`docs/runbook.md`, `docs/architecture.md`, `docs/database.md`, `docs/api.md`,
`docs/data_sources.md`, `docs/data_dictionary.md`, `docs/methodology.md`, `docs/RESULTS_2020_2026.md`,
`docs/AUDIT_AND_IMPROVEMENTS_v1.2.md`,
`docs/deployment.md`, `docs/DEVELOPMENT_REPORT.md`.
