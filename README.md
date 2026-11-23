# Esports Intelligence

**Beyond the Game. Inside the Data.**

**Live site:** [esports-intelligence.vercel.app](https://esports-intelligence.vercel.app) ·
**Article:** [Does machine learning beat Elo? And what actually does?](https://nahianibnat-2000.github.io/esports-intelligence/) ·
**Five-year results:** [Experiments](https://esports-intelligence.vercel.app/experiments) ·
**Try a prediction:** [Prediction lab](https://esports-intelligence.vercel.app/predictions) ·
**Case study (PDF):** [docs/case-study](docs/case-study/Esports_Intelligence_Case_Study_Nahian_Ibnat.pdf) ·
**New to the terms?** [FAQ and glossary](https://esports-intelligence.vercel.app/faq)

> The live API runs on a free server that sleeps when unused. Most pages load instantly from a
> saved snapshot; if a page says the server is waking up, wait up to a minute.

![Match centre](docs/screenshots/match-centre.png)

| Overview | Prediction lab |
|---|---|
| ![Overview](docs/screenshots/overview.png) | ![Predictions](docs/screenshots/predictions.png) |

A research-driven esports analytics platform built on 75,830 professional
League of Legends games (2020 to November 2026) from the public historical files of
[Oracle's Elixir](https://oracleselixir.com/tools/downloads). VALORANT and
Counter-Strike 2 have provider adapters but no verified data integration yet, and
the site says so instead of showing empty or invented numbers.

Central research question: *can machine learning predict professional League of
Legends game outcomes better than an Elo benchmark?*

## Key findings

Test period 23 Sep 2025 to 14 Nov 2026 (10,087 games), never used for fitting or tuning.

| Model | Brier (lower is better) | Accuracy |
|---|---|---|
| Constant blue-side win rate (baseline) | 0.2488 | 53.5% |
| Elo with league offsets | 0.2176 | 64.7% |
| Calibrated Elo | 0.2170 | 64.8% |
| Logistic regression (pre-game features) | 0.2164 | 64.9% |

- Logistic regression beats calibrated Elo: Brier difference -0.00062, 95% CI -0.00104 to
  -0.00023 (paired bootstrap over series; also holds with tournament clusters). The gain is
  statistically clear but small in practice: about 0.3% of the Brier score.
- The largest real improvement came from the rating design, not from machine learning:
  giving Elo separate league levels lowered the Brier score by 0.0054 against flat Elo.
- Tree models (gradient boosting, random forest) did not beat logistic regression on the
  validation period and were not deployed.

Full results: `docs/RESULTS_2020_2026.md` and `docs/AUDIT_AND_IMPROVEMENTS_v1.2.md`.

### Walk-forward check and player information (Nov 2026)

The same comparison repeated for five test years (2022 to 2026, 49,748 games), with models
re-tuned and refit for each year (`docs/EXPERIMENTS.md`, page `/experiments`):

- The finding above holds every year: league levels are the largest gain over flat Elo, and
  the six form features add little over calibrated Elo (-0.0004 Brier pooled).
- Player information adds far more. Using only the players from each team's previous game
  (no knowledge of today's lineup needed), the Brier score falls a further 0.0053 [95% CI -0.0059 to
  -0.0047] over the form model, better in all five years. One feature, the average number
  of earlier pro games of the players, does most of the work.
- The prediction lab now includes this as a fourth model (logistic + player experience of
  each team's previous lineup). On the original test period: Brier 0.2116 vs 0.2164, a
  difference of -0.0048 [95% CI -0.0060 to -0.0035]; accuracy 65.7% vs 64.9%.
- **Timing.** All models update after every game, so in a best-of series the forecast for game 2
  already knows game 1. With every input frozen before the series starts, the experience gain is
  the same (-0.0044 pooled), so the player feature is usable the day before.

### What player experience captures, and a pre-registered test (Nov 2026)

- About **55%** of the experience gain remains after adding four point-in-time measures of player
  skill (shrunk win rate, lane gold lead at 15 minutes, player Elo, rating of previous teams), in
  every test year. Most of the rest overlaps with career length and recent activity: the signal
  is the players' professional track record, not the exact game count.
- It is **not mainly a new-team fix**: 68% of the gain comes from games between established,
  stable teams.
- These are associations. Skill, survival in the pro scene and team resources cannot be separated
  in this data.
- Every game in the data has now been used to choose or study the models, so the models are
  frozen and a **prospective test on games after 17 November 2026** is pre-registered
  ([plan](docs/PREREGISTRATION_2027.md)). Results will be published whether or not they support
  the finding.
- Reports: [mechanisms](docs/PLAYER_EXPERIENCE_MECHANISMS.md) ·
  [robustness](docs/ROBUSTNESS_AND_SENSITIVITY.md) ·
  [league uncertainty](docs/LEAGUE_RATING_UNCERTAINTY.md) ·
  [reproduction](docs/REPRODUCTION_VERIFICATION.md) · [audit](docs/AUDIT_2026_11_FOLLOWUP.md)

## Related work

This project is not the first to compare ratings and machine learning for professional
League of Legends.

- **Riot Games and AWS, [LoL Esports Global Power Rankings](https://lolesports.com/en-GB/news/dev-diary-unveiling-the-global-power-rankings) (2024).**
  A blended rating of team Elo and league Elo (80/20), where international events move the
  league Elo. Riot reports about 65% predictive accuracy. The league-offset Elo here follows
  the same idea; its 64.7% test accuracy is on different games, so the figures are not
  directly comparable.
- **Jadowski and Cunningham, [Statistical models for predicting results in professional League of Legends](https://e-space.mmu.ac.uk/629272) (2022).**
  Models built on 2020 international competitions; best model correct on 67% of 306 games.
- **[SBGames 2021 short paper](https://www.sbgames.org/proceedings2021/ComputacaoShort/217082.pdf)
  (Federal University of Paraíba).** Several classification algorithms trained on the
  Oracle's Elixir dataset, the same source used here.
- **De Bois et al., [PandaSkill](https://arxiv.org/abs/2501.10049) (2025).** Player ratings
  built from in-game statistics with machine learning, plus regional meta-ratings; reports
  better outcome prediction than Elo and TrueSkill over five years of pro matches.
- **Do et al., [Using Machine Learning to Predict Game Outcomes Based on Player-Champion Experience](https://arxiv.org/abs/2108.02799) (2021).**
  Outcome prediction from player-champion experience in ranked (non-professional) games.

**What this project adds.** The contribution is in the evaluation rather than a new model:
a date-based split with a test period never used for fitting or tuning, constant baselines,
series-clustered bootstrap intervals, and a separation between statistical and practical
significance. Under these checks, machine learning on pre-game features adds little once
league structure is in the rating. This is consistent with PandaSkill, whose gains come
from player-level in-game data that these ratings do not use. Data processing, code and the
data quality report are public, so the test can be rerun.

## What the platform shows

- **Overview:** data coverage, data quality indicators, Elo methodology, model comparison
  against baselines.
- **Match centre:** every game with Elo change, pre-game probabilities, series, recent form,
  scoreboards, team stats and objectives.
- **Prediction lab:** five models scored on the same test games, calibration, ROC, confusion
  matrices, probability distributions, bootstrap intervals, explained predictions and
  historical predictions.
- **Statistics:** competitive balance (HHI, Gini, Lorenz, Noll-Scully) by league and season,
  champion placements, Elo trajectories, consistency, player metrics by role and season.
- **Research and data:** three research reports, data quality report, data provenance and a
  Data Explorer with CSV downloads.

## Hosting

Hybrid: the default views of every page are pre-computed into a static snapshot served by the
website host, so they load instantly at any time; other requests go to the live API, which is
kept awake by a free uptime monitor. See `docs/deployment.md`.

## What is in the box

| Part | Folder | Stack |
|---|---|---|
| Web app | `frontend/` | Next.js 15 (App Router), React 19, TypeScript, Tailwind, Recharts, React Query |
| API | `backend/app/` | FastAPI, Pydantic, SQLAlchemy 2, Alembic |
| Database | `backend/alembic/` | PostgreSQL (SQLite works for tests) |
| Ingestion pipeline | `pipelines/oracle_elixir/` | pandas: acquire, inspect, clean, validate, transform, load |
| Ratings and models | `machine_learning/` | Elo with league offsets, calibrated Elo, logistic regression (scikit-learn), evaluation |
| Economics / statistics | `analytics/` | HHI, Gini, Lorenz, Noll-Scully, persistence, upset rate |
| Research reports | `backend/app/services/research.py` | Generated from computed outputs |
| Provider adapters | `backend/app/providers/` | Riot, GRID, PandaScore (pending) |
| Tests | `tests/`, `frontend/tests/` | pytest, Vitest + Testing Library |
| Docs | `docs/` | Architecture, database, API, methodology, deployment, reports |

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

With Docker: put the CSV files in `./data/raw/oracles_elixir/`, then run
`docker compose build`,
`docker compose run --rm api make all FILES="/app/data/raw/oracles_elixir/*.csv"`
and `docker compose up`. On Git Bash for Windows, prefix the `run` command with
`MSYS_NO_PATHCONV=1`.

Use at least two seasons. Models need 500 training games and 200 test games
after the burn-in, or they stay switched off with an explanation.

## Data integrity rules (enforced in code)

- Only values computed from imported records are shown. Missing values are
  `null` and display as "n/a" or "Unavailable", never as 0.
- One match = one game. Player rows are never counted as games.
- Train, validation and test periods are split by date, never at random; features use
  only games before each prediction.
- Every excluded row has a written reason (`data/reports/exclusions.csv`).
- Every API response carries `data_status`, `data_type`, source and sample period.
- Predictions are refused for dates inside the training/validation period and
  for teams with fewer than 5 earlier games.
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
Not affiliated with Riot Games.

## Documentation

`docs/runbook.md`, `docs/architecture.md`, `docs/database.md`, `docs/api.md`,
`docs/data_sources.md`, `docs/data_dictionary.md`, `docs/methodology.md`,
`docs/RESULTS_2020_2026.md`, `docs/AUDIT_AND_IMPROVEMENTS_v1.2.md`,
`docs/deployment.md`, `docs/DEVELOPMENT_REPORT.md`.

Follow-up research (Nov 2026): `docs/PLAYER_EXPERIENCE_MECHANISMS.md`,
`docs/ROBUSTNESS_AND_SENSITIVITY.md`, `docs/LEAGUE_RATING_UNCERTAINTY.md`,
`docs/PREREGISTRATION_2027.md`, `docs/REPRODUCTION_VERIFICATION.md`,
`docs/AUDIT_2026_11_FOLLOWUP.md`, `docs/ISSUE_STATUS.md`. Every headline number is checked
against its artifact by `make verify` (`research/claims.json`).

## Author

Nahian Ibnat

## Acknowledgements

- Data: [Oracle's Elixir](https://oracleselixir.com) by Tim Sevenhuysen. Game statistics are
  the property of Riot Games. This project is not affiliated with or endorsed by Riot Games.
- Much of the code and documentation was written with the help of
  [Claude](https://www.anthropic.com/claude) (Anthropic), an AI assistant. The research
  question, methods, data integrity rules and final decisions are my own, and I reviewed
  and tested the results.
