# Audit and improvements, version 1.2 (18 November 2026)

> Historical record, kept as written. Current status of every issue: [`ISSUE_STATUS.md`](ISSUE_STATUS.md) (23 November 2026).

Data: Oracle's Elixir 2020-2026 (75,830 games). Model version `1.0.0+c8b6f8e19c`.
All numbers below come from `evaluation.json`, the `analysis_outputs` table and the
data quality report of this run.

## 1. Audit findings (before changes)

| Area | Finding | Status |
|---|---|---|
| Overview figures | All KPIs come from database queries; 75,830 games = 75,830 distinct game ids | Correct, kept |
| Splits and leakage | Chronological train/validation/test; features use earlier games only (tested) | Correct, kept |
| Model comparison | Paired series-cluster bootstrap on identical test games | Correct, extended |
| Baselines | Only a 0.25 "coin flip" line in text; no prevalence model scored | Missing, added |
| Metrics | No F1, no calibration error; ROC and confusion computed but not shown | Incomplete, added |
| Prediction output | No explanation (contributions, head-to-head, side effect) | Missing, added |
| Historical predictions | No model version, no filters | Incomplete, added |
| Clustering | Only series-level checked | Extended (tournament-level sensitivity) |
| Data quality | Partial games (9.6%), unmatched ids (346 teams, 1,228 players), 20.6% games without split name not visible | Missing, added |
| Elo documentation | Deviations from the standard formula only in code | Added to Overview and docs |
| Competitive balance | HHI/Gini computed but not shown; Lorenz never plotted; no league/season comparison | Incomplete, added |
| Data Explorer | No season/tournament/team/player/role filters | Added |
| Research 3 | Was "persistence" only | Replaced by "Evolution of team performance" |
| Tree models | Not tested | Tested on validation only; not deployed (section 4) |

## 2. What changed

Backend
- `machine_learning/evaluation/metrics.py`: F1, expected calibration error (10 bins), probability
  histogram; ROC-AUC reported as null for constant predictions; cluster bootstrap reports its unit
  and number of units.
- `machine_learning/training/train.py`: two prevalence baselines scored on the test set
  (constant 50%; constant blue-side rate from earlier data); comparisons against them;
  tournament-clustered sensitivity; validation-only tree experiment; feature means stored.
- `backend/app/services/predictions.py`: prediction explanation (logistic contributions that add
  up to the logit, Elo difference, last-10 form, head-to-head before the date, side effect);
  `/predictions/history` with filters, model versions and monthly Brier scores.
- `backend/app/services/overview.py`: data coverage, data quality, Elo method, research highlight
  with best model by Brier, accuracy and F1; `/data-quality` report.
- `analytics/run_all.py`: HHI/Gini/Noll-Scully by league and season, Lorenz curve of wins per
  split, regular-season rank of champions, team consistency, season trends.
- `backend/app/services/explorer.py`: filters by season, tournament, team, player and role.
- Player metrics: kill participation added; season-by-role medians.
- Research reports: baselines, clustering sensitivity, statistical vs practical significance,
  report 3 rewritten.

Frontend
- Overview: coverage charts, data quality panel, Elo methodology panel with formulas and
  deviations, research card with best-by-Brier/accuracy/F1.
- Predictions: metrics table with baselines/ECE/F1, calibration, ROC, confusion matrices,
  probability distribution, by quarter, by region, features, tree experiment, uncertainty table,
  prediction explanation, filterable historical predictions.
- Analytics: league-season balance comparison, Lorenz curves, placements, Elo trajectories,
  consistency, kill participation, season-by-role trends, season trends.
- New Data quality report page; Data provenance page with cleaning rules and download dates;
  Data Explorer filters.

## 3. Actual model performance (test: 23 Sep 2025 to 14 Nov 2026, 10,087 games)

| Model | Brier | Log loss | ECE | ROC-AUC | Accuracy | F1 |
|---|---|---|---|---|---|---|
| Constant 50% | 0.2500 | 0.6931 | 0.0350 | n/a | 53.5% | 0.697 |
| Constant blue-side rate (52.8%) | 0.2488 | 0.6908 | 0.0068 | n/a | 53.5% | 0.697 |
| Elo with league offsets | 0.2176 | 0.6249 | 0.0224 | 0.705 | 64.7% | 0.670 |
| Calibrated Elo | 0.2170 | 0.6232 | 0.0123 | 0.705 | 64.8% | 0.691 |
| Logistic regression | 0.2164 | 0.6215 | 0.0094 | 0.707 | 64.9% | 0.691 |

The constant baselines have the highest F1, because predicting "blue wins" every game gives 100%
recall. This is why F1 and accuracy are not used to rank probabilistic models here.

Brier differences, paired bootstrap, 2,000 resamples:

| Comparison | Difference | 95% CI | Unit (n) |
|---|---|---|---|
| Elo vs prevalence baseline | -0.03124 | -0.03490 to -0.02755 | series (4,584) |
| Elo with offsets vs flat Elo | -0.00543 | -0.00675 to -0.00406 | series (4,584) |
| Calibrated Elo vs Elo | -0.00056 | -0.00110 to +0.00003 | series (4,584) |
| Logistic vs Elo | -0.00118 | -0.00188 to -0.00047 | series (4,584) |
| Logistic vs calibrated Elo | -0.00062 | -0.00104 to -0.00023 | series (4,584) |
| Logistic vs calibrated Elo | -0.00062 | -0.00106 to -0.00017 | tournament (126) |
| Logistic vs Elo | -0.00118 | -0.00189 to -0.00046 | single game (10,087) |

Reading: the logistic model's gain over calibrated Elo is statistically clear (also with
tournament clustering) but practically small: 0.29% of the calibrated Elo Brier score.
Calibrated Elo vs raw Elo is not distinguishable on Brier (interval includes zero), although its
calibration error is lower. The league-offset change to Elo is the largest real improvement.

Tree models (validation only, fit on training data): gradient boosting Brier difference vs
logistic +0.00004 (CI -0.00035 to +0.00043); random forest +0.00075 (CI +0.00025 to +0.00128).
Neither beats logistic regression, so neither was added.

## 4. Economics findings

- Regular-season balance: median Noll-Scully 1.64 across 654 splits; Gini of wins 0.258;
  normalised HHI of win shares 0.028 (small by construction in round robins).
- The best regular-season team won the derived title in 52% of 408 splits.
- Persistence: slope 0.42 of next-split win% on current win%.
- Spread of team win% (90th minus 10th percentile): 0.404 in 2020, 0.354 in 2026.

## 5. Data quality findings

910,140 rows read; 0 exact or conflicting duplicate rows; 15 games excluded (12 with the same
team on both sides, 2 without exactly one winner, 1 with a missing team row); 204 rows excluded
in total; 7,313 partial games (9.6%); 9.4% of team games without 15-minute stats; 346 teams and
1,228 players without source id; 15,586 games (20.6%) without a split name.

## 6. Tests

91 Python tests (90 run on SQLite plus the PostgreSQL migration test) and 11 frontend tests pass.
New tests cover F1/ECE/histograms, constant-prediction AUC, cluster bootstrap (identical models
give zero; clustered errors widen intervals), baselines through the API, explanation
contributions adding up to the logit, history containing only out-of-sample predictions, and
Data Explorer filters. Pages were checked in a headless browser on the real data, including a
full prediction request through the form; no console errors.

## 7. Unresolved limitations

- Series and tournament names are not in the source; series are approximated.
- League levels for leagues that rarely meet the major leagues are poorly identified.
- Models are fixed at the start of the test period (no rolling refit).
- One test period: results are one realisation of the future.
- Derived titles, not official ones; prize money and countries unavailable.
- Remaining npm advisories are in build/test tools with no patched version (runtime: 0).

## 8. Version 1.3: match-centre design (18 November 2026)

- New look across the site: top navigation with dropdown groups and a second row of sub-pages,
  near-black panels, red interface accent, gold and green as the two-team colour pair.
  Colours are tokens in `tailwind.config.ts` and `lib/chart-theme.ts`.
- New `/matches` (list) and `/matches/[id]` (match centre) pages, backed by
  `GET /api/v1/matches/{id}`: Elo before/after, stored out-of-sample predictions (validation and
  test games only; Elo expectation otherwise), Elo over the last 20 games, approximate series
  (same teams and tournament, games under 3 hours apart), last 10 results before the game,
  scoreboards, team stat comparison, objectives and firsts.
- "Top performer" uses a stated rule (winning-team player with the highest KDA, ties by damage
  share) and compares with the same role's median in the tournament. It is not an official MVP.
- Not reproducible from the source and therefore left out: round history, in-game win
  probability timelines, kill maps, player photos, team logos and venue images. Crests are
  generated from team initials; all artwork is original.
