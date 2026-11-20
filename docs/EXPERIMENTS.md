# Experiments: walk-forward evaluation and player-information ablation

Record: `machine_learning/experiments/registry/walk-forward-20261120-143704-c8b6f8e19c.json`
(data fingerprint `c8b6f8e19c`, code checksum `5b503f5ed064`, Python 3.13, numpy 2.5.3,
pandas 3.0.5, scikit-learn 1.9.1, seed 0). Re-run with
`python -m machine_learning.experiments.walk_forward`, then
`python -m machine_learning.experiments.export_summary` to refresh the website copy.

Every number below is copied from that record. All Brier differences are model minus
reference (negative = better) with 95% intervals from a series-clustered bootstrap.

## 1. Question

The published result (one test period, Sep 2025 to Nov 2026) was: league levels help Elo a
lot, extra team features help a little. Two open questions:

1. Does that hold in other years, or was the test period unusual?
2. The source records which five players played every game. Does player information add
   what team-level Elo and form features miss?

## 2. Design (fixed before running)

- **Windows.** Test year Y = 2022, 2023, 2024, 2025, 2026. Training: eligible games before
  Y-1. Validation: year Y-1. Test: year Y. Eligible: after the 90-day burn-in and both teams
  with at least 5 earlier games (same rule as the published split). 49,748 test games in
  total; each game is in at most one test window.
- **Tuning per window, on validation log loss only.** Team Elo: the full grid
  K x carry-over x league K (264 points). Player Elo: K {24 to 64} x carry-over {0 to 0.5} x
  league K {0 to 32} (96 points). Logistic regression: C chosen on validation, then refit on
  train + validation and scored once on test.
- **Lineup timing.** "Today's lineup" features use the five who played. That lineup is
  public when the game starts (draft), usually not days before. Every player feature was
  therefore also built from each team's *previous* game ("previous lineup"), which is known
  before match day. The `prematch` model uses only those.

Models: constant blue-side rate; flat Elo; Elo with league levels; calibrated Elo; the
published logistic model ("form", 6 features); form plus one roster feature at a time; form
plus all roster features; calibrated player Elo (today's or previous lineup); `prematch`
(form + previous-lineup player experience + previous-lineup player Elo); `all` (form +
roster + today's player Elo).

New features (all from strictly earlier games; leakage tests in
`tests/unit/test_experiments.py`):

| Feature | Definition |
|---|---|
| continuity_diff | share of today's players who also played the team's previous game |
| tenure_diff | mean log(1 + earlier games for this team) over today's players |
| player_exp_diff | mean log(1 + earlier pro games, any team) over today's players |
| player_exp_prev_diff | the same for the previous game's players (pre-match) |
| player_elo_diff | league level + mean player rating of today's five (`player_elo.py`) |
| player_elo_prev_diff | the same for the previous game's five (pre-match) |

## 3. Results

### Pooled over five test years (49,748 games)

| Model | Brier | Log loss | Accuracy |
|---|---|---|---|
| Constant (blue-side rate) | 0.2491 | 0.6913 | 53.1% |
| Flat Elo | 0.2226 | 0.6357 | 63.7% |
| Elo with league levels | 0.2193 | 0.6280 | 64.4% |
| Calibrated Elo | 0.2184 | 0.6260 | 64.5% |
| Form (published logistic model) | 0.2181 | 0.6250 | 64.6% |
| **Pre-match: form + previous-lineup player data** | **0.2128** | **0.6129** | **65.6%** |
| Form + roster (today's lineup) | 0.2126 | 0.6123 | 65.7% |
| Calibrated player Elo (today's lineup) | 0.2160 | 0.6205 | 65.1% |
| Everything (today's lineup) | 0.2115 | 0.6099 | 65.8% |

### What each step adds

| Comparison | Brier change [95% CI] | Better in | CI below 0 in |
|---|---|---|---|
| League levels vs flat Elo | -0.0033 [-0.0038, -0.0028] | 5/5 years | 5/5 |
| Calibration of league Elo | -0.0009 [-0.0011, -0.0006] | 5/5 | 3/5 |
| Form features over calibrated Elo | -0.0004 [-0.0006, -0.0002] | 4/5 | 2/5 |
| Lineup continuity alone over form | -0.0001 [-0.0002, -0.0000] | 4/5 | 0/5 |
| Player tenure alone over form | -0.0007 [-0.0009, -0.0004] | 5/5 | 3/5 |
| **Player experience alone over form** | **-0.0055 [-0.0062, -0.0049]** | 5/5 | 5/5 |
| Player experience, previous lineup | -0.0044 [-0.0050, -0.0039] | 5/5 | 5/5 |
| Player Elo vs team Elo (both calibrated) | -0.0024 [-0.0031, -0.0018] | 5/5 | 4/5 |
| Player Elo, previous lineup, vs team Elo | -0.0019 [-0.0025, -0.0013] | 5/5 | 4/5 |
| **Pre-match additions over form** | **-0.0053 [-0.0059, -0.0047]** | 5/5 | 5/5 |
| Roster + player Elo over form (today's lineup) | -0.0066 [-0.0073, -0.0059] | 5/5 | 5/5 |
| Everything over calibrated Elo | -0.0069 [-0.0077, -0.0062] | 5/5 | 5/5 |

Year by year (Brier):

| Test year | Calibrated Elo | Form | Pre-match | Everything |
|---|---|---|---|---|
| 2022 | 0.2193 | 0.2188 | 0.2137 | 0.2119 |
| 2023 | 0.2217 | 0.2218 | 0.2169 | 0.2156 |
| 2024 | 0.2145 | 0.2144 | 0.2089 | 0.2082 |
| 2025 | 0.2197 | 0.2192 | 0.2141 | 0.2130 |
| 2026 | 0.2163 | 0.2155 | 0.2097 | 0.2083 |

### Early in a patch

| Games | n | Calibrated Elo | Everything | Difference [95% CI] |
|---|---|---|---|---|
| First 7 days of a patch | 11,056 | 0.2172 | 0.2091 | -0.0081 [-0.0098, -0.0065] |
| Later | 38,666 | 0.2187 | 0.2122 | -0.0066 [-0.0074, -0.0058] |

The intervals overlap, so there is no clear evidence that player information helps more
early in a patch.

## 4. Findings

1. **The published finding replicates.** In every year, league levels are the biggest gain
   over flat Elo and the six form features add very little over calibrated Elo
   (-0.0004 pooled; clearly below zero in only 2 of 5 years).
2. **Player information is the largest gain found so far, and it is stable.** Adding
   player experience lowers Brier by about 0.005, more than ten times the form features,
   in all five years with intervals below zero each year. Most of it (about 80%) survives
   when only the previous game's lineup is used, so it is usable before match day.
3. **One simple feature does most of the work.** Player experience alone matches all
   roster features together; continuity and tenure add little. Player-level Elo adds a
   further, smaller gain on top.
4. **Accuracy moves less than Brier.** The pre-match model is right 65.6% of the time vs
   64.6% for the published model; most of the gain is in better-calibrated probabilities.

## 5. Interpretation and open questions

- *Why does experience help?* Two readings, not yet separated: (a) experienced players are
  better and Elo is slow to see that when a team is new or rebuilt; (b) experience is a proxy
  for league tier that the league levels measure poorly (see the LFL vs LPL issue in
  `PROJECT_AUDIT.md`). Next test: the same comparison inside the best-linked leagues only
  (LCK, LPL, LEC, LCS) and for teams with fewer than 20 earlier games.
- Player ratings share outcomes (five players, one result), so player Elo is a way for a
  rating to follow players, not a measure of individual skill.
- Tuning picks K = 40 and carry-over 0.1 for player Elo in every window; both are inside the
  grid.
- Not tested yet: Glicko-2 / TrueSkill (rating uncertainty for new teams), champion-level
  experience, patch identity as a feature.

## 6. What changed and what did not

- The published model, its artifact and the prediction lab are unchanged. These experiments
  are a separate, documented study.
- New code: `machine_learning/experiments/` (`lineups.py`, `player_elo.py`, `registry.py`,
  `walk_forward.py`, `export_summary.py`). New tests: `tests/unit/test_experiments.py`.
- New page: `/experiments` reads `frontend/public/experiments/walk-forward.json`, exported
  from the registry record above.
- Proposed next step (needs a decision): retrain the deployed model with the pre-match player
  features, so the prediction lab uses them. That changes the public model and its numbers,
  so it should be a new model version with its own record.
