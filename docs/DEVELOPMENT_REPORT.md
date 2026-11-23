# Development report: Esports Intelligence v1.0

> Historical record, kept as written. Current status of every issue: [`ISSUE_STATUS.md`](ISSUE_STATUS.md) (23 November 2026).

Date: 18 November 2026

## Summary

The full application is built, tested and has been run on the real Oracle's Elixir
files for 2020-2026 (75,830 games, 3 Jan 2020 to 17 Nov 2026). Results, data quality
figures and the problems found on real data are in `RESULTS_2020_2026.md`.

An earlier version of this report said the app had only been tested on synthetic data,
because the build environment could not reach oracleselixir.com. The files were then
supplied directly and the whole pipeline, training and analytics were run on them.

## Version 1.2

Audit, evaluation upgrade and new analyses: see `AUDIT_AND_IMPROVEMENTS_v1.2.md`.

## A. Architecture

Monorepo: `frontend/` (Next.js), `backend/` (FastAPI + SQLAlchemy + Alembic),
`pipelines/` (ingestion), `machine_learning/` (Elo, features, models, evaluation,
inference), `analytics/` (economic indicators), `docs/`, `tests/`. See `architecture.md`.

## B. Frontend

Next.js 15.5 App Router, React 19, TypeScript (strict), Tailwind 3.4, Recharts 2.15,
React Query 5, Lucide. Self-hosted Inter and Space Grotesk.

- Sections: Overview, Tournaments (+ detail), Teams & Players (teams, players,
  details, team comparison, player comparison), Analytics (6 modules), Predictions,
  Global Index, Research (+ report), Data Explorer. Also Search, Methodology, Data
  sources, Documentation, 404.
- Desktop sidebar; mobile drawer (Escape closes, focus-visible styles, skip link).
- Global game selector (LoL / VALORANT / CS2) with status dots; data status panel.
- Loading, error, empty ("no data imported"), integration-pending and
  insufficient-data states on every data view; breadcrumbs on detail pages; source
  and sample period under each view; CSV download of chart aggregates.
- Checked: `tsc --noEmit` clean, `next build` succeeds (20 routes), Vitest 11/11,
  screenshots at 1440 px and 390 px (no horizontal overflow, no console errors).

## C. Backend

FastAPI with a common envelope (`data` + `meta.data_status/data_type/source/sample_period`),
Pydantic schemas and query validation, pagination, filtering, CORS restricted to
configured origins, gzip, an in-process rate limit, a TTL cache, and a generic 500
handler. 30 endpoints, listed in `api.md`.

## D. Data source and coverage

Oracle's Elixir yearly CSV files (manual download, non-commercial use, Riot Games
owns game statistics). Coverage depends on the files you import. Raw files are not
shipped. VALORANT and CS2 have no data.

## E. Cleaning and validation

Six stages with raw / intermediate / processed separation, SHA-256 manifest,
per-file inspection reports, row exclusions with reasons, game-structure validation,
duplicate detection, NULL preservation, ingestion logs in the database and an
idempotent transactional load. Verified on the synthetic fixture, including injected
defects (a duplicate row, a game missing a team row, partial games with missing
stats, a team without an id).

Needs checking on real files: column differences between years, the league codes
used for MSI and Worlds, and how often `teamid`/`playerid` are missing in older years.

## F. Statistical methodology

See `methodology.md`. Single-game unit; chronological 70/15/15 split after a 90-day
burn-in; minimum 5 earlier games; strict-timestamp features.

## G. Elo

Implemented with batching of same-timestamp games, optional season shrinkage, and a
K × shrinkage grid chosen by validation log loss. Unit tests check the formula,
zero-sum updates, same-timestamp handling and carry-over.

## H. Machine learning evaluation

Three models (Elo, calibrated Elo, logistic regression) scored on identical test
games: accuracy, precision, recall, ROC-AUC, Brier, log loss, reliability diagram,
confusion matrix, quarterly and league breakdowns, paired bootstrap intervals.
Models stay unavailable below 500 train / 200 test games.

Leakage tests: flipping all future results leaves past features unchanged; split
periods do not overlap; the inference path rebuilds exactly the training features.

Random Forest and XGBoost were not added (optional in the brief; add them only if
the logistic model's comparison against calibrated Elo justifies more complexity).

## I. Research findings

Established on 2020-2026 data (details in `RESULTS_2020_2026.md`):
- Elo with league offsets beats flat Elo (Brier 0.2176 vs 0.2230, CI excludes zero); the gain
  is concentrated in games between leagues.
- Logistic regression beats the improved Elo (0.2164 vs 0.2176, CI excludes zero), but the
  gain is a quarter of the league-offset gain and accuracy barely moves.
- Blue side wins about 53% of games in every year.
- Regular-season balance is stable 2020-2026 (median Noll-Scully about 1.64); the LCK is the
  least balanced major league.
- Win% carries over between splits with a slope of 0.42 (strong regression toward .500).
- LEC titles are the most concentrated among leagues with 10+ splits (G2 Esports 14 of 20).

## J. VALORANT and CS2

Integration pending. Adapters (Riot, GRID, PandaScore) implement authentication from
environment variables, retries with exponential backoff (429/5xx, `Retry-After`),
a client-side rate limiter and caching. No endpoint is enabled because none has been
verified with a working key. Calls return a structured `not_configured` or
`not_verified` response.

## K. Testing

| Suite | Result |
|---|---|
| pytest (unit + integration, SQLite) | 73 tests (72 passed, 1 PostgreSQL test run separately and passed) |
| PostgreSQL migration test (`TEST_POSTGRES_URL`) | passed (PostgreSQL 18) |
| `alembic check` against PostgreSQL | no differences between models and migration |
| Pipeline → train → analytics → API on PostgreSQL (synthetic) | all endpoints 200 |
| Full run on real 2020-2026 files (PostgreSQL) | pipeline 2.1 min, training 1.3 min; site checked with screenshots |
| Frontend `tsc --noEmit` | clean |
| Frontend Vitest | 11 passed |
| `next build` | success |

External APIs are mocked; no real requests are made in tests.

## L. Known limitations

- League levels are poorly identified for leagues that rarely meet the major leagues (RESULTS section 5).
- Source `year` is a season label; "2027" already appears for autumn qualifiers.
- 346 teams and 1,228 players have no source id and are keyed by name.
- Series (Bo3/Bo5) are not reconstructed; standings count games, not series.
- Tournament names, prize money and countries are not in the source; the Global
  Index therefore shows league-level analysis and no map.
- Derived champions come from the last playoff game, not an official register.
- Elo regions are linked only through international events.
- Series are approximated (same teams, tournament and UTC day) for the cluster bootstrap.
- Rate limiting and cache are per process.
- Recharts 2.x is no longer the active line; upgrading to 3.x is a small migration.

## M. Local installation

See `README.md` (Quick start) and `runbook.md`.

## N. Deployment

See `deployment.md`: Supabase/Render PostgreSQL, Render API (`render.yaml`), Vercel
frontend (`frontend/vercel.json`), GitHub Actions CI.

## O. ZIP archive

`esports-intelligence-v1.0.zip`: source, docs, tests, configs. Excludes node_modules,
`.next`, caches, virtual environments, raw data and model artifacts.

## P. Next steps

1. Done: league offsets in Elo (RESULTS section 5). Next: priors on league levels for weakly
   linked leagues, or a joint (Bradley-Terry style) estimate.
2. Series-level prediction from single-game probabilities.
3. Add roster-change features (share of last split's players still on the team).
4. Add Random Forest only if the logistic model beats calibrated Elo.
5. Apply for GRID Open Access and enable verified endpoints for VALORANT.
