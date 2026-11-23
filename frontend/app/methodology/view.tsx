"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Card, PageHeader } from "@/components/ui/primitives";

/* Kept in line with docs/methodology.md and the code it names. */

type Section = { title: string; items: ReactNode[]; wide?: boolean };

const SECTIONS: Section[] = [
  { title: "Unit of analysis", items: [
    "One match = one single game (one map), identified by the Oracle's Elixir gameid. Ratings, features and predictions are all made per game. The target is whether the blue side wins.",
    "One tournament = one league split (league + year + split) from the source.",
    "Each game has two team rows and normally ten player rows. Player rows are never counted as games.",
  ] },
  { title: "Cleaning and validation", items: [
    "Rows are excluded only for a recorded reason (missing game id, date or team, invalid result, unidentifiable row type, duplicates). Every exclusion is written to data/reports/exclusions.csv.",
    "A game is accepted only with exactly two team rows (one Blue, one Red), two different teams, one date and exactly one winner.",
    "Exact duplicate rows are dropped (one kept). Conflicting rows with the same gameid and participantid are dropped entirely and reported.",
    "Missing statistics stay missing (null). They are never replaced with zero, and averages use only games where the metric exists.",
    "Teams and players are keyed by source ids; a name is used only when the id is missing, and such records are flagged.",
  ] },
  { title: "Series reconstruction", items: [
    "The source has no series identifier, so best-of series are rebuilt for display on the match centre.",
    "Games between the same two teams in the same tournament are one series if they are less than 3 hours apart, or up to 12 hours apart when the source's game number is exactly one higher (long pauses inside a best-of-5). A game the source numbers as game 1 always starts a new series.",
    "The series score counts game wins. The format (best of 1, 3 or 5) is not in the source and is not inferred.",
    "Models still work per game. For uncertainty intervals, games from the same series (same tournament, same two teams, same UTC day) are resampled together.",
    "Forecasts are made before each game, not before the series: ratings and features update after every game, so the forecast for game 2 already knows game 1. With every input frozen before the series starts, the player-experience gain is the same (−0.0044 Brier, five test years).",
  ] },
  { title: "Features (fixed before evaluation)", items: [
    "elo_diff: blue pre-game Elo minus red pre-game Elo.",
    "recent_wr_diff: difference in (wins + 1)/(n + 2) over each team's last 10 games.",
    "hist_wr_diff: difference in (wins + 2.5)/(n + 5) over all earlier games.",
    "opp_strength_diff: difference in the mean pre-game Elo of each team's last 10 opponents.",
    "experience_diff: difference in log(1 + earlier games).",
    "elo_diff_x_intl: elo_diff times 1 if the game is at Worlds, MSI, First Stand or the Esports World Cup.",
    "Every feature uses only games with a strictly earlier timestamp. No statistic from the game itself is used. The list was not tuned on test results.",
  ] },
  { title: "Models and validation", items: [
    "Elo: the expected score, no fitted parameters.",
    "Calibrated Elo: logistic regression on elo_diff only. The intercept estimates the blue-side advantage.",
    "Logistic regression: the six features, standardised inside a scikit-learn pipeline fitted on training rows; L2 strength C chosen on validation.",
    "Gradient boosting and random forest were also tried. They did not beat logistic regression on validation and were not deployed.",
    "Split by date: 70% train, 15% validation, 15% test of eligible games, after a 90-day burn-in. Eligible = both teams have at least 5 earlier games. All models are scored on the same test games.",
    "Logistic models are refit on train + validation and scored once on test. The test period is never used for fitting or tuning.",
    "Leakage checks: future results are flipped in tests to confirm past features do not change, the scaler is fitted on training rows only, one row per gameid, and the date split is tested for overlap.",
  ] },
  { title: "Evaluation", items: [
    "Two constant baselines with no information about the teams are reported next to every model: a flat 50% and the blue-side win rate of the earlier data.",
    "Metrics: accuracy, precision and recall (0.5 threshold, positive = blue win), ROC-AUC, Brier score, log loss, reliability diagram (10 equal-width bins), confusion matrix, and breakdowns by quarter and league.",
    "Model differences use a paired cluster bootstrap with 2,000 resamples of per-game loss differences, resampling whole series. Results are also checked with tournament clusters.",
    "Statistical significance and practical size are reported separately: a difference can be clearly real and still too small to matter.",
  ] },
  { title: "Competitive economics", items: [
    "HHI = sum of squared shares; normalised HHI = (HHI - 1/N)/(1 - 1/N). Applied to shares of regular-season wins and of derived titles.",
    "Gini coefficient of wins per team; Lorenz curve of cumulative title shares.",
    "Noll-Scully = sd of win% / (0.5 / sqrt(games per team)); 1 means as balanced as coin flips.",
    "Persistence: correlation and OLS slope of team win% in consecutive splits.",
    "Upset rate: share of games won by the team with the lower pre-game Elo.",
    "Each indicator states what is being concentrated. Prize money is not in the source and is never estimated.",
  ] },
  { title: "Rankings and comparisons", items: [
    "Current Elo = a team's rating after its last game. Top-team lists include teams with at least 10 games and a game in the last 180 days of the data.",
    "Without a league filter, only teams from leagues with at least 50 games at Worlds, MSI, First Stand or the Esports World Cup in the last three years are ranked together, because Elo points move between leagues only through those games.",
    "Top performer on match pages: the player on the winning team with the highest KDA, (kills + assists) / max(deaths, 1). Player statistics are compared with the median of the same role in the same tournament.",
  ] },
];

const ELO_TABLE: [string, ReactNode][] = [
  ["Expected score", <>E<sub>A</sub> = 1 / (1 + 10<sup>(R<sub>B</sub> − R<sub>A</sub>)/400</sup>)</>],
  ["Update", <>R′<sub>A</sub> = R<sub>A</sub> + K (S<sub>A</sub> − E<sub>A</sub>), after every game in time order; games with the same timestamp are one batch</>],
  ["Rating", "League level + team component. With no league levels this is plain (flat) Elo."],
  ["League levels", <>Move only in games between teams from different leagues, by k<sub>league</sub> (S − E). Games inside a league move only the team components.</>],
  ["New teams", "Start at their league's level. Every league starts at 1500."],
  ["Home league", "The league a team has played most domestic games in so far. If it changes, the team component is re-based so the total rating does not jump."],
  ["Inactive teams", "No decay."],
  ["New calendar year", <>Team component shrinks toward the league level: r ← (1 − s) r</>],
  ["Side", "No side term in Elo. The calibrated model estimates the blue-side effect."],
  ["Tuning", <>K ∈ {"{8 … 80}"}, s ∈ {"{0, 0.25, 0.5, 0.75}"}, k<sub>league</sub> ∈ {"{0, 2, 4, 8, 16, 32}"}; coordinate search on validation log loss (K × s, then k<sub>league</sub>, then K × s again). The full grid is in the research report.</>],
];

export default function MethodologyView() {
  return (
    <>
      <PageHeader eyebrow="Documentation" title="Methodology"
        description={<>How records are cleaned, how ratings and models are built, and what the indicators mean. The full text is in docs/methodology.md. New to esports or these terms? Start with the <Link className="link" href="/faq">FAQ and glossary</Link>.</>} />

      <Card title="Elo ratings with league levels" className="mb-3"
        info="Plain-language version with an interactive example: FAQ and glossary page.">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <tbody>
              {ELO_TABLE.map(([k, v]) => (
                <tr key={k} className="border-b border-line last:border-0 align-top">
                  <th scope="row" className="w-40 whitespace-nowrap py-2 pr-4 text-left font-semibold text-ink">{k}</th>
                  <td className="py-2 leading-relaxed text-ink-2">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-ink-3">
          Why league levels: teams mostly play inside their own league, so on one flat scale a team that dominates a small league can rank above the best teams in Korea or China. Known limit: a league&apos;s level is only as well measured as the number of games it plays against other leagues. See <Link className="link" href="/faq#elo-leagues">the FAQ</Link> for a plain explanation.
        </p>
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        {SECTIONS.map((s) => (
          <Card key={s.title} title={s.title}>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-ink-2">{s.items.map((i, n) => <li key={n}>{i}</li>)}</ul>
          </Card>
        ))}
        <Card title="Data status labels">
          <ul className="space-y-2 text-sm text-ink-2">
            <li><b className="text-ink">Active</b>: verified live data available (none at present).</li>
            <li><b className="text-ink">Historical</b>: imported historical files.</li>
            <li><b className="text-ink">Integration pending</b>: adapter built, provider not connected (VALORANT, CS2).</li>
            <li><b className="text-ink">Unavailable</b>: required data not present.</li>
            <li><b className="text-ink">Demo</b>: illustrative content, always labelled (not used in this release).</li>
          </ul>
          <p className="mt-3 text-xs text-ink-3">See <Link className="link" href="/data-sources">data sources</Link> for provenance of every imported file.</p>
        </Card>
        <Card title="Known limits">
          <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-ink-2">
            <li>Series are rebuilt from game times and can be wrong in rare cases.</li>
            <li>Ratings are only comparable between leagues that play each other often.</li>
            <li>Models are fixed at the start of the test period and there is one test period, so results are one look at the future, not a guarantee.</li>
            <li>No roster, patch or draft information is used in predictions.</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
