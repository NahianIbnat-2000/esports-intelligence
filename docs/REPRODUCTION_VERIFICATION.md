# Reproduction verification

23 November 2026. Every published number was rebuilt from the raw source files, in a clean
folder where possible, and compared with the published value.

## 1. Environment

| Item | Value |
|---|---|
| OS | Linux, 2 CPU cores, 7 GB memory |
| Python | 3.13.18 |
| numpy / pandas / scikit-learn / scipy | 2.5.3 / 3.0.5 / 1.9.1 / 1.18.1 |
| Code | branch `research/v2.1` from master `3152946` |

The published artifacts were produced on another machine. Float results agree to about 1e-16
(the last digit of a few coefficients in `evaluation_logreg_player.json`); no printed number
changes.

## 2. Source files

The data is Oracle's Elixir match data (CSV per year), downloaded manually; it is not
redistributed here. The seven files used (2020 to 2026, downloaded 18 November 2026) have the
SHA-256 values listed in `research/release_manifest.json` and in every registry record.

**All 7 files match** the recorded checksums (data fingerprint `c8b6f8e19c`).

**Important:** Oracle's Elixir adds games to the current-year file every day. A 2026 file downloaded
after 18 November 2026 will not match, and results will differ slightly. To reproduce exactly you
need the same file versions; the checksums tell you whether you have them.

## 3. Commands

```bash
pip install -r requirements-dev.txt
export DATA_DIR=/path/to/data          # with raw/oracles_elixir/*.csv and manifest.json
python -m pipelines.oracle_elixir.run --no-load       # processed tables, no database needed
python -m machine_learning.training.player_model --no-db   # needs models/artifacts (in the repo)
python -m machine_learning.experiments.walk_forward
make research                                          # mechanisms, robustness, leagues, coefficients
make verify                                            # numbers on every surface vs artifacts
python -m pytest
```

## 4. Results

| Check | Published | Rebuilt | Match |
|---|---|---|---|
| Rows read / excluded / accepted | 910,140 / 204 / 909,936 | same | exact |
| Games valid / excluded | 75,830 / 15 | same | exact |
| Processed tables (8 parquet files, all rows and columns) | | identical | exact |
| Data quality report and exclusions list | | identical (except run time stamps) | exact |
| Split train / validation / test | 47,070 / 10,086 / 10,087 | same | exact |
| Test Brier: baseline, Elo, calibrated Elo, logistic, player model | 0.2488, 0.2176, 0.2170, 0.2164, 0.2116 | 0.24882, 0.21758, 0.21702, 0.21640, 0.21163 | exact |
| Player model: log loss, accuracy, AUC, C | 0.6104, 65.7%, 0.721, 10 | 0.61037, 65.75%, 0.72098, 10 | exact |
| Player vs logistic, Brier [95% CI] | −0.0048 [−0.0060, −0.0035] | −0.004771 [−0.005989, −0.003491] | exact (same seed) |
| Predictions from the committed model files | | equal to the published test predictions | exact |
| Coefficient table (paper Table 4) | intervals from an unsaved run | rebuilt; 3 interval ends and one count changed by one unit in the last digit | **fixed in the paper** |
| Walk-forward record (full rerun, 264 Elo + 96 player-Elo replays) | `walk-forward-20261120-154137` | identical | exact |
| Mechanism study, run twice | | byte-identical records | exact |

## 5. Walk-forward rerun

The complete walk-forward study was rerun from scratch: all 264 team-Elo replays, all 96
player-Elo replays, every window's choice of settings, 14 models per window, the pooled
comparisons, the patch analysis and the subgroups (about 15 minutes on 2 cores). Every value in
the new record equals the published record (largest difference: 0; tolerance 1e-12). Fields
that describe the run itself (time, code checksum, package versions) were excluded from the
comparison.

## 6. Automatic checks

`research/claims.json` lists 31 headline numbers (counts, Brier scores, accuracy, differences,
coefficients), each with the artifact path that produced it and the files where it appears
(README, article, paper, `EXPERIMENTS.md`, `RESULTS_2020_2026.md`). `make verify` formats each
artifact value and checks it is present in every listed file. The test suite runs the same check,
so a number changed in an artifact but not in the text (or the reverse) fails CI.

`research/release_manifest.json` links the data checksums, model version, evaluation periods,
artifact checksums, every experiment record, the paper (PDF and LaTeX) and the website version.
The tests fail if any checked file changes without the manifest being regenerated
(`make manifest`).

Current state: 31/31 claims ok, all manifest checksums ok.

## 7. What cannot be reproduced exactly

- Results that depend on the 2026 source file, with a later download (section 2).
- Bootstrap intervals with a different seed or number of draws (all records store both).
- The website snapshot, which is built from the live database at a point in time.
