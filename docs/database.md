# Database

PostgreSQL, managed with Alembic (`backend/alembic/versions/0001_initial_schema.py`).
`alembic check` reports no difference between models and migrations.
All timestamps are `timestamptz` in UTC (the API connection forces `timezone=UTC`).

## Tables

| Table | Purpose | Key constraints |
|---|---|---|
| `games` | LoL, VALORANT, CS2 and their status | unique `slug` |
| `data_sources` | Oracle's Elixir, GRID, PandaScore with licence notes | unique `key` |
| `dataset_versions` | one row per imported file: hash, coverage, counts, cleaning procedure | unique (source, sha256) |
| `data_ingestion_logs` | one row per pipeline stage per run | index `run_id` |
| `tournaments` | league split; derived champion | unique (game, source_key), unique slug |
| `teams` | source team id, name, primary league, current Elo | unique (game, source_team_id) |
| `players` | source player id, name, primary position | unique (game, source_player_id) |
| `team_rosters` | observed appearances per tournament and position | unique (team, player, tournament, position) |
| `matches` | one row per game: date, sides, winner, duration, completeness | unique (game, source_match_id) |
| `team_match_statistics` | per team per game: side, result, kills, deaths, assists | unique (match, team) |
| `player_match_statistics` | per player per game | unique (match, player) |
| `lol_team_match_stats` | LoL team metrics (1:1 with team_match_statistics) | PK = FK |
| `lol_player_match_stats` | LoL player metrics (1:1) | PK = FK |
| `elo_ratings` | pre/post Elo for each team in each game | unique (model_version, match, team); index (team, date) |
| `model_versions` | elo / elo_logit / logreg: periods, hyperparameters, features, metrics, artifact | unique (game, model_key, version) |
| `model_predictions` | stored validation and test predictions | unique (model_version, match) |
| `analysis_outputs` | JSON research outputs | unique (game, key) |

All foreign keys are declared; statistics rows cascade on match deletion.
Every statistic column is nullable: `NULL` means "not recorded".

## Adding VALORANT or CS2

1. Add rows through the existing core tables (`matches` with maps as games).
2. Create `valorant_*` / `cs2_*` extension tables with their own metric definitions.
3. Write a pipeline under `pipelines/<game>/` and set the game's status to `active`.
