# Runbook: from CSV files to a working platform

## 1. Get the source files

1. Open https://oracleselixir.com/tools/downloads.
2. Follow the link to the match data folder and download the yearly files, for
   example `2024_LoL_esports_match_data_from_OraclesElixir.csv`.
3. Read the terms on that page. The data is free for non-commercial use and game
   statistics belong to Riot Games.

## 2. Load

```bash
make db
python -m pipelines.oracle_elixir.run --import path/to/2024.csv path/to/2025.csv
```

What happens:

| Stage | Module | Output |
|---|---|---|
| Acquire | `download.py` | Copy into `data/raw/oracles_elixir/` (unchanged), SHA-256 in `manifest.json` |
| Inspect | `inspect.py` | `data/reports/inspection/<file>.json`: columns, types, missing shares, row types, leagues |
| Clean | `clean.py` | `data/intermediate/oracles_elixir/clean_rows.parquet` |
| Validate | `validate.py` | game-level checks (2 team rows, Blue + Red, one winner) |
| Transform | `transform.py` | `data/processed/oracles_elixir/*.parquet` |
| Load | `load.py` | full transactional rebuild of the LoL tables |

Reports: `data/reports/data_quality_report.json` (counts retrieved, accepted,
excluded, duplicated, missing critical fields) and `data/reports/exclusions.csv`
(one line per excluded row with its reason). Each stage is also written to the
`data_ingestion_logs` table.

Running the command again with the same files gives the same database.
Adding a new yearly file and re-running rebuilds everything with all files in
`data/raw/oracles_elixir/`.

## 3. Ratings, models and research outputs

```bash
python -m machine_learning.training.train   # Elo grid, features, logistic models, evaluation
python -m analytics.run_all                  # balance, concentration, persistence, regional
```

Artifacts: `machine_learning/models/artifacts/<version>/` with
`logreg.joblib`, `elo_logit.joblib` and `evaluation.json`. The version is
`1.0.0+<hash of the source files>`, so a model is tied to the exact data.

If the data is too small (fewer than 500 train or 200 test games) the models
are stored with status `unavailable` and the site explains why.

## 4. Check

- `GET /api/v1/data-status` shows coverage and the last ingestion.
- `GET /api/v1/data-provenance` lists every file and the cleaning procedure.
- Inspect `data/reports/inspection/*.json` for `expected_columns_absent`: older
  files lack some columns; those metrics are null for those years.
- Confirm the international league codes (`MSI`, `WLDs`) in the inspection
  report's `leagues`; edit `INTERNATIONAL_LEAGUES` in
  `pipelines/oracle_elixir/config.py` if the source uses other codes.
