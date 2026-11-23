# Robustness and sensitivity

Follow-up study, 23 November 2026. Record:
`machine_learning/experiments/registry/robustness-20261123-110344-c8b6f8e19c.json`.
Code: `machine_learning/experiments/robustness.py` (uses `harness.py`). Reproduce:
`DATA_DIR=<data> python -m machine_learning.experiments.robustness` (about 3 minutes).

Models in this report: `elo_cal` (logistic regression on the Elo difference), `form` (the
published six-feature model), `exp` (form + previous-lineup player experience, the deployed
player model). All are refit here with C chosen on validation, so `elo_cal` on the main test
is 0.21699 instead of the published 0.21702 (the published version is unregularised). Brier
differences are model minus reference, with 95% series-bootstrap intervals (2,000 draws).

## 1. When is each forecast made?

### The finding

Every published model, Elo included, updates after every game. For game 2 of a best-of-three,
the forecast already knows who won game 1, and the player feature already knows who played
game 1. The published forecasts are therefore **pre-game** forecasts, made between games. This
was not stated anywhere. The comparisons between models are still fair, because all models get
the same information, but "forecast the day before" was never tested.

### Three information contracts

| Contract | What the forecast may use | When it is available |
|---|---|---|
| Pre-series | the state before the series starts; each team's previous lineup | the day before |
| Pre-game (published) | every earlier game, including earlier games of the same series | between games |
| Lineup-confirmed | pre-game plus the five players who start this game | after the draft is announced |

Pre-series features for game *k* of a series are game 1's features, with the sign flipped when
the teams have swapped sides. Each contract is trained, tuned and tested on its own
information.

### Results

| Brier | Main test (10,087) | | Walk-forward (49,748) | |
|---|---|---|---|---|
| | pre-series | pre-game | pre-series | pre-game |
| Calibrated Elo | 0.21936 | 0.21699 | 0.22005 | 0.21842 |
| Form model | 0.21869 | 0.21640 | 0.21967 | 0.21805 |
| Player experience model | 0.21425 | 0.21163 | 0.21526 | 0.21364 |
| Today's lineup (lineup-confirmed) | | 0.21057 | | 0.21254 |
| Today's and previous lineup | | 0.21053 | | 0.21253 |

| Comparison | Main test | Walk-forward |
|---|---|---|
| Experience over form, pre-series | −0.00444 [−0.00574, −0.00307] | −0.00440 [−0.00499, −0.00383] |
| Experience over form, pre-game | −0.00477 [−0.00599, −0.00349] | −0.00442 [−0.00499, −0.00388] |
| Form over calibrated Elo, pre-series | −0.00066 [−0.00113, −0.00022] | −0.00038 [−0.00063, −0.00016] |
| Form over calibrated Elo, pre-game | −0.00059 [−0.00100, −0.00021] | −0.00037 [−0.00060, −0.00015] |
| Value of in-series updates, calibrated Elo | −0.00236 [−0.00312, −0.00163] | −0.00163 [−0.00191, −0.00135] |
| Value of in-series updates, experience model | −0.00262 [−0.00346, −0.00181] | −0.00163 [−0.00193, −0.00131] |
| Today's lineup instead of previous lineup | −0.00107 [−0.00161, −0.00052] | −0.00110 [−0.00134, −0.00085] |
| Today's lineup in addition to previous lineup | −0.00110 [−0.00169, −0.00051] | −0.00111 [−0.00136, −0.00084] |

Game 1 of each series is identical under both contracts. On later games only (5,552 main test;
21,966 walk-forward), in-series updates are worth −0.00433 [−0.00581, −0.00294] (Elo, main) and
−0.00350 [−0.00417, −0.00289] (Elo, walk-forward).

### Reading

- **The player-experience gain does not depend on in-series information.** It is the same size
  before the series (−0.0044) as between games (−0.0044). The deployed feature is usable the day
  before, as claimed.
- **The machine-learning gain is also unchanged** before the series (−0.0004 pooled).
- **Knowing earlier games of the same series is worth more than the machine-learning step**:
  about 0.0016 pooled, four times the form gain. Part of this is real information about the
  day (form, the draft meta, who adapted), and part is that a best-of series ends once a team
  has enough wins, so game 2 or 3 results are linked. This is not a defect, but the site and
  the paper should say "before each game" rather than "before the match".
- **Knowing today's lineup adds a further 0.0011.** That is the cost of the pre-match contract
  in the deployed model. A lineup-confirmed model is better, but only usable once lineups are
  public. The site never uses today's lineup for the deployed model.

**Caveat on the lineup-confirmed contract.** The source shows who played, not when the lineup
was announced. "Lineup-confirmed" assumes the starting five is known before the game starts,
which is true at draft time but not necessarily earlier.

## 2. How series are rebuilt

The source has no series id. The published key groups games by tournament, team pair and UTC
day. A series that runs past midnight UTC (common for North American evening games) is split
in two by that rule. The alternative tested here starts a new series when the same pair in the
same tournament has not played for 6 hours.

| Check | Value |
|---|---|
| Games | 75,830 |
| Series, published key | 45,367 |
| Series, 6-hour gap rule | 44,518 |
| Gap-rule series split across two UTC days by the published key | 861 (1.9%) |
| Published series that hold two gap-rule series | 12 |
| Games whose order inside the published series matches the source's game number | 97.9% |
| Series sizes (published key): 1 / 2 / 3 / 4 / 5 games | 27,284 / 9,284 / 6,245 / 1,527 / 1,027 |

The rule matters little for the intervals (next section). Of the 1,597 games (2.1%) whose order
does not match the source's game number, 1,255 sit in series that the published key splits at
midnight UTC, 27 in published series that hold two separate meetings on one day, and 322 in
series where the source's own numbering has gaps (for example a missing game 1).

## 3. Does the choice of bootstrap unit change the intervals?

The same two comparisons, with different resampling units. Coarser units allow for more kinds
of dependence (shared tournament conditions, shared calendar shocks) but have fewer units, so
their intervals are themselves less precise.

| Comparison | Unit | Units | Main test: SE, 95% interval | Walk-forward: SE, 95% interval |
|---|---|---|---|---|
| Experience over form | single game | 10,087 / 49,748 | 0.00064 [−0.00604, −0.00356] | 0.00027 [−0.00494, −0.00389] |
| | series (published) | 4,584 / 28,012 | 0.00064 [−0.00599, −0.00349] | 0.00028 [−0.00499, −0.00388] |
| | series (6-hour gap) | 4,494 / 27,553 | 0.00066 [−0.00602, −0.00348] | 0.00028 [−0.00497, −0.00385] |
| | tournament | 126 / 563 | 0.00079 [−0.00636, −0.00329] | 0.00036 [−0.00515, −0.00372] |
| | calendar week | 59 / 243 | 0.00074 [−0.00623, −0.00333] | 0.00033 [−0.00507, −0.00375] |
| | calendar month | 15 / 59 | 0.00104 [−0.00696, −0.00289] | 0.00044 [−0.00535, −0.00360] |
| Form over calibrated Elo | single game | | 0.00020 [−0.00099, −0.00019] | 0.00011 [−0.00060, −0.00015] |
| | series (published) | | 0.00020 [−0.00100, −0.00021] | 0.00011 [−0.00060, −0.00015] |
| | series (6-hour gap) | | 0.00021 [−0.00099, −0.00020] | 0.00012 [−0.00060, −0.00014] |
| | tournament | | 0.00025 [−0.00106, −0.00011] | 0.00014 [−0.00063, −0.00011] |
| | calendar week | | 0.00018 [−0.00095, −0.00023] | 0.00012 [−0.00061, −0.00013] |
| | calendar month | | 0.00019 [−0.00093, −0.00021] | 0.00015 [−0.00066, −0.00009] |

**Reading.** Tournament clustering widens the standard errors by about 25 to 30%. Month clusters
widen them most, but with only 15 months in the main test that interval is itself unreliable.
No unit makes either interval reach zero. The published series unit is adequate; the tournament
unit is the cautious choice and is already reported for the main comparisons.

## 4. Many comparisons

The project now reports 72 pooled comparisons: 26 in the walk-forward record (13 comparisons, Brier
and log loss), 25 subgroup comparisons in that record, and 21 in the new mechanism study. Per-window,
main-split and robustness comparisons come on top. None of them was pre-registered.

Each comparison's p-value comes from its stored 95% interval (z = difference / SE, SE = interval
width / 3.92; an approximation). Corrections across the 72:

| | Count |
|---|---|
| Nominal 95% interval excludes zero | 69 |
| Holm, family-wise 5% | 64 |
| Bonferroni, family-wise 5% | 62 |

Comparisons that lose significance under Holm: continuity over form (Brier and log loss),
player-informed Elo start on top of experience, time-decayed experience, and mean-plus-spread
experience. All are 0.0001 or smaller.

**Which results are primary.** Looking back, the study had two primary questions: does the
form model beat calibrated Elo (z ≈ −3.3 pooled), and do league levels beat flat Elo
(z ≈ −14). The player
result began as one of several roster features tested in the walk-forward study and became
primary only after it worked. Its z is about −16, so no correction changes it, but its size on
the main test is not a clean confirmatory estimate (section 6).

## 5. Time

**Expanding vs rolling training.** Training on only the last two years before validation gives
the same results as using all earlier years: form +0.00003 [−0.00001, +0.00007], experience
+0.00003 [−0.00000, +0.00007]. Older games neither help nor hurt.

**Refitting.** A model frozen with data to the end of 2021 and used unchanged for 2023 to 2026
(ratings keep updating; only the logistic coefficients are frozen) is worse than yearly refits
by 0.0002 to 0.0005 per year:

| Test year | Form: frozen − yearly | Experience: frozen − yearly |
|---|---|---|
| 2023 | +0.00021 | +0.00028 |
| 2024 | +0.00053 | +0.00050 |
| 2025 | +0.00027 | +0.00020 |
| 2026 | +0.00027 | +0.00024 |

Yearly refits help a little; the coefficients are stable.

**Calibration by test year** (logistic recalibration slope, 1 = perfect; intercept, 0 = perfect;
ECE):

| Window | Calibrated Elo: slope, intercept, ECE | Experience model: slope, intercept, ECE |
|---|---|---|
| main | 0.980, −0.029, 0.009 | 0.974, −0.029, 0.010 |
| 2022 | 1.078, −0.027, 0.013 | 1.096, −0.031, 0.014 |
| 2023 | 0.997, 0.050, 0.012 | 0.990, 0.050, 0.011 |
| 2024 | 1.077, 0.040, 0.016 | 1.071, 0.031, 0.011 |
| 2025 | 0.964, 0.073, 0.017 | 0.989, 0.068, 0.015 |
| 2026 | 0.995, −0.026, 0.010 | 1.012, −0.032, 0.012 |

Slopes stay within 0.96 to 1.10, and the experience model is as well calibrated as Elo. The
intercepts track the year-to-year blue-side win rate (about 0.05 in log odds = about 1 point of
probability), which the models estimate from the previous years.

**International games.** Experience over form on the 1,379 pooled international test games:
−0.0031 [−0.0049, −0.0013]; on 48,369 domestic games: −0.0045 [−0.0050, −0.0039]. The gain is
smaller at international events but clearly present.

Patch timing was already tested in the walk-forward record (`EXPERIMENTS.md`).

## 6. How much has the test period been used?

| Step | Used the main test period (23 Sep 2025 to 14 Nov 2026)? |
|---|---|
| Elo, form model, league levels: settings | No: chosen on validation, scored once |
| Walk-forward study (2022 to 2026 test years) | Yes: the 2026 test year and part of 2025 lie inside the main test period |
| Choice of the player-experience feature | Made after the walk-forward results |
| Player model score on the main test (0.2116) | Measured after the choice |
| This follow-up (mechanisms, robustness) | Uses all of it again |

So **there is no untouched holdout in the current data.** The published Elo vs machine-learning
comparison stays confirmatory (its settings were fixed before testing). The player-model numbers
are strong and stable across years, but they are no longer a clean out-of-sample estimate: they
are evidence from data that also guided the choice. The data ends on 17 November 2026; the 6 games after the
main test all involve a team with fewer than 5 earlier games, so none is eligible.

The remedy is a prospective test on games that do not yet exist: `PREREGISTRATION_2027.md` fixes
the models, hypotheses and analysis before the 2027 season starts.
