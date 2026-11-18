# Data sources

Checked on 18 November 2026. Re-check before relying on any of this.

## League of Legends: Oracle's Elixir (ACTIVE as historical data)

- Where: https://oracleselixir.com/tools/downloads (links to a Google Drive folder of yearly CSV files).
- Terms: data aggregated and released by Tim Sevenhuysen of OraclesElixir.com,
  provided free of charge for analysts, commentators and fans; free downloadable
  data can be used non-commercially. Game statistics are the property of Riot
  Games and their use must follow Riot's terms and policies.
- Attribution shown in the app: "Data: Oracle's Elixir (oracleselixir.com),
  Tim Sevenhuysen. Game statistics © Riot Games."
- Redistribution: raw files are not included in this repository. The pipeline
  rebuilds everything from files the user downloads. CSV export in the Data
  Explorer is limited to 5,000 rows and can be turned off (`ALLOW_CSV_EXPORT=false`).
- Structure: each `gameid` has up to 12 rows (10 players, 2 teams with
  `position = team`, participant ids 100/200). `datacompleteness` marks partial
  games (for example some regions lack detailed stats).
- Known limitations: no prize money, no country/nationality, no tournament
  name; column sets differ between years (checked per file by `inspect.py`).
- Verified on the 2020-2026 files (165 columns each, all mapped columns present, 12 rows
  per game). The `year` column is a season label, not the calendar year. See
  `RESULTS_2020_2026.md`.

## VALORANT: Riot Games Open Access / GRID (INTEGRATION PENDING)

- Riot Games Open Access powered by GRID offers official LoL and VALORANT esports
  data to students, researchers, hobbyists and early-stage developers (Central
  Data Feed, Series State API). It requires an approved account.
- The Riot Developer API (developer.riotgames.com) covers ranked player data, not
  professional esports results.
- Adapter: `backend/app/providers/grid_provider.py`, `riot_provider.py`. No
  endpoint is enabled.

## Counter-Strike 2: GRID / PandaScore (INTEGRATION PENDING)

- GRID Open Access offers CS2 and Dota 2 esports data through an API after
  account approval, with daily rate limits.
- PandaScore issues API keys with plan-dependent coverage and rate limits;
  check on the dashboard which historical and post-match data a plan includes.
- Adapter: `backend/app/providers/pandascore_provider.py`. No endpoint is enabled.

## Enabling a provider

1. Get a key and put it in `.env` (server side only).
2. Verify the endpoint, its fields and its licence against the current docs.
3. Add it to `verified_endpoints` of the adapter and write a mocked test.
4. Write a pipeline that maps it to the core tables plus a game extension table.
5. Change the game status to `active` only when real data loads.
