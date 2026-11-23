# What does player experience capture?

Follow-up study, 23 November 2026. Record:
`machine_learning/experiments/registry/mechanisms-20261123-110321-c8b6f8e19c.json`.
Code: `machine_learning/experiments/mechanisms.py`, `player_history.py`, `harness.py`.
Reproduce: `DATA_DIR=<data> python -m machine_learning.experiments.mechanisms` (about 4 minutes on
2 CPU cores). A second full run gave a byte-identical result.

All results are predictive associations. Nothing here identifies a causal effect of experience
on winning.

## 1. Question

The published work found that one feature, the mean of log(1 + earlier professional games) over
the five players of each team's previous game (`player_exp_prev_diff`), lowers the Brier score
of the form model from 0.2164 to 0.2116 on the main test (10,087 games) and by 0.0044 pooled over
five walk-forward test years (49,748 games). This study asks what that feature stands for, and
whether a better-founded measure does the same job.

## 2. Hypotheses (fixed before running)

| | If experience mainly stands for... | then... |
|---|---|---|
| H1 | player skill | point-in-time skill measures should remove most of its gain |
| H2 | career length or recent activity | those measures should remove most of its gain |
| H3 | the cold-start problem of new teams | its gain should sit mostly in new teams, and a player-informed Elo start should capture much of it |
| H4 | nothing special about the formula | the simple mean of log games should be about as good as other transformations chosen on validation data |

Organisational resources (salaries, staff, scrims) are not in the data, so they cannot be
tested. They remain a possible explanation for part of any association below.

## 3. Information and design

**Information contract.** Every new feature describes each team's *previous* lineup and uses
only games with an earlier timestamp. This is the contract of the deployed feature: no
knowledge of today's lineup is needed. One exception is labelled: the player-informed Elo start
(H3) uses today's lineup at a team's first game, which is lineup-confirmed information.

**Settings.** The same two designs as the published work, rebuilt without re-tuning anything:
- *Main split*: train to 11 Aug 2024 (47,070 games), validation to 22 Sep 2025 (10,086), test to
  14 Nov 2026 (10,087), published Elo configuration. The rebuilt split and the rebuilt form and
  player models match the saved artifacts exactly.
- *Walk-forward*: test years 2022 to 2026, each with the Elo and player-Elo settings that the
  saved walk-forward record chose on that window's validation year.

Every model is a logistic regression on the six published features plus the listed extras. C
is chosen on validation log loss; the model is refit on train + validation and scored once on
test. Any extra setting (half-life, saturation point, Elo start weight) is chosen on validation
log loss. Intervals: paired bootstrap re-drawing whole series (2,000 draws pooled, 1,000 per
window).

**New point-in-time measures** (mean over the previous lineup's five players unless stated):

| Feature | Definition |
|---|---|
| Shrunk win rate | (wins + 10) / (games + 20): earlier win rate pulled toward 50% |
| Lane gold lead | sum of gold difference at 15 minutes against the lane opponent / (games + 20) |
| Player Elo | existing player-level Elo of the previous lineup (`player_elo.py`) |
| Previous-team Elo | current team Elo of the team each player last played for |
| Career length | log(1 + days since the player's first game in the data) |
| Recent games | log(1 + games in the last 180 days) |
| Experience vs league | experience minus the mean experience of the team's home league in the previous calendar year |

The win-rate and gold-lead measures are shrunk because many players have few games; 20 is a
fixed prior weight, not tuned.

## 4. Results

Brier differences are model minus reference: negative means the first model is better.
"Years" counts test years (of 5) in which the model was better; in brackets, how many of those
had a 95% interval below zero.

### 4.1 H1 and H2: experience against skill and participation

| Comparison | Main test (10,087) | Walk-forward (49,748) | Years |
|---|---|---|---|
| Experience over form (replication) | −0.0048 [−0.0060, −0.0035] | −0.0044 [−0.0050, −0.0039] | 5 (5) |
| Four skill measures over form | −0.0044 [−0.0055, −0.0033] | −0.0033 [−0.0038, −0.0029] | 5 (5) |
| **Experience after the four skill measures** | −0.0024 [−0.0034, −0.0014] | −0.0024 [−0.0029, −0.0020] | 5 (5) |
| Experience after career length + recent games | −0.0016 [−0.0022, −0.0009] | −0.0012 [−0.0015, −0.0009] | 5 (5) |
| Experience after skill + career + recent | −0.0004 [−0.0007, −0.0000] | −0.0003 [−0.0005, −0.0001] | 5 (1) |
| Experience alone vs four skill measures | −0.0004 [−0.0018, +0.0010] | −0.0011 [−0.0017, −0.0005] | 5 (1) |
| Player Elo over form | −0.0030 [−0.0040, −0.0020] | −0.0024 [−0.0028, −0.0021] | 5 (5) |
| Experience vs league peers, instead of plain experience | +0.0018 [+0.0011, +0.0023] | +0.0013 [+0.0011, +0.0016] | 0 |

Correlations with the experience feature on training games (main split): career length 0.85,
recent games 0.67, player Elo 0.51, shrunk win rate 0.47, team Elo difference 0.46, lane gold
lead 0.42, team experience (games as a team) 0.25.

The standardised coefficient of experience in the main-split model falls from 0.336 alone to
0.271 with the four skill measures, and to 0.212 with skill, career length and recent games.

**Reading.**
- Experience and skill overlap but are not the same. On the walk-forward games, experience alone
  gains 0.0044 and skill alone 0.0033; together they gain 0.0057. So about 0.0020 is shared,
  0.0024 is unique to experience and 0.0013 is unique to skill. **About 55% of the experience
  gain remains after controlling for four measures of player quality, in every test year.** H1
  is rejected as a full explanation: experience is not just a skill proxy.
- Experience is close to the same thing as career length (r = 0.85). Once skill, career length
  and recent games are all in the model, experience adds only 0.0003, and that remainder is
  below zero with 95% confidence in one year of five. The useful signal is therefore *how long
  and how much a player has played professionally*, measured almost any reasonable way, plus
  skill. The specific game count is not special.
- Measuring experience relative to league peers is worse in every year. Part of the feature's
  value is therefore between-league information: leagues with more experienced players beat
  leagues with less experienced ones beyond what the Elo league levels capture. This sits
  alongside the published finding that the gain also holds inside single leagues.
- The previous-team Elo measure gives nothing (−0.0000). The reason is a design limit, not a
  result about transfers: for 81% of games every player's last team is the same team, so the
  measure equals the team's own Elo (r = 0.994 with the Elo difference). It cannot test whether
  transfers carry strength. A better test needs transfer events, which the data only shows
  indirectly through team changes.

**Possible mechanisms consistent with this pattern, none identified:** survivorship (players who
last many seasons were selected for being good, and selection keeps information that one-season
statistics miss), learning by doing, and organisations with more resources hiring veterans. The
data cannot separate them.

### 4.2 H3: new teams and cold starts

Team-game categories (pooled walk-forward test games; a game is counted in a row when at least one
team fits, so rows overlap):

| Category | Definition | Games | Experience over form | Elo start over form | Experience after Elo start |
|---|---|---|---|---|---|
| New team, successor | < 20 earlier games; at its first game 3+ of 5 players had last played for one other team active in the previous 180 days | 1,167 | −0.0060 [−0.0104, −0.0012] | −0.0028 [−0.0055, −0.0001] | −0.0041 [−0.0082, +0.0003] |
| New team, experienced players | < 20 games, not a successor, first lineup averaged 50+ earlier games | 2,563 | −0.0096 [−0.0129, −0.0062] | −0.0034 [−0.0051, −0.0016] | −0.0071 [−0.0102, −0.0039] |
| New team, inexperienced players | other new teams | 4,168 | −0.0112 [−0.0139, −0.0086] | −0.0014 [−0.0026, −0.0004] | −0.0100 [−0.0126, −0.0075] |
| Returning after 90+ days | established team | 658 | +0.0018 [−0.0041, +0.0076] | −0.0008 [−0.0022, +0.0005] | +0.0020 [−0.0037, +0.0076] |
| Roster turnover | established team; today's lineup keeps at most 3 of 5 from the previous game | 1,604 | −0.0009 [−0.0047, +0.0028] | −0.0002 [−0.0010, +0.0007] | −0.0009 [−0.0046, +0.0028] |
| Both teams stable | none of the above | 40,420 | −0.0037 [−0.0043, −0.0032] | −0.0002 [−0.0004, −0.0001] | −0.0036 [−0.0041, −0.0030] |

The "successor" rule is decided by players, not by names: a rebrand with the same roster is a
successor, a new name with a new roster is not. 1,198 team-games in the test windows belong to
successor teams.

**Player-informed Elo start.** A new team's starting rating is set to
α × the mean over its first five players of (rating of the team each player last played for −
league level); players with no earlier game count as 0. α was chosen on validation from
{0.25, 0.5, 0.75, 1}; every window chose 1.0, the edge of the grid.

| Comparison (walk-forward) | Brier difference | Years |
|---|---|---|
| Elo start over form | −0.0005 [−0.0006, −0.0003] | 5 (5) |
| Experience after the Elo start | −0.0041 [−0.0046, −0.0036] | 5 (5) |
| Elo start on top of experience | −0.0001 [−0.0003, −0.0000] | 5 (0) |

**Reading.**
- Per game, experience helps most where a team is new: −0.0096 to −0.0112 against −0.0037 for
  stable games. But stable games are far more common, and **68% of the total experience gain
  comes from games between two established, stable teams**; games with a new team give 32%.
  H3 is rejected as the main mechanism: the feature is not mainly a cold-start fix.
- The player-informed Elo start works (a small gain in every year) but captures little of what
  experience does, and adds almost nothing once experience is in the model. For new teams of
  inexperienced players, it helps least, as expected: those players have no earlier team to
  inherit from.
- For teams returning after a long break and teams that just changed most of the roster, the
  previous-lineup measure gives no clear gain. This is expected: the previous lineup describes
  the team less well when the team has just changed. It is a limit of the pre-match contract,
  not a contradiction.

### 4.3 H4: how to measure experience

Each row replaces the deployed measure (mean log games) by an alternative, against the deployed
model. Settings marked "tuned" were chosen on validation in each window.

| Alternative | Walk-forward difference | Years better |
|---|---|---|
| Time-decayed games (tuned half-life; 730 days chosen every year) | −0.0001 [−0.0002, −0.0000] | 3 (2) |
| Mean plus spread across the five | −0.0001 [−0.0002, −0.0000] | 5 (2) |
| One feature per role | +0.0000 [−0.0000, +0.0001] | 2 (0) |
| Diminishing returns 1 − exp(−games/T) (tuned T) | +0.0006 [+0.0004, +0.0008] | 0 |
| Square root of games | +0.0008 [+0.0005, +0.0010] | 0 |
| Median player | +0.0009 [+0.0007, +0.0012] | 0 |
| Most experienced player | +0.0013 [+0.0009, +0.0017] | 0 |
| Least experienced player | +0.0024 [+0.0020, +0.0027] | 0 |
| Raw game count | +0.0025 [+0.0021, +0.0030] | 0 |

**Reading.** The simple measure is as good as any alternative. Two alternatives are better by
about 0.0001, an amount that does not survive correction for multiple tests
(`ROBUSTNESS_AND_SENSITIVITY.md`). The chosen half-life sat at the longest value in the grid,
which means "decay as little as possible", consistent with no decay. Averaging matters: the
weakest or strongest player alone, or raw counts dominated by a few veterans, are clearly worse.
H4 is supported.

### 4.4 A better model, found after looking

The best model in this study adds the four skill measures to the deployed model. It beats the
deployed player model on the main test by −0.0020 [−0.0028, −0.0012] (Brier 0.2096 against
0.2116; accuracy 66.4% against 65.7%) and on the walk-forward games by −0.0013 [−0.0017, −0.0010],
better in all five years.

This is an exploratory result. It was found by comparing many models on test games that had
already been used, so its size is likely optimistic. **It is not deployed.** It is listed as a
secondary hypothesis in `PREREGISTRATION_2027.md`, to be tested on games played after the data
ends.

## 5. Interpretation

Player experience is best read as *a measure of professional track record*. About half of its
predictive value overlaps with what one can learn from players' past results (win rate, lane
gold lead, player-level Elo); the other half overlaps with career length and recent activity,
and very little is left once both are included. It is not mainly a fix for new teams: most of
its gain comes from ordinary games between established teams, which suggests the team Elo
rating systematically underrates long-careered lineups and overrates short-careered ones.

## 6. Limits

- **Not causal.** Experienced players may win because they learned, because only good players
  last, or because rich organisations hire them. No variation in this data separates these.
- **Previous lineup, not today's.** All features describe the previous game's five. Where the
  roster just changed, they describe the wrong team (section 4.2).
- **Player identity.** A player who changes id in the source is counted as new. Games before
  2020 are not in the data, so veterans' counts are truncated at 2020 (career length is too).
- **Test reuse.** The walk-forward windows 2025 and 2026 overlap the main test period, and the
  experience feature itself was selected after the earlier walk-forward study. All numbers here
  are evidence about mechanisms, not a fresh confirmation of the headline gain. The confirmatory
  test is the prospective one in `PREREGISTRATION_2027.md`.
- **Many comparisons.** This study adds 21 comparisons. Section 4 marks the ones that do not
  survive a Holm correction across all 72 reported comparisons.
- **Lane gold lead** at 15 minutes is missing for some games in the source; those games are
  skipped in that average.
- **Previous-team Elo** cannot test transfers (section 4.1).
