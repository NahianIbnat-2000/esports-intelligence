"use client";

import Link from "next/link";
import { Card, PageHeader } from "@/components/ui/primitives";

const SECTIONS: { title: string; items: string[] }[] = [
  { title: "Unit of analysis", items: [
    "One match = one single game (one map), identified by the Oracle's Elixir gameid. Best-of series are not reconstructed in version 1.0.",
    "One tournament = one league split (league + year + split) from the source.",
    "Each game has two team rows and normally ten player rows. Player rows are never counted as games.",
  ] },
  { title: "Cleaning and validation", items: [
    "Rows are excluded only for a recorded reason (missing game id, date or team, invalid result, unidentifiable row type, duplicates). Every exclusion is written to data/reports/exclusions.csv.",
    "A game is accepted only with exactly two team rows (one Blue, one Red), two different teams and exactly one winner.",
    "Missing statistics stay missing (null). They are never replaced with zero, and averages use only games where the metric exists.",
    "Teams and players are keyed by source ids; a name is used only when the id is missing, and such records are flagged.",
  ] },
  { title: "Elo ratings", items: [
    "Expected score E_A = 1 / (1 + 10^((R_B - R_A)/400)); update R' = R + K (S - E) after every game, in time order.",
    "All teams start at 1500. No decay during inactivity. At a new calendar year ratings can shrink toward 1500 (carry-over).",
    "K-factor and carry-over are chosen by validation log loss from a fixed grid; the sensitivity table is published in the research report.",
  ] },
  { title: "Prediction models and evaluation", items: [
    "Target: blue side wins a single game. Models: Elo, calibrated Elo (logistic on Elo difference), logistic regression on six pre-specified pre-game features.",
    "Chronological split: 70% train, 15% validation, 15% test by date after a 90-day burn-in. Both teams need at least 5 earlier games.",
    "Every feature uses only games with an earlier timestamp. No post-game statistic is used. Scaling is fitted on training data inside the model pipeline.",
    "Metrics: accuracy, precision, recall, ROC-AUC, Brier score, log loss, reliability diagrams and paired bootstrap intervals on identical test games.",
  ] },
  { title: "Economic indicators", items: [
    "HHI = sum of squared shares; normalised HHI = (HHI - 1/N)/(1 - 1/N). Gini coefficient from the sorted values. Lorenz curve of cumulative shares.",
    "Noll-Scully = sd of win% / (0.5 / sqrt(games per team)); 1 means as balanced as coin flips.",
    "Each indicator states what is being concentrated (wins, derived titles). Prize money is not in the source and is never estimated.",
  ] },
];

export default function MethodologyView() {
  return (
    <>
      <PageHeader eyebrow="Documentation" title="Methodology" description="How records are cleaned, how ratings and models are built, and what the indicators mean. The full text is in docs/methodology.md." />
      <div className="grid gap-4 lg:grid-cols-2">
        {SECTIONS.map((s) => (
          <Card key={s.title} title={s.title}>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-ink-2">{s.items.map((i) => <li key={i}>{i}</li>)}</ul>
          </Card>
        ))}
        <Card title="Data status labels">
          <ul className="space-y-2 text-sm text-ink-2">
            <li><b className="text-ink">Active</b>: verified live data available (none in version 1.0).</li>
            <li><b className="text-ink">Historical</b>: imported historical files.</li>
            <li><b className="text-ink">Integration pending</b>: adapter built, provider not connected.</li>
            <li><b className="text-ink">Unavailable</b>: required data not present.</li>
            <li><b className="text-ink">Demo</b>: illustrative content, always labelled (not used in this release).</li>
          </ul>
          <p className="mt-3 text-xs text-ink-3">See <Link className="link" href="/data-sources">data sources</Link> for provenance of every imported file.</p>
        </Card>
      </div>
    </>
  );
}
