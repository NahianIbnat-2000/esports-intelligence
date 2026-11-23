# Development report: research follow-up (version 2.1), 23 November 2026

Branch `research/v2.1`. Nothing was deployed; no database, model artifact or published record
was overwritten. The published models are unchanged.

## 1. What was done

| Area | Change | Files |
|---|---|---|
| Audit | Classified findings with evidence, ranked plan, current issue status | `docs/AUDIT_2026_11_FOLLOWUP.md`, `docs/ISSUE_STATUS.md` |
| Research: player experience | Hypotheses H1 to H4, 21 comparisons, main split + five-year walk-forward | `docs/PLAYER_EXPERIENCE_MECHANISMS.md`, `machine_learning/experiments/{mechanisms,player_history,harness}.py` |
| Research: robustness | Forecast-timing contracts, series rebuild, bootstrap units, multiple testing, temporal checks | `docs/ROBUSTNESS_AND_SENSITIVITY.md`, `robustness.py` |
| Research: leagues | Connectivity network by year, league strength with intervals, Elo-level sensitivity | `docs/LEAGUE_RATING_UNCERTAINTY.md`, `league_uncertainty.py` |
| Pre-registration | Frozen models (with checksums) and an evaluation script fixed before 2027 games exist | `docs/PREREGISTRATION_2027.md`, `research/preregistration_2027/`, `prospective.py`, `preregister.py` |
| Reproducibility | Table 4 rebuilt; claims registry (31 claims) and checker; release manifest | `coefficients.py`, `research/claims.json`, `verify_claims.py`, `manifest.py`, `research/release_manifest.json` |
| Paper | Table 4 intervals and "82 earlier games" corrected to reproducible values; PDF rebuilt (15 pages) | `docs/case-study/*` |
| Tests | 12 new tests (point-in-time features, Elo start, timing helpers, Holm, claims, manifest, frozen files) | `tests/unit/test_followup_studies.py` |
| Tooling | `make research`, `make verify`, `make manifest` | `Makefile` |
| Records | 4 new registry records | `machine_learning/experiments/registry/*-20261123-*` |

## 2. Main findings

1. **Player experience is a measure of professional track record.** About 55% of its gain
   remains after four point-in-time skill measures (win rate, lane gold lead, player Elo,
   previous-team Elo), in every test year. Most of the rest overlaps with career length and recent
   activity. The exact formula does not matter much; the simple mean of log games is as good as
   any alternative tried.
2. **It is not mainly a new-team fix.** 68% of the gain comes from games between established,
   stable teams. A player-informed Elo start for new teams helps a little (−0.0005) and adds
   almost nothing once experience is in the model.
3. **Forecasts are pre-game, not pre-match.** All models update between games of a series. The
   player gain is unchanged when inputs are frozen before the series (−0.0044); knowing earlier
   games of the same series is worth about 0.0016, more than the machine-learning step.
4. **Uncertainty handling holds up.** Tournament-level clustering widens standard errors by
   25 to 30% and changes no conclusion; 64 of 69 nominally significant comparisons survive Holm.
5. **League strengths are precise only at the top.** LCK and LPL intervals are about 50 points
   wide; most other leagues 160 to 310. In 2020 the European regional leagues had no link to the
   major leagues, which explains the old LFL anomaly.
6. **A better model exists but is not deployed:** adding the skill measures beats the deployed
   player model by 0.0013 to 0.0020, found after looking at test data. It is frozen and listed as
   a secondary hypothesis for the prospective test.
7. **Everything published reproduces**, from raw files to processed tables to model scores
   (`REPRODUCTION_VERIFICATION.md`), except Table 4, which is now fixed.

## 3. Testing report

| Command | Result |
|---|---|
| `python -m pytest` | 116 passed, 1 skipped (Postgres migration test; needs `TEST_POSTGRES_URL`) |
| `python -m machine_learning.experiments.verify_claims` | 31/31 claims ok; all manifest checksums ok |
| `python -m pipelines.oracle_elixir.run --no-load` (clean folder, raw files only) | processed tables identical to the study data |
| `python -m machine_learning.experiments.mechanisms` run twice | byte-identical results |
| `python -m machine_learning.experiments.prospective --cutoff <validation end>` (dry run) | published test Brier scores reproduced from frozen files |
| `python -m machine_learning.experiments.walk_forward` full rerun | every value equal to the published record |
| Frontend (`npm run typecheck`, `npm test`, `npm run build`) | not run: no frontend file changed |

Remaining failures: none. Not tested: live site and API (not reachable from this session),
keyboard and screen-reader behaviour, browser journeys.

## 4. Unresolved limitations

- No clean holdout until 2027 games are played; the player-model numbers are strong but come
  from data that also guided the choice.
- The experience association is not causal; skill, survival and team resources cannot be
  separated with this data.
- The previous-lineup contract misses roster changes made since the last game.
- Exact reproduction needs the 18 November 2026 source files (the 2026 file keeps changing).
- Site changes listed in the audit (§8, ranks 9 to 12) are not started.

## 5. What you need to do

1. Review the new reports. If you agree with them, approve the wording changes in
   `AUDIT_2026_11_FOLLOWUP.md` §9; I can then update the paper, article, README and site text.
2. **Push the branch soon**, at least the pre-registration files, so the GitHub timestamp is
   before new games enter the data. Optional: register the same plan on OSF (free).
3. After pushing, merging into master is safe: no deployed file changes behaviour (the frontend
   and API code are unchanged).

## 6. Next research opportunities

- Run the prospective test after 31 August 2027.
- Transfer events: follow players across teams directly, to test whether strength moves with
  players (the previous-team Elo measure could not).
- A point-in-time hierarchical league rating, compared with league Elo on the same games, for
  weakly linked leagues only.
- A lineup-confirmed product mode: once lineups are announced, today's lineup adds 0.0011.
