# Project audit (Esports Intelligence 2.0, stage 1)

Date: 20 Nov 2026. Audited: the GitHub repository (commit `30ef549`, "Updated index.html"),
the local working copy with the same code plus the unpushed methodology update, the local
database built from the same Oracle's Elixir files, the saved model artifact
`1.0.0+c8b6f8e19c`, and the live site (server-rendered HTML only; see limits at the end).

## 1. Current architecture and features

| Layer | What exists | Location |
|---|---|---|
| Data pipeline | Download (manifest + SHA-256), normalise, validate, load; exclusions with reasons | `pipelines/oracle_elixir/` |
| Database | PostgreSQL, SQLAlchemy models, Alembic migrations (games, matches, teams, players, rosters, Elo history, predictions, model versions, dataset versions, ingestion logs) | `backend/app/models`, `backend/alembic` |
| Ratings | Flat Elo and Elo with league levels, same-timestamp batching, new-year carry-over | `machine_learning/elo/elo.py` |
| Features | Six pre-game features, strictly earlier games only | `machine_learning/feature_engineering/features.py` |
| Training | Date split 70/15/15 after a 90-day burn-in; Elo grid on validation log loss; calibrated Elo; logistic regression (C on validation); tree models checked on validation only | `machine_learning/training/train.py` |
| Evaluation | Brier, log loss, accuracy, ROC-AUC, ECE (10 bins), reliability table, series-cluster and tournament-cluster paired bootstrap, quarter and league breakdowns | `machine_learning/evaluation/metrics.py` |
| API | FastAPI v1: overview, matches, series, match centre, teams, players, tournaments, analytics (team, player, balance, history, trajectories, regional), predictions (models, test games, history, POST), research, data explorer and CSV export, data quality, provenance, ticker, health | `backend/app/api/routes/v1.py` |
| Frontend | Next.js 15, React 19, Tailwind, Recharts, React Query; terminal theme; 20 routes incl. FAQ | `frontend/app` |
| Hosting | Vercel (frontend), Render free (API), Supabase (database), static snapshot fallback, UptimeRobot | `render.yaml`, `docs/deployment.md` |
| Tests and CI | 97 backend tests (unit + PostgreSQL integration), 13 frontend tests, GitHub Actions for both | `tests/`, `frontend/tests`, `.github/workflows/ci.yml` |

Confirmed working in this audit: backend test suite (97 passed), frontend type check, unit
tests and production build, local rendering of every route at desktop and phone width (earlier
session), live site responds.

## 2. Verified research baselines

Every published number was recomputed from the database or read from the saved artifact
(`machine_learning/models/artifacts/1.0.0+c8b6f8e19c/evaluation.json`).

| Claim (portfolio / README) | Source checked | Result |
|---|---|---|
| 75,830 games | `count(*) from matches`; split counts 47,070 + 10,086 + 10,087 + 8,587 excluded | Confirmed |
| 1,914 teams, 10,239 players, 109 leagues | database counts | Confirmed |
| Data 3 Jan 2020 to 17 Nov 2026 | min/max `match_date` | Confirmed |
| Test 23 Sep 2025 to 14 Nov 2026, 10,087 games | artifact `split` | Confirmed (games after 14 Nov fail the 5-earlier-games rule or fall in the excluded tail) |
| Logistic regression Brier 0.2164, 64.9% | artifact | Confirmed (0.21640, 0.6488) |
| Calibrated Elo Brier 0.2170 | artifact | Confirmed (0.21702) |
| Elo with league levels 0.2176, 64.7% | artifact | Confirmed (0.21765, 0.6470) |
| League levels vs flat Elo: -0.0054 Brier | artifact `league_offsets.selected_vs_flat_brier` | Confirmed (-0.00543, 95% CI -0.0068 to -0.0041) |
| Logistic vs calibrated Elo: -0.0006 Brier | artifact `comparisons.logreg_vs_elo_logit_brier` | Confirmed (-0.00062, 95% CI -0.0010 to -0.0002) |
| Tree models not better | artifact `experimental_models` | Confirmed (gradient boosting +0.00004, random forest +0.00075 vs logistic, validation) |

## 3. Inconsistencies and problems found

Ranked by how much they affect the research claims.

1. **One test period only.** All headline results come from a single 14-month window. There
   is no evidence yet that the ranking of models holds in other years. This is the main
   research gap. *Fix in this stage: walk-forward evaluation.*
2. **League levels are not on one common scale.** The fitted levels put LFL (France, 1,932)
   above LPL (China, 1,895) and far above LEC (1,713). LFL's cross-league games are mostly
   against other European regional leagues, so its level is identified inside that cluster,
   not against LPL. The site already limits global rankings to well-linked leagues, but the
   raw level table should not be read as a world ranking. *Documented; a hierarchical
   prior is listed as future work.*
3. **Two series definitions.** The bootstrap groups games by tournament + team pair + UTC day;
   the match centre uses the 3-hour / 12-hour rule. Both are reasonable, but they can
   disagree for series that cross midnight UTC. *Documented; low impact on intervals.*
4. **Article note said the model uses head-to-head records.** It does not (head-to-head is
   shown in the prediction explanation only). *Fixed in `index.html`.*
5. **Methodology page out of date on GitHub** (still says series are not rebuilt, no league
   levels). *Fixed locally in the previous session, not yet pushed.*
6. **No player or roster information in the model**, although the source has a player id for
   every player in every game. This is the most direct way to test whether more information
   beats Elo. *Investigated in this stage.*
7. **`year` is the source's season label, not the calendar year** (180 games played in
   Aug to Nov 2026 are labelled 2027, e.g. LCS and CBLOL qualifiers). Elo carry-over uses the
   game date, so ratings are not affected; season tables follow the source label.
   *Documented.*
8. **Experiment metadata is partial.** The artifact stores data fingerprint, split, grid and
   metrics, but not package versions, code commit or a run seed. *Fixed for new experiments
   (registry below).*

Potential leakage checked: features use strictly earlier timestamps (tested), scaler fitted on
training rows, Elo hyperparameters tuned on validation only, logistic models refit on train +
validation before the single test scoring. No leakage found. One point to state openly: Elo
hyperparameters stay fixed when the logistic models are refit on train + validation, which is
conservative for Elo-based features.

## 4. UI, API, database, security

- Prediction lab already has local explanations (log-odds contributions, side effect,
  head-to-head shown as context). Scenario sliders and side-by-side model comparison are not
  there yet.
- Missing states: snapshot views degrade to a "waking up" notice; explicit "model not
  available" states exist on the prediction page.
- Rate limiting on the API; CORS restricted to the Vercel domain and localhost; secrets only
  in host dashboards; `.env.example` is the only env file in the repository. No secrets found
  in tracked files.
- Model artifacts are joblib (pickle) files loaded from the repository. Safe as long as only
  the owner can write to the repository; do not load artifacts from elsewhere.
- Render free tier sleeps; the snapshot covers common views. Supabase free tier pauses after a
  week without activity; UptimeRobot hits `/health`, which queries the database, so it also
  keeps Supabase awake.

## 5. Ranked plan

| Rank | Change | Why | Needs approval? |
|---|---|---|---|
| 1 | Walk-forward evaluation over several years | Tests whether the main finding holds beyond one window | No |
| 2 | Roster-aware features and player-level Elo, with ablation | Direct test of "does more information beat Elo" using data already in the source | No |
| 3 | Experiment registry (JSON per run: data checksum, periods, configs, versions, seed, metrics) | Reproducibility | No |
| 4 | Experiments page on the site reading the registry | Makes the new evidence visible | No (frontend only) |
| 5 | Prediction lab: compare models side by side; scenario sliders that re-run the real model | Explainability | No |
| 6 | Patch analysis (calibration early vs late in a patch) | Cheap, uses the existing `patch` column | No |
| 7 | Glicko-2 or TrueSkill as a rating alternative | Only if walk-forward shows rating uncertainty matters (new teams) | No |
| 8 | Research assistant (LLM) | Needs a paid API key on the server, abuse protection, an evaluation set | **Yes: cost and keys** |
| 9 | Automated ingestion schedule and drift monitoring | Data updates are manual today; a schedule needs a reliable job runner | Yes: infrastructure |

Not planned: MLflow (a JSON registry is enough at this scale), a full UI redesign (the
terminal restyle is two days old and works), any new paid service.

## 6. Risks and data constraints

- Lineups: the source gives the five players who actually played. They are known when the
  game starts (draft), not days before. Roster features therefore answer "does knowing the
  lineup help?", not "can we predict a week ahead?". This is stated with every result.
- Player ids are stable within Oracle's Elixir but players who change names or ids are
  counted as new players.
- Walk-forward re-tunes Elo per window, which is compute-heavy (a full Elo run takes about 3 s);
  grids are trimmed around the published optimum and the trimming is recorded.
- Patch: present for 99.97% of games; patch naming changed over the years, so only
  "games since patch start" type features are safe across years.

## 7. Audit limits

- The live site was checked through its server-rendered HTML only; interactive behaviour was
  checked on a local production build with the same code.
- GitHub Actions results could not be read from this environment; the same commands were run
  locally instead.

## 8. Status after this stage

| Plan item | Status |
|---|---|
| 1 Walk-forward evaluation | Done: `machine_learning/experiments/walk_forward.py`, results in `docs/EXPERIMENTS.md` |
| 2 Roster and player features, ablation | Done (pre-match and lineup-known variants); leakage tests added |
| 3 Experiment registry | Done: `machine_learning/experiments/registry/` |
| 4 Experiments page | Done: `/experiments` |
| 4b Article note on head-to-head | Fixed in `index.html` |
| 5 to 9 | Not started; see ranked plan above |

Main new result: the published finding replicates in all five test years, and player
experience (usable before match day) improves Brier about ten times more than the form
features. A follow-up by type of game shows the gain is not a league-tier artefact: it is
the same size in same-league domestic games and largest for new teams. Follow-up (same day): the pre-match player model was added to the prediction lab as a
fourth model; the three published models are unchanged.
