"""Research publications.

The text of each report (question, motivation, method, limitations) is
fixed. Results and findings are generated from stored analysis outputs and
model metrics using explicit rules; when the inputs do not exist the report
is labelled "proposed" and shows no results. No finding is written by hand.
"""
from __future__ import annotations

import numpy as np
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import DatasetVersion, Game, ModelVersion
from backend.app.services.overview import analysis

REFERENCES = {
    "elo": "Elo, A. E. (1978). The Rating of Chessplayers, Past and Present. Arco Publishing.",
    "brier": "Brier, G. W. (1950). Verification of forecasts expressed in terms of probability. Monthly Weather "
             "Review, 78(1), 1-3.",
    "hvattum": "Hvattum, L. M., & Arntzen, H. (2010). Using ELO ratings for match result prediction in association "
               "football. International Journal of Forecasting, 26(3), 460-470.",
    "niculescu": "Niculescu-Mizil, A., & Caruana, R. (2005). Predicting good probabilities with supervised "
                 "learning. Proceedings of the 22nd International Conference on Machine Learning, 625-632.",
    "efron": "Efron, B., & Tibshirani, R. J. (1993). An Introduction to the Bootstrap. Chapman & Hall.",
    "rottenberg": "Rottenberg, S. (1956). The baseball players' labor market. Journal of Political Economy, 64(3), "
                  "242-258.",
    "fort_quirk": "Fort, R., & Quirk, J. (1995). Cross-subsidization, incentives, and outcomes in professional team "
                  "sports leagues. Journal of Economic Literature, 33(3), 1265-1299.",
    "scully": "Scully, G. W. (1989). The Business of Major League Baseball. University of Chicago Press.",
    "hirschman": "Hirschman, A. O. (1964). The paternity of an index. American Economic Review, 54(5), 761.",
    "gini": "Gini, C. (1912). Variabilità e mutabilità. Tipografia di Paolo Cuppini, Bologna.",
    "oe": "Sevenhuysen, T. Oracle's Elixir: LoL esports match data. https://oracleselixir.com/tools/downloads",
}


def _fmt(x, d=4):
    return "n/a" if x is None else f"{x:.{d}f}"


def _ci_sentence(label: str, c: dict, base: str = "Elo") -> str:
    borderline = min(abs(c["ci95_low"]), abs(c["ci95_high"])) < 5e-5
    if c["ci95_high"] < 0:
        verdict = f"lower (better) than {base}, and the 95% bootstrap interval excludes zero" + (
            ", but only just (the upper bound is almost zero)" if borderline else "")
    elif c["ci95_low"] > 0:
        verdict = f"higher (worse) than {base}, and the 95% bootstrap interval excludes zero"
    else:
        verdict = f"not distinguishable from {base}: the 95% bootstrap interval includes zero"
    return (f"{label}: {c['metric'].replace('_', ' ')} difference {c['difference']:+.5f} "
            f"(95% CI {c['ci95_low']:+.5f} to {c['ci95_high']:+.5f}); {verdict}.")


def _data_section(db: Session, game: Game) -> dict:
    dvs = db.scalars(select(DatasetVersion).where(DatasetVersion.game_id == game.id)).all()
    return {"source": "Oracle's Elixir professional League of Legends match data (yearly CSV files).",
            "files": [{"filename": d.filename, "sha256": d.sha256[:12], "coverage_start": d.coverage_start,
                       "coverage_end": d.coverage_end, "rows_accepted": d.rows_accepted} for d in dvs]}


def ml_report(db: Session, game: Game) -> dict:
    mvs = {m.model_key: m for m in db.scalars(select(ModelVersion).where(ModelVersion.game_id == game.id))}
    base = {
        "slug": "can-machine-learning-beat-elo",
        "title": "Can Machine Learning Beat Elo in Professional League of Legends?",
        "research_question": "Does a logistic regression with pre-game features predict single-game outcomes "
                             "better than an Elo benchmark, in terms of probability accuracy (Brier score, log "
                             "loss) on a later, untouched test period?",
        "motivation": "Elo is simple, transparent and hard to beat in many sports. If extra features do not "
                      "improve out-of-sample probability accuracy, the added complexity is not justified. "
                      "Separating a calibrated Elo from a feature-rich model shows whether any gain comes from "
                      "calibration (including the blue-side effect) or from new information.",
        "methodology": [
            "Unit: one game. Target: blue side wins (1/0).",
            "Elo: initial 1500, expected score 1/(1+10^((Rb-Ra)/400)), updated after every game in time order. "
            "K-factor (8-80) and between-season shrinkage (0-0.75) chosen by validation log loss.",
            "League offsets: a team's rating is its league's level plus a team component. Games between "
            "leagues also move the two league levels (step k_league, 0-32, chosen on validation; 0 = flat Elo). "
            "New teams start at their league's level. The 'Elo baseline' below is the selected version; flat "
            "Elo is reported separately.",
            "Calibrated Elo: logistic regression on the Elo difference only; its intercept estimates the "
            "blue-side advantage.",
            "Logistic regression: six pre-specified pre-game features (Elo difference, recent and historical "
            "shrunk win rates, recent opponent strength, experience, Elo difference x international event). "
            "Standardised inside the pipeline, fitted on training data only; L2 strength chosen on validation.",
            "Chronological split 70/15/15 by date after a 90-day burn-in; games where either team has fewer "
            "than 5 earlier games are excluded from all models alike. Final logistic models are refit on "
            "train+validation and scored once on the test period.",
            "Every feature uses games with an earlier timestamp only. Post-game statistics are never used.",
            "Comparison: paired cluster bootstrap (2,000 resamples) of the per-game loss difference on identical "
            "test games, resampling whole series (approximated as same tournament, same two teams, same UTC day).",
        ],
        "limitations": [
            "Series are approximated from the data (no series id in the source); two series between the same "
            "teams on the same day would be merged, which makes intervals slightly more conservative.",
            "All teams start at the same rating, and regions are linked only by international events, so "
            "cross-region rating levels are uncertain.",
            "Roster changes, patches and drafts are not modelled.",
            "Results describe this sample period and these leagues; they may not transfer to other periods.",
        ],
        "references": [REFERENCES[k] for k in ("elo", "brier", "hvattum", "niculescu", "efron", "oe")],
        "conclusion_rule": "Conclusions are generated from the bootstrap intervals: a model is called better only "
                           "if the 95% interval of its Brier difference excludes zero.",
    }
    if not mvs or any(m.status != "trained" for m in mvs.values()):
        reason = next((m.metrics or {}).get("reason") for m in mvs.values()) if mvs else "models not trained"
        return {**base, "status": "proposed", "status_note": f"Not yet conducted: {reason}", "results": None,
                "findings": [], "interpretation": None}
    e, el, lr = mvs["elo"].metrics, mvs["elo_logit"].metrics, mvs["logreg"].metrics
    table = [{"model": mvs[k].display_name, "model_key": k, **mvs[k].metrics["test"]} for k in ("elo", "elo_logit", "logreg")]
    comps = {**el["comparisons"], **lr["comparisons"]}
    findings = [
        f"Test sample: {e['test']['n']} games ({mvs['elo'].periods['test']['start'][:10]} to "
        f"{mvs['elo'].periods['test']['end'][:10]}); blue side won {e['test']['base_rate_blue_win']:.1%}.",
        f"Brier scores on the test period: Elo {_fmt(e['test']['brier'])}, calibrated Elo "
        f"{_fmt(el['test']['brier'])}, logistic regression {_fmt(lr['test']['brier'])} (coin flip = 0.25).",
        _ci_sentence("Logistic regression vs Elo", comps["logreg_vs_elo_brier"]),
        _ci_sentence("Calibrated Elo vs Elo", comps["elo_logit_vs_elo_brier"]),
        _ci_sentence("Logistic regression vs calibrated Elo", comps["logreg_vs_elo_logit_brier"], "calibrated Elo"),
    ]
    rel = comps["logreg_vs_elo_brier"]["difference"] / e["test"]["brier"]
    findings.append(f"Size of the gain: the logistic regression lowers the Elo Brier score by {abs(rel):.2%}. "
                    f"Accuracy moves from {e['test']['accuracy']:.1%} (Elo) to {lr['test']['accuracy']:.1%}.")
    unit = comps["logreg_vs_elo_brier"].get("resampling_unit", "single game")
    findings.append(f"Confidence intervals: {unit}, {comps['logreg_vs_elo_brier'].get('n_units', 'n/a')} resampling units.")
    lo = mvs["elo"].hyperparameters.get("league_offsets")
    if lo:
        c = lo["selected_vs_flat_brier"]
        verdict = ("lower (better)" if c["ci95_high"] < 0 else "higher (worse)" if c["ci95_low"] > 0
                   else "not distinguishable")
        findings.append(
            f"League offsets (k_league = {lo['selected_k_league']:g}) vs flat Elo: Brier {e['test']['brier']:.4f} vs "
            f"{lo['flat_test']['brier']:.4f}, difference {c['difference']:+.5f} (95% CI {c['ci95_low']:+.5f} to "
            f"{c['ci95_high']:+.5f}), {verdict}; a {abs(c['difference']) / lo['flat_test']['brier']:.2%} change.")
        xl = lo.get("cross_league_only_brier")
        if xl:
            findings.append(f"On the {lo['cross_league_test_games']} test games between teams from different leagues, "
                            f"the Brier difference is {xl['difference']:+.5f} (95% CI {xl['ci95_low']:+.5f} to "
                            f"{xl['ci95_high']:+.5f}).")
    if "baseline_prevalence" in mvs:
        b = mvs["baseline_prevalence"].metrics["test"]
        findings.append(f"Prevalence baseline (always predict the earlier blue-side win rate): Brier {b['brier']:.4f}, "
                        f"accuracy {b['accuracy']:.1%}. Elo improves on it by "
                        f"{b['brier'] - e['test']['brier']:.4f} Brier points.")
    tcl = comps.get("logreg_vs_elo_logit_brier_tournament_clusters")
    if tcl:
        findings.append(f"Sensitivity: clustering by tournament ({tcl.get('n_units')} tournaments) instead of series "
                        f"gives a logistic vs calibrated Elo interval of {tcl['ci95_low']:+.5f} to "
                        f"{tcl['ci95_high']:+.5f}.")
    exp = (mvs["logreg"].hyperparameters or {}).get("experimental_models")
    if exp:
        findings.append("Tree models (validation only): " + exp["decision"])
    ep = mvs["elo_logit"].hyperparameters
    if "implied_blue_win_prob_equal_elo" in ep:
        findings.append(f"Estimated blue-side effect: with equal Elo, the calibrated model gives blue "
                        f"{ep['implied_blue_win_prob_equal_elo']:.1%}.")
    gain = comps["logreg_vs_elo_logit_brier"]
    if gain["ci95_high"] < 0:
        interp = ("Statistically, the pre-game features add predictive information beyond a calibrated Elo in this "
                  "test period (the interval excludes zero). Practically, the gain is small: "
                  f"{abs(gain['difference']):.5f} Brier points, about "
                  f"{abs(gain['difference']) / mvs['elo_logit'].metrics['test']['brier']:.2%} of the calibrated Elo "
                  "score, and accuracy barely moves. Elo already carries most of the signal.")
        if lo and lo["selected_vs_flat_brier"]["ci95_high"] < 0 and \
                abs(lo["selected_vs_flat_brier"]["difference"]) > abs(comps["logreg_vs_elo_logit_brier"]["difference"]):
            interp += (" A structural change to the benchmark (league offsets) improves accuracy more than the "
                       "machine-learning features do on top of it: modelling how leagues relate matters more "
                       "than adding predictors.")
    elif gain["ci95_low"] > 0:
        interp = ("Adding features made probabilities worse than a calibrated Elo in this test period, which "
                  "points to overfitting or features that are not stable over time.")
    else:
        interp = ("There is no evidence that the extra features improve on a calibrated Elo in this test period. "
                  "Most of the information in recent form and opponent strength appears to be captured by Elo "
                  "already. Any improvement over raw Elo should be read through the calibrated-Elo comparison, "
                  "which isolates calibration and side effects.")
    return {**base, "status": "completed", "status_note": None,
            "data": _data_section(db, game), "sample_period": mvs["elo"].periods,
            "results": {"model_table": [{"model": mvs[k].display_name, "model_key": k, **mvs[k].metrics["test"]}
                                        for k in ("baseline_50", "baseline_prevalence") if k in mvs] + table,
                        "experimental_models": exp, "comparisons": comps,
                        "calibration": {k: mvs[k].metrics["calibration"] for k in mvs},
                        "temporal_breakdown": lr["temporal_breakdown"], "league_breakdown": lr["league_breakdown"],
                        "elo_grid": [g for g in (mvs["elo"].hyperparameters.get("grid") or [])
                                     if g.get("k_league", 0) == mvs["elo"].hyperparameters.get("k_league", 0)],
                        "k_league_curve": sorted(
                            [g for g in (mvs["elo"].hyperparameters.get("grid") or [])
                             if g["k"] == mvs["elo"].hyperparameters.get("k")
                             and g["carryover_shrink"] == mvs["elo"].hyperparameters.get("carryover_shrink")],
                            key=lambda g: g.get("k_league", 0)),
                        "league_offsets": lo,
                        "coefficients": mvs["logreg"].hyperparameters.get("coefficients")},
            "findings": findings, "interpretation": interp}


def _trend(xs, ys) -> float | None:
    if len(xs) < 3:
        return None
    return float(np.polyfit(xs, ys, 1)[0])


def balance_report(db: Session, game: Game) -> dict:
    cb, _ = analysis(db, game, "competitive_balance")
    up, _ = analysis(db, game, "upset_rate")
    base = {"slug": "competitive-balance", "title": "Competitive Balance in Professional League of Legends",
            "research_question": "How unequal are regular-season results within leagues, and has balance changed "
                                 "over time?",
            "motivation": "The uncertainty-of-outcome hypothesis in sports economics links fan interest to "
                          "balanced competition. Esports leagues differ in format (franchised vs promotion and "
                          "relegation), which makes balance worth measuring rather than assuming.",
            "methodology": ["Unit of analysis: one league split (league + season + split), regular-season games only; "
                            "international events and playoffs excluded; teams with fewer than 5 games left out.",
                            "Share variable: each team's share of all regular-season wins in the split (not prize "
                            "money, which the source does not contain).",
                            "Noll-Scully ratio: sd of team win% divided by the sd expected if every game were a "
                            "coin flip (0.5/sqrt(games per team)). 1 = as balanced as chance; higher = less balanced.",
                            "HHI of win shares (normalised: 0 = equal shares, 1 = one team has every win), Gini "
                            "coefficient of wins and Lorenz curves of wins per split.",
                            "Title side: regular-season rank of each derived champion.",
                            "Upset rate: share of games won by the lower pre-game Elo team, by quarter."],
            "limitations": ["Short splits make Noll-Scully noisy; the ideal sd depends on games per team.",
                            "Leagues with unbalanced schedules (teams not all playing each other equally) violate "
                            "the round-robin assumption behind Noll-Scully.",
                            "Win share Gini has a floor and ceiling set by the schedule, not only by team quality."],
            "references": [REFERENCES[k] for k in ("rottenberg", "fort_quirk", "scully", "gini", "oe")]}
    if not cb or not cb.get("tournaments"):
        return {**base, "status": "proposed", "status_note": "Not yet conducted: no processed data.",
                "results": None, "findings": [], "interpretation": None}
    # Season years with few splits (e.g. a season that has only just started)
    # would dominate a trend line, so the trend uses years with >= 20 splits.
    by_year = [y for y in cb["by_year"] if y["n_tournaments"] >= 20]
    t = cb["tournaments"]
    ns = [x["noll_scully"] for x in t if x["noll_scully"] is not None]
    slope = _trend([y["year"] for y in by_year], [y["median_noll_scully"] for y in by_year])
    findings = [f"{cb['n_tournaments']} league splits analysed; median Noll-Scully ratio "
                f"{np.median(ns):.2f} (range {min(ns):.2f} to {max(ns):.2f})."]
    if slope is not None:
        findings.append(f"Linear trend in the median Noll-Scully ratio by season year: {slope:+.3f} per year over "
                        f"{len(by_year)} seasons with at least 20 splits ({by_year[0]['year']} to {by_year[-1]['year']}; "
                        "descriptive, not a significance test).")
    gi = [x["gini_wins"] for x in t if x.get("gini_wins") is not None]
    hh = [x["hhi_win_share_normalised"] for x in t if x.get("hhi_win_share_normalised") is not None]
    if gi and hh:
        findings.append(f"Median Gini of wins per split {np.median(gi):.3f}; median normalised HHI of win shares "
                        f"{np.median(hh):.4f}. A round-robin limits how unequal win shares can get, so these values "
                        "are small by construction; compare them across leagues and years, not with market HHI "
                        "thresholds.")
    pl, _ = analysis(db, game, "placements")
    if pl and pl.get("available"):
        findings.append(f"The best regular-season team went on to win the derived title in "
                        f"{pl['share_rs_first_wins_title']:.0%} of {pl['n_splits']} splits.")
    if up and up.get("available") and up.get("overall") is not None:
        findings.append(f"Across {up['n_games']} games after the Elo burn-in, the lower-rated team won "
                        f"{up['overall']:.1%} of the time.")
    interp = ("Values above 1 mean results are more spread out than chance alone would produce, i.e. real "
              "differences in team strength. How far above 1 is the measure of imbalance.")
    return {**base, "status": "completed", "status_note": None, "data": _data_section(db, game),
            "sample_period": cb["sample_period"],
            "results": {"competitive_balance": cb, "upset_rate": up, "placements": pl},
            "findings": findings, "interpretation": interp}


def evolution_report(db: Session, game: Game) -> dict:
    p, _ = analysis(db, game, "persistence")
    tr, _ = analysis(db, game, "season_trends")
    tc, _ = analysis(db, game, "team_consistency")
    base = {"slug": "evolution-of-team-performance",
            "title": "The Evolution of Team Performance in Professional League of Legends",
            "research_question": "How persistent is team strength from split to split, how has the spread of team "
                                 "performance changed across seasons, and which teams were consistently strong?",
            "motivation": "Persistence measures how durable competitive advantages are. Strong persistence "
                          "suggests stable organisations and rosters; weak persistence suggests results driven by "
                          "short-term factors or roster turnover. The seasonal spread shows whether the field "
                          "became more or less even.",
            "methodology": ["Persistence: regular-season win% of the same team id in consecutive splits of the same "
                            "league; Pearson and Spearman correlation and OLS slope.",
                            "Seasonal spread: per calendar year, quantiles (10th to 90th) of win% across teams "
                            "with 20+ games.",
                            "Consistency: mean and standard deviation of split win% for teams with 6+ splits.",
                            "Elo trajectories: rating after each game (Elo with league offsets)."],
            "limitations": ["A team id can carry a very different roster across splits.",
                            "Teams that are relegated or leave a league drop out (survivorship).",
                            "Win% has sampling noise, which biases the persistence slope toward zero (attenuation).",
                            "Calendar years differ in league coverage in the source, so trend lines mix changes in "
                            "competition with changes in coverage."],
            "references": [REFERENCES[k] for k in ("fort_quirk", "elo", "oe")]}
    if not p or not p.get("available"):
        return {**base, "status": "proposed",
                "status_note": "Not yet conducted: " + (p.get("reason") if p else "no processed data."),
                "results": None, "findings": [], "interpretation": None}
    findings = [f"{p['n_pairs']} team pairs across consecutive splits.",
                f"Correlation of win% between splits: Pearson {p['pearson']:.2f}, Spearman {p['spearman']:.2f}; "
                f"OLS slope {p['ols_slope']:.2f}."]
    years = [y for y in (tr or {}).get("by_year", []) if y.get("wp_p10") is not None and y["teams_20plus_games"] >= 50]
    if len(years) >= 2:
        a, b = years[0], years[-1]
        findings.append(f"Spread of team win% (90th minus 10th percentile, teams with 20+ games): "
                        f"{a['wp_p90'] - a['wp_p10']:.3f} in {a['year']} and {b['wp_p90'] - b['wp_p10']:.3f} in "
                        f"{b['year']} ({len(years)} years with 50+ such teams).")
    if tc and tc.get("teams"):
        strong = [t for t in tc["teams"] if t["splits"] >= 8]
        if strong:
            best = max(strong, key=lambda t: t["mean_wp"])
            findings.append(f"Highest mean split win% among teams with 8+ splits: {best['name']} ({best['league']}), "
                            f"{best['mean_wp']:.1%} over {best['splits']} splits (sd {best['sd_wp']:.3f}).")
    interp = (f"A slope of {p['ols_slope']:.2f} means a team 10 points above .500 in one split is expected to be "
              f"about {10 * p['ols_slope']:.1f} points above .500 in the next: "
              + ("strong carry-over." if p["ols_slope"] > 0.7 else
                 "partial regression toward the middle." if p["ols_slope"] > 0.3 else "weak carry-over.")
              + " Part of this regression is measurement noise from short splits, so true persistence is "
                "somewhat higher than the slope suggests.")
    return {**base, "status": "completed", "status_note": None, "data": _data_section(db, game),
            "sample_period": p["sample_period"],
            "results": {"persistence": p, "season_trends": tr, "team_consistency": tc},
            "findings": findings, "interpretation": interp}


def concentration_report(db: Session, game: Game) -> dict:
    tc, _ = analysis(db, game, "title_concentration")
    base = {"slug": "concentration-of-tournament-success",
            "title": "The Concentration of Tournament Success",
            "research_question": "How concentrated are league titles among teams?",
            "motivation": "Concentration of titles is the long-run counterpart to within-season balance, and a "
                          "standard lens from industrial organisation (HHI) applied to competitive success.",
            "methodology": ["Concentrated quantity: derived titles (winner of the last playoff game of each split).",
                            "HHI = sum of squared title shares among title winners; Lorenz curve of title counts.",
                            "Leagues with at least 4 splits that have playoff games in the data."],
            "limitations": ["Titles are derived from game records, not an official register; a third-place game "
                            "played after a final would be mislabelled.",
                            "HHI over winners only ignores teams that never won; a league where one team wins "
                            "every title gives HHI = 1 whatever the number of teams.",
                            "Prize money is not in the source data, so prize concentration is not analysed."],
            "references": [REFERENCES[k] for k in ("hirschman", "gini", "oe")]}
    if not tc or not tc.get("leagues"):
        return {**base, "status": "proposed",
                "status_note": "Not yet conducted: no league has at least 4 splits with playoffs in the data.",
                "results": None, "findings": [], "interpretation": None}
    L_all = tc["leagues"]
    # Extremes are reported only for leagues with at least 10 splits; with
    # 4-5 splits one team winning everything is common and says little.
    L = [r for r in L_all if r["n_tournaments_with_champion"] >= 10] or L_all
    most = max(L, key=lambda r: r["hhi_titles"])
    least = min(L, key=lambda r: r["hhi_titles"])
    findings = [f"{len(L_all)} leagues have at least 4 splits with playoffs; {len(L)} have at least 10, and the "
                f"comparisons below use those.",
                f"Most concentrated: {most['league']} (HHI {most['hhi_titles']:.2f}; {most['top_team']} holds "
                f"{most['top_team_titles']} of {most['n_tournaments_with_champion']} derived titles).",
                f"Least concentrated: {least['league']} (HHI {least['hhi_titles']:.2f}; "
                f"{least['distinct_champions']} different winners in {least['n_tournaments_with_champion']} splits)."]
    return {**base, "status": "completed", "status_note": None, "data": _data_section(db, game),
            "sample_period": tc["sample_period"], "results": tc, "findings": findings,
            "interpretation": "An HHI near 1/(number of distinct winners) means titles are spread evenly among "
                              "those who won; values near 1 mean one team dominates."}


REPORTS = {"can-machine-learning-beat-elo": ml_report, "competitive-balance": balance_report,
           "evolution-of-team-performance": evolution_report,
           "concentration-of-tournament-success": concentration_report}


def list_reports(db: Session, game: Game) -> list[dict]:
    out = []
    for slug, fn in REPORTS.items():
        r = fn(db, game)
        out.append({k: r.get(k) for k in ("slug", "title", "research_question", "status", "status_note")}
                   | {"n_findings": len(r.get("findings") or [])})
    return out


def get_report(db: Session, game: Game, slug: str) -> dict:
    if slug not in REPORTS:
        raise HTTPException(404, f"report '{slug}' not found")
    return REPORTS[slug](db, game)
