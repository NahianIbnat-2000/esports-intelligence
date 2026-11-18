# Methodology

## 1. Sample construction

- Unit: one game. The target is whether the blue side wins.
- Rows excluded only for a recorded reason; games accepted only with exactly two
  team rows (Blue and Red), two different teams, one winner, one date.
- Duplicates: exact duplicate rows are dropped (one kept); conflicting rows with the
  same `gameid` + `participantid` are dropped entirely and reported.

## 2. Elo

E_A = 1 / (1 + 10^((R_B − R_A)/400)), update R'_A = R_A + K (S_A − E_A).

| Choice | Value |
|---|---|
| Initial rating | 1500 for every team when first seen |
| Update frequency | after every game, chronological; games with the same timestamp are one batch |
| Inactive teams | no decay |
| New season | R ← 1500 + (1 − s)(R − 1500) at a team's first game in a new calendar year |
| K and s | grid K ∈ {8, 12, 16, 20, 24, 32, 40, 48, 56, 64, 80}, s ∈ {0, 0.25, 0.5, 0.75}; chosen by validation log loss |
| League offsets | rating = league level + team component; games between leagues move league levels by k_league ∈ {0, 2, 4, 8, 16, 32}; new teams start at their league level; home league = most frequent domestic league so far; on a home change the total is kept |
| Search | coordinate search on validation log loss: K x s (flat), then k_league, then K x s again |
| Sensitivity | full grid stored in `model_versions.hyperparameters.grid` and shown in the research report |

Known limitation: league levels are identified only through games between leagues. Leagues
that rarely meet the major leagues have poorly identified levels against them.

## 3. Features (pre-specified)

All computed from games with a strictly earlier timestamp (series game 2 may use
game 1, which ended earlier).

| Feature | Definition |
|---|---|
| elo_diff | blue pre-game Elo − red pre-game Elo |
| recent_wr_diff | difference in (wins + 1)/(n + 2) over the last 10 games |
| hist_wr_diff | difference in (wins + 2.5)/(n + 5) over all earlier games |
| opp_strength_diff | difference in mean pre-game Elo of the last 10 opponents |
| experience_diff | difference in log(1 + earlier games) |
| elo_diff_x_intl | elo_diff × 1[Worlds, MSI, First Stand or Esports World Cup] |

The feature list was fixed before evaluation and is not tuned on test results.

## 4. Models and validation

- Elo baseline: expected score, no fitted parameters.
- Calibrated Elo: logistic regression on elo_diff (intercept = blue-side effect).
- Logistic regression: the six features, standardised inside a scikit-learn
  pipeline fitted on training data, L2 strength C ∈ {0.0003, 0.001, 0.003, 0.01, 0.1, 1, 10} chosen on validation.
- Split by date: train 70%, validation 15%, test 15% of eligible games, after a
  90-day burn-in. Eligible = both teams have ≥ 5 earlier games. Same games for all models.
- Logistic models are refit on train + validation and scored once on test.
- Leakage controls: strict-timestamp features (tested by flipping future results
  and checking past features do not change), no post-game statistics, scaler fitted
  on training rows, one row per `gameid`, chronological split (tested for overlap).

## 5. Evaluation

Accuracy, precision, recall (0.5 threshold, positive = blue win), ROC-AUC,
Brier score BS = (1/N) Σ (p_i − y_i)², log loss, reliability diagram (10 equal-width
bins), confusion matrix, quarter-by-quarter and league breakdowns, and a paired
cluster bootstrap (2,000 resamples) of per-game loss differences that resamples whole
series (same tournament, same two teams, same UTC day).

## 6. Competitive economics

| Indicator | Formula | Concentrated quantity |
|---|---|---|
| HHI | Σ s_i² | share of regular-season wins; share of derived titles |
| Normalised HHI | (HHI − 1/N)/(1 − 1/N) | as above |
| Gini | (2 Σ i·x_(i))/(N Σ x) − (N+1)/N | wins per team |
| Lorenz curve | cumulative share by sorted holders | titles |
| Noll-Scully | sd(win%) / (0.5/√G) | within-split balance |
| Persistence | corr and OLS slope of win% in consecutive splits | team strength |
| Upset rate | share of games won by the lower pre-game Elo team | predictability |

Assumptions and limits are listed in each research report. Prize money is not
in the source and is not analysed.

## 7. References

Elo (1978); Brier (1950); Hvattum & Arntzen (2010), IJF 26(3); Niculescu-Mizil &
Caruana (2005), ICML; Efron & Tibshirani (1993); Rottenberg (1956), JPE 64(3);
Fort & Quirk (1995), JEL 33(3); Scully (1989); Hirschman (1964), AER 54(5); Gini (1912).
