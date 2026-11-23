# Pre-registration: prospective test on games after 17 November 2026

Written 23 November 2026, before any game in the evaluation period was in the data. Author:
Nahian Ibnat. This file, `research/preregistration_2027/frozen_models.json` and
`machine_learning/experiments/prospective.py` are fixed from the commit that adds them. The
GitHub commit date is the public timestamp; a matching registration on OSF (free) can be added.

## Why

Every game in the current data has now been used to choose or study the models
(`ROBUSTNESS_AND_SENSITIVITY.md`, section 6). The only clean test of the player-experience
finding is on games that did not exist when the models were frozen.

## Frozen models

| Model | What it is | Artifact |
|---|---|---|
| `elo` | Elo expected score, published settings (K 40, carry-over shrink 0.5, league K 16) | computed |
| `elo_logit` | calibrated Elo | `machine_learning/models/artifacts/1.0.0+c8b6f8e19c/elo_logit.joblib` |
| `logreg` | published six-feature form model | `.../logreg.joblib` |
| `logreg_player` | form + previous-lineup player experience (deployed) | `.../logreg_player.joblib` |
| `skill_exp` | logreg_player + four player-skill measures (found in the mechanism study; exploratory) | `research/preregistration_2027/skill_exp.joblib` |

SHA-256 checksums of all five files are in `frozen_models.json`. The evaluation script stops if any
of them has changed. Elo and player-Elo ratings keep updating as new games are played (as in the
published design); model coefficients do not change.

## Evaluation games

- All games in Oracle's Elixir data with a start time after **17 November 2026 19:42:11 UTC**
  (the last game in the study data) and on or before **31 August 2027**.
- Same eligibility rule as the published test: both teams have at least 5 earlier games.
- Forecast contract: pre-game, as published (earlier games of the same series may be used).
- If fewer than **3,000** eligible games exist on 31 August 2027, the end date moves to
  **31 December 2027**, once, and the analysis is run then. No other change of dates.

## Hypotheses

| Id | Hypothesis | Supported if |
|---|---|---|
| **P1 (primary)** | `logreg_player` has a lower Brier score than `logreg` | upper end of the 95% series-bootstrap interval of the Brier difference < 0 |
| P2 | `logreg` has a lower Brier score than `elo_logit` | same rule |
| S1 (secondary, exploratory model) | `skill_exp` has a lower Brier score than `logreg_player` | same rule |

Only P1 is confirmatory for the paper's main new claim. P2 re-tests the published small
machine-learning gain. S1 tests a model that was found after looking at test data.

**Expected power** (from the standard errors already observed, assuming effects of the size seen
so far): with 3,000 games, P1 (expected −0.0044, standard error about 0.0012) has a high chance of
support; P2 (expected −0.0004, standard error about 0.0004) has roughly a 20% chance even if the
effect is real, so a null result for P2 would be weak evidence; S1 (expected about −0.0013,
standard error about 0.0007) has roughly an even chance.

## Analysis (fixed)

```
python -m machine_learning.experiments.prospective --processed <new data> --raw <new data> \
       --end 2027-08-31 --out research/preregistration_2027/result.json
```

- Brier difference, model minus reference; 95% percentile interval from 2,000 paired bootstrap
  draws re-drawing whole series (tournament, team pair, UTC day); seed 0.
- Reported alongside, not used for the decision: log loss differences; tournament-cluster
  intervals; Brier, log loss and accuracy of all five models.
- No other models, features, subgroups or periods are part of the confirmatory test. Anything else
  run on the new games is labelled exploratory.
- The result is published on the article page and in the paper whether it supports the hypotheses
  or not.

## Software check (not a result)

`prospective.py` was run with the cutoff moved back to the end of the old validation period, so
that it scored the already-published test games. It reproduced the published test Brier scores
from the frozen files exactly (elo 0.21758, elo_logit 0.21702, logreg 0.21640, logreg_player
0.21163; skill_exp 0.20962). With the real cutoff it reports no eligible games, as expected.

## What could break the test

- Oracle's Elixir changes its team or player ids: the data pipeline must map them as it does now.
  Any mapping change is documented before the analysis.
- A league is added or renamed: handled by the existing home-league rule; no manual fix.
- The source stops publishing: the test is reported as not completed.
