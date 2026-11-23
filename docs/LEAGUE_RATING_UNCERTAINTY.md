# League connectivity and league-rating uncertainty

Follow-up study, 23 November 2026. Record:
`machine_learning/experiments/registry/league-uncertainty-20261123-110629-c8b6f8e19c.json`.
Code: `machine_learning/experiments/league_uncertainty.py`. Reproduce:
`DATA_DIR=<data> python -m machine_learning.experiments.league_uncertainty` (about 2 minutes;
run `mechanisms` first for section 4).

## 1. Why this matters

The Elo model gives each league a level, and a league's level moves only when its teams play
teams from other leagues. A league whose teams rarely meet outsiders has a level that rests on
few games, or only on games against other weakly linked leagues. The earlier audit found one
symptom: the French league (LFL) sat above LPL in the raw level table. This study measures how
well each league is linked, puts intervals on league strength, and checks whether weak links
hurt forecasts.

**Home league** follows the Elo replay: the league a team has played most domestic games in, using
earlier games only. A side effect: a few teams whose only games are in a domestic cup get that
cup as their "league" (for example KeSPA Cup, EM). These rows are kept and flagged.

## 2. The network of cross-league games

Nodes are home leagues; two leagues are linked when their teams met in that period.

| Year | Leagues | Links | Cross-league games | Separate groups | Largest group | Leagues with no link |
|---|---|---|---|---|---|---|
| 2020 | 46 | 111 | 860 | 12 | 17 | 9 |
| 2021 | 59 | 142 | 1,789 | 11 | 22 | 8 |
| 2022 | 63 | 161 | 2,104 | 8 | 51 | 6 |
| 2023 | 58 | 149 | 1,607 | 4 | 52 | 2 |
| 2024 | 57 | 154 | 1,947 | 5 | 53 | 4 |
| 2025 | 58 | 197 | 2,821 | 2 | 57 | 1 |
| 2026 | 57 | 215 | 2,819 | 2 | 56 | 1 |
| 24 months to 14 Nov 2026 | 65 | 274 | 5,653 | 2 | 64 | 1 |

**Reading.** In 2020 and 2021 the network was in pieces within each year. In 2020 the
European regional leagues (LFL, PRM, NLC, UKLC and 13 others) formed a group of 17 with no game
against the group that held LCK, LPL, LEC and LCS. Their levels were set only against each other,
which explains the LFL anomaly. From 2022 almost every active league is in one connected group,
and from 2025 the network is close to complete. League levels from 2020 and 2021 are
therefore much less reliable than recent ones. The site's rule of ranking only well-linked
leagues is justified.

## 3. League strength with intervals

**Method.** On the 5,653 cross-league games in the 24 months to 14 November 2026, a
Bradley-Terry model with one strength per league:

logit P(blue wins) = b0 + θ(blue's league) − θ(red's league)

with a light ridge penalty (C = 10) that only fixes the scale of barely linked leagues. Strengths
are converted to Elo points (× 400 / ln 10) and centred on the mean of LCK and LPL. 95% intervals
come from 500 bootstrap re-draws of whole series. Like Elo league levels, θ describes how a
league's *representatives* did against other leagues' representatives, usually its top teams;
it is not the strength of the league's average team.

Selected rows (all 64 linked leagues are in the record):

| League | Cross-league games | Opponent leagues | Strength [95% interval] | Elo level (published settings) | Elo level range across 7 settings |
|---|---|---|---|---|---|
| LCK | 303 | 11 | +39 [+13, +65] | +38 | +10 to +45 |
| LPL | 250 | 11 | −39 [−65, −13] | −38 | −45 to −10 |
| LFL | 680 | 29 | −46 [−131, +26] | −1 | −18 to +17 |
| LEC | 435 | 10 | −126 [−195, −62] | −219 | −270 to −174 |
| LCS | 412 | 13 | −146 [−215, −80] | −245 | −285 to −200 |
| LTA N | 143 | 5 | −217 [−307, −128] | −393 | −453 to −310 |
| CBLOL | 429 | 13 | −278 [−366, −196] | −364 | −432 to −284 |
| PCS | 574 | 15 | −293 [−394, −209] | −477 | −576 to −355 |
| VCS | 305 | 15 | −289 [−384, −215] | −463 | −547 to −360 |
| LJL | 275 | 9 | −488 [−602, −398] | −775 | −946 to −582 |
| CCWS (flag: few games) | 29 | 1 | −30 [−186, +151] | −343 | −386 to −279 |

The "7 settings" are the published Elo configuration, the configurations chosen by the five
walk-forward windows, and k_league of 8 and 32 around the published 16. This range is a
sensitivity check, not a confidence interval.

**Reading.**
- On the 51 leagues with at least 30 cross-league games, the static strengths and the Elo levels
  rank leagues similarly (Spearman 0.84). Interval width falls as games rise (Spearman −0.84
  between games and width).
- Only the top of the table is precise. LCK and LPL have the narrowest intervals (about 50
  points), and LCK's interval lies above LPL's. LEC's and LCS's intervals sit almost entirely below
  LPL's. For leagues with at least 30 cross-league games the median interval is 225 points wide
  (10th to 90th percentile: 160 to 310), and leagues with fewer games have wider ones. Neighbouring
  leagues in the table usually cannot be told apart.
- **LFL is still the problem case.** It has the most cross-league games (680) but mostly against
  other European regional leagues. The static model puts it at −46, close to LEC, with an interval
  from −131 to +26; the Elo level of −1 is inside that interval but at its top. A claim that LFL
  is as strong as LCK/LPL is not supported.
- Elo levels are more spread out than the static strengths (LJL: −775 against −488). Part of this is
  the ridge penalty, which pulls weak leagues toward the middle; part is that Elo levels keep
  moving with each result. Neither scale should be read as exact.
- The Elo level of a weakly linked league moves by up to about 380 points across reasonable settings.

## 4. Do weak links hurt forecasts?

Main test games between teams from different leagues, grouped by the smaller of the two leagues'
cross-league game counts in the previous 365 days:

| Link strength | Games | Brier, form model | Brier, experience model | Mean forecast for blue | Blue win rate |
|---|---|---|---|---|---|
| fewer than 50 games | 507 | 0.1856 | 0.1826 | 0.545 | 0.540 |
| 50 to 199 | 2,351 | 0.2072 | 0.2037 | 0.544 | 0.543 |
| 200 or more | 237 | 0.2256 | 0.2222 | 0.579 | 0.595 |

**Reading.** No sign that weakly linked matchups are forecast worse. Their Brier scores are
lower because these games are often lopsided (a strong league's team against a small league's
team), and the average forecast matches the average result in every group. This is a coarse check:
237 games in the top group is a small sample, and matching averages do not prove calibration
inside each group.

## 5. What to change, and what not

- **Do not replace league Elo.** The static model is a check, not a forecaster: it uses games from
  the whole 24-month window, including games after the forecast date. A hierarchical or partial-pooling
  rating that is fitted point-in-time could reduce the spread of weakly linked levels; it should be
  tested only against the current model on the same games, and it is not needed to fix any forecast
  problem found here.
- **Show uncertainty where rankings are shown.** Any league table on the site should show the
  cross-league game count, the interval from section 3 with its cutoff date, and a warning below
  30 games. Elo levels alone should not be shown as a ranking. This is listed in the audit as a
  pending site change; the numbers are in the record.
- **Treat 2020 to 2021 league levels with care** in any historical comparison.

## 6. Limits

- The static model ignores which teams represented each league and in which events; a league that
  sends only its champion looks stronger than one that sends three teams.
- Cross-league games are not random: they happen at events where the best teams meet.
- Home league is a rule, not a fact: a team that switches leagues takes some time to be moved.
- The bootstrap treats series as independent; teams that meet repeatedly in one event are linked.
