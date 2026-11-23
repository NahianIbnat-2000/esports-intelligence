# Current issue status

Last updated 23 November 2026. This file gives the current status of every issue raised in
earlier audits and reports. The earlier documents are kept unchanged as historical records:
`DEVELOPMENT_REPORT.md` (v1.0), `AUDIT_AND_IMPROVEMENTS_v1.2.md` (18 Nov), `PROJECT_AUDIT.md`
(2.0 stage 1, 20 Nov), `AUDIT_2026_11_FOLLOWUP.md` (23 Nov).

| Issue | First raised | Status now | Where |
|---|---|---|---|
| Only one test period | v1.2 §7, PROJECT_AUDIT §3.1 | **Resolved**: five-year walk-forward | `EXPERIMENTS.md` |
| No untouched holdout after the walk-forward study | AUDIT_2026_11 R1 | **Open, plan fixed**: prospective test pre-registered | `PREREGISTRATION_2027.md` |
| League levels poorly identified for weakly linked leagues | v1.0 L, v1.2 §7, PROJECT_AUDIT §3.2 | **Measured, still a limit**: intervals and network analysis; site table with intervals not yet built | `LEAGUE_RATING_UNCERTAINTY.md` |
| Series approximated by tournament, team pair and UTC day | v1.0 L, v1.2 §7, PROJECT_AUDIT §3.3 | **Measured, low impact**: 861 series split at midnight; intervals change in the 5th decimal | `ROBUSTNESS_AND_SENSITIVITY.md` §2 to 3 |
| Article said the model uses head-to-head | PROJECT_AUDIT §3.4 | **Resolved** | `index.html` |
| Methodology page out of date | PROJECT_AUDIT §3.5 | **Resolved** | `/methodology` |
| No player or roster information | PROJECT_AUDIT §3.6 | **Resolved**: roster and player features tested; player model deployed | `EXPERIMENTS.md` |
| What player experience captures | AUDIT_2026_11 R2 | **Studied** | `PLAYER_EXPERIENCE_MECHANISMS.md` |
| Source `year` is a season label | v1.0 L, PROJECT_AUDIT §3.7 | **Documented**; Elo uses dates, not affected | `RESULTS_2020_2026.md` |
| Experiment metadata partial | PROJECT_AUDIT §3.8 | **Resolved**: registry; release manifest added | `research/release_manifest.json` |
| Models fixed for the whole test period (no rolling refit) | v1.2 §7 | **Measured**: yearly refits help by 0.0002 to 0.0005; rolling vs expanding training makes no difference | `ROBUSTNESS_AND_SENSITIVITY.md` §5 |
| Forecast timing not stated (pre-game updating) | AUDIT_2026_11 D2 | **Resolved**: measured; README, article, paper, methodology, FAQ and Experiments page updated | `ROBUSTNESS_AND_SENSITIVITY.md` §1 |
| Paper Table 4 not reproducible | AUDIT_2026_11 D1 | **Resolved** | `coefficients.py`, paper |
| Published numbers can go stale across surfaces | AUDIT_2026_11 G2 | **Resolved**: claims registry checked in CI | `research/claims.json` |
| Many comparisons, none pre-registered | AUDIT_2026_11 R3 | **Measured**: Holm correction reported | `ROBUSTNESS_AND_SENSITIVITY.md` §4 |
| 346 teams and 1,228 players without a source id (keyed by name) | v1.0 L | **Open**, documented | `/data-quality` |
| Tournament names, prize money, countries not in source | v1.0 L, v1.2 §7 | **Open**, source limit | |
| Derived champions, not an official register | v1.0 L, v1.2 §7 | **Open**, labelled on site | |
| Rate limiting and cache per process | v1.0 L | **Open**, acceptable on one instance | |
| Recharts 2.x | v1.0 L | **Open**, small migration | |
| npm advisories in build tools only | v1.2 §7 | **Open**, no runtime exposure | |
| Prediction Lab: side-by-side model comparison | PROJECT_AUDIT §5.5 | **Resolved**: four models side by side | `/predictions` |
| Prediction Lab: scenario sliders | PROJECT_AUDIT §5.5 | **Open** | |
| Player-model contributions not shown in the Prediction Lab | AUDIT_2026_11 A3 | **Open** | |
| Snapshot meta lacks data and model version | AUDIT_2026_11 A2 | **Open** | |
| No API timeout on the client | AUDIT_2026_11 A1 | **Needs a live check** | |
| Chart text alternatives, focus styles, browser tests | AUDIT_2026_11 U2 to U5 | **Needs a browser session** | |
| Glicko-2 / TrueSkill | PROJECT_AUDIT §5.7 | **Not needed now**: cold-start study shows a player-informed start adds little | `PLAYER_EXPERIENCE_MECHANISMS.md` §4.2 |
| Research assistant (LLM) | PROJECT_AUDIT §5.8 | **Not planned**: needs paid keys | |
| Automated ingestion and drift monitoring | PROJECT_AUDIT §5.9 | **Not planned**: needs infrastructure approval | |
