# Follow-up audit, 23 November 2026

Scope: the repository at commit `3152946` (GitHub, master), the processed and raw data of the 18
November 2026 run, the published case study, the registry records and the article. Branch for
this work: `research/v2.1`. Nothing was deployed.

Classes: **Confirmed defect**, **Research limitation**, **Enhancement opportunity**,
**Requires verification**, **Already resolved**. Evidence is a file, record, test or command.

## 1. Verified existing functionality

| # | Finding | Class | Evidence |
|---|---|---|---|
| V1 | The 7 raw Oracle's Elixir files match the SHA-256 values in the walk-forward record (fingerprint c8b6f8e19c) | Already resolved | checksum comparison, `REPRODUCTION_VERIFICATION.md` §2 |
| V2 | The published split (47,070 / 10,086 / 10,087) and test Brier scores (0.2488, 0.2176, 0.2170, 0.2164, 0.2116) rebuild exactly from processed data | Already resolved | `player_model.rebuild_published`, §3 there |
| V3 | The committed model files reproduce the published test predictions exactly | Already resolved | `prospective.py` dry run, `PREREGISTRATION_2027.md` |
| V4 | Local working copy and GitHub master are the same apart from the snapshot you rebuilt and float noise at the 16th decimal in one evaluation file | Already resolved | `diff -rq` |
| V5 | Backend tests: 105 passed before; 116 pass now (1 skipped: needs Postgres) | Already resolved | `pytest`, §6 there |
| V6 | Prediction Lab replays point-in-time: team state from games before the chosen date, only dates after validation allowed, model version shown per prediction, exact log-odds contributions for the logistic model | Already resolved | `backend/app/services/predictions.py` lines 104 to 220 |
| V7 | Pages served from the snapshot say so, with the snapshot time | Already resolved | `frontend/components/ui/primitives.tsx` line 209 |
| V8 | Experiment registry stores data checksum, code checksum, package versions, seed | Already resolved | `machine_learning/experiments/registry.py` |

## 2. Confirmed defects

| # | Finding | Class | Evidence | Status |
|---|---|---|---|---|
| D1 | Table 4 of the paper (coefficient intervals) and "about 83 earlier games" were computed in an earlier session and not saved; rebuilt values differ slightly: 1.68 to 1.82 (paper: 1.83), 1.36 to 1.43 (1.37), 1.03 to 1.10 (1.04), 82 games (83) | Confirmed defect | `coefficients-20261123-110345-c8b6f8e19c.json` | **Fixed**: `coefficients.py`, paper corrected, PDF rebuilt (15 pages) |
| D2 | Forecast timing is not stated. All published forecasts are **pre-game**: game 2 of a series already uses game 1's result and lineup. The pages call the player feature "known before match day" | Confirmed defect (documentation) | `ROBUSTNESS_AND_SENSITIVITY.md` §1 | Measured: the player gain is the same before the series (−0.0044). **Text change pending your approval** (§9) |
| D3 | The "previous-team Elo" idea cannot test transfers with this data: it equals the team's own Elo in 81% of games | Confirmed defect (in a new measure, found and reported, not used) | `PLAYER_EXPERIENCE_MECHANISMS.md` §4.1 | Documented |

No defect was found in the published model results.

## 3. Unresolved research weaknesses

| # | Finding | Class | Evidence | Status |
|---|---|---|---|---|
| R1 | No untouched holdout: the walk-forward 2025 and 2026 test years overlap the main test, and the player feature was chosen after the walk-forward study | Research limitation | `ROBUSTNESS_AND_SENSITIVITY.md` §6 | **Addressed**: models frozen, prospective test pre-registered (`PREREGISTRATION_2027.md`) |
| R2 | What player experience measures was unknown | Research limitation | | **Studied**: about 55% of its gain survives four skill controls; most of the rest overlaps with career length and recent activity; 68% of the gain comes from stable teams (`PLAYER_EXPERIENCE_MECHANISMS.md`) |
| R3 | 72 pooled comparisons, none pre-registered | Research limitation | | **Measured**: 64 of 69 nominal results survive Holm; the five that do not are all ≤ 0.0001 |
| R4 | League levels for weakly linked leagues are uncertain; in 2020 the European regional leagues had no link to the major leagues | Research limitation | `LEAGUE_RATING_UNCERTAINTY.md` | **Measured**: intervals from a series bootstrap; Spearman 0.84 with Elo levels |
| R5 | Series rebuilt by UTC day split 861 series at midnight | Research limitation | `ROBUSTNESS_AND_SENSITIVITY.md` §2 | **Measured**: intervals change in the 5th decimal |
| R6 | The source shows who played, not when the lineup was announced | Research limitation | | Labelled in every lineup-confirmed result |
| R7 | Player careers before 2020 are not in the data; renamed player ids count as new | Research limitation | | Documented |
| R8 | Organisation resources (salary, staff) are not observed, so the experience association cannot be split into skill, survival and resources | Research limitation | | Documented; no fix in this data |

## 4. Reproducibility gaps

| # | Finding | Class | Status |
|---|---|---|---|
| G1 | Table 4 not reproducible from the repository | Confirmed defect | Fixed (D1) |
| G2 | No machine-readable link between published numbers and artifacts; a number could go stale on one surface | Enhancement opportunity | **Done**: `research/claims.json` (31 claims) + `verify_claims.py` + test; all pass |
| G3 | No release manifest linking data, artifacts, records, paper and site | Enhancement opportunity | **Done**: `research/release_manifest.json` + `manifest.py`; checksums tested in CI |
| G4 | Oracle's Elixir updates the current-year file daily, so a later download of the 2026 file will not match. Exact reproduction needs the 18 November 2026 files (SHA-256 in the manifest), which cannot be redistributed | Research limitation | Documented in `REPRODUCTION_VERIFICATION.md`; checksums make the mismatch visible |
| G5 | Processed data rebuilt from raw in a clean folder | Already resolved | All 8 tables identical (`REPRODUCTION_VERIFICATION.md` §4) |
| G6 | Full walk-forward rerun from scratch | Already resolved | Every value equal (`REPRODUCTION_VERIFICATION.md` §5) |

## 5. UX and accessibility (code review only)

No browser automation was run in this session. Findings from reading the code:

| # | Finding | Class |
|---|---|---|
| U1 | 24 `aria-label`s, 1 `aria-live` region, 6 `sr-only` texts | Already resolved (partly) |
| U2 | Only 2 charts have `role="img"` and a text label; most charts have no text alternative | Requires verification (likely defect) |
| U3 | Focus styles: one `focus-visible` rule in the code base; keyboard focus may be hard to see on custom controls | Requires verification |
| U4 | Reduced motion handled in one place | Requires verification |
| U5 | No end-to-end browser tests (Playwright) | Enhancement opportunity |

## 6. API and deployment reliability

| # | Finding | Class |
|---|---|---|
| A1 | Snapshot is tried first; if a view is missing, the live API is called with no timeout, so a sleeping Render instance can leave a page waiting | Requires verification |
| A2 | Snapshot `meta` records when it was made but not the data fingerprint or model version, so a snapshot from an older model could be shown next to newer live results without notice | Enhancement opportunity |
| A3 | The Prediction Lab explains the logistic model's log-odds; the deployed player model shows its input values but not its contributions | Enhancement opportunity |
| A4 | The live site and API were not reachable from this session | Requires verification |

## 7. Documentation inconsistencies

| # | Finding | Status |
|---|---|---|
| DOC1 | "known before match day" / "pre-match" (README, article, paper) vs actual pre-game updating | Pending text change (§9) |
| DOC2 | `PROJECT_AUDIT.md` §8 lists items 5 to 9 as "not started"; some are now done | **Done**: `ISSUE_STATUS.md` gives the current status of every past finding; old audits keep their text and get a pointer at the top |
| DOC3 | Paper Table 4 values | Fixed (D1) |

## 8. Improvements ranked by expected value

| Rank | Change | Why | Status |
|---|---|---|---|
| 1 | Pre-register a prospective test, freeze models | Only clean confirmation left for the main new claim | **Done** |
| 2 | Mechanism study of player experience | Main open research question | **Done** |
| 3 | Claims registry, checker, manifest, CI test | Stops stale numbers, links paper to code | **Done** |
| 4 | Fix Table 4 reproducibility | Published numbers must rebuild | **Done** |
| 5 | Forecast-timing contracts and wording | Defensible claims about when forecasts are usable | Measured; wording pending approval |
| 6 | Robustness: bootstrap units, multiple testing, temporal checks | Strength of evidence | **Done** |
| 7 | League connectivity and intervals | Ranking claims | **Done** (analysis); site table with intervals pending |
| 8 | Add the new findings to the paper and article | Publication consistency | Pending your review |
| 9 | Snapshot data/model version in `meta`; API timeout with a clear message | Reliability | Not started |
| 10 | Player-model contributions in the Prediction Lab | Transparency | Not started |
| 11 | Chart text alternatives, focus styles, Playwright journeys | Accessibility, reliability | Not started; needs a browser session |
| 12 | Model-disagreement explorer | Product | Not started; the mechanism predictions (`/tmp` during runs) would supply it |

Not recommended now: replacing league Elo with a hierarchical model (no forecast problem found),
deploying the better `skill_exp` model before the prospective test, an LLM assistant, VALORANT or
CS2.

## 9. Text changes that need your approval

These are corrections of wording to match evidence, but they change public pages:

1. README, article and paper: replace "known before match day" with "uses only each team's
   previous lineup; measured between games, and the gain is the same when all inputs are frozen
   before the series starts (−0.0044)".
2. Paper and article: add one short section on what experience captures (H1 to H4 results), the
   pre-registered test, and the timing contracts.
3. Methodology page and FAQ: say that forecasts update between games of a series.
