"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Card, ErrorState, Loading, PageHeader, Select, cx } from "@/components/ui/primitives";

/* Everything on this page is read from /experiments/walk-forward.json, which is
 * exported from a registry record by machine_learning/experiments/export_summary.py.
 * No number is written by hand here. */

type Metric = { n: number; brier: number; log_loss: number; accuracy: number; roc_auc: number | null; ece: number };
type WinComp = { model: string; reference: string; question: string; difference: number; ci95_low: number; ci95_high: number };
type PoolComp = {
  model: string; reference: string; question: string;
  brier_difference: number; brier_ci95_low: number; brier_ci95_high: number;
  log_loss_difference: number; log_loss_ci95_low: number; log_loss_ci95_high: number;
  windows_better: number; windows_ci_below_zero: number; window_sd: number | null;
};
type Summary = {
  experiment_id: string; created_at: string; data_fingerprint: string; code_sha256: string; git_commit: string | null;
  environment: { python: string; packages: Record<string, string | null> };
  design: { test_years: number[]; split_rule: string; eligibility: { burn_in_days: number; min_prior_games: number };
    selection_metric: string; bootstrap: { unit: string; n_window: number; n_pooled: number; seed: number };
    lineup_note: string; patch_early_days: number };
  features: { form: string[]; roster: { name: string; definition: string }[]; player: string[] };
  windows: { test_year: number; periods: Record<string, { n: number; start: string; end: string }>;
    chosen: Record<string, unknown>; metrics: Record<string, Metric>; comparisons: WinComp[] }[];
  pooled: { n: number; metrics: Record<string, Metric>; comparisons: PoolComp[] };
  patch_analysis: { group: string; n: number; elo_cal_brier: number; all_brier: number; difference: number; ci95_low: number; ci95_high: number }[];
};

const LABEL: Record<string, string> = {
  baseline: "Constant (blue-side rate)",
  elo_flat: "Flat Elo",
  elo_league: "Elo with league levels",
  elo_cal: "Calibrated Elo",
  form: "Logistic: form (published model)",
  form_continuity: "Form + lineup continuity",
  form_tenure: "Form + player tenure",
  form_player_exp: "Form + player experience",
  form_player_exp_prev: "Form + player experience (previous lineup)",
  player_cal_prev: "Calibrated player Elo (previous lineup)",
  prematch: "Pre-match: form + previous-lineup player data",
  form_roster: "Form + all roster features",
  player_cal: "Calibrated player Elo",
  all: "Form + roster + player Elo",
};
const MAIN = ["baseline", "elo_flat", "elo_league", "elo_cal", "form", "prematch", "form_roster", "player_cal", "all"];

const f4 = (x: number | null | undefined) => (x == null ? "–" : x.toFixed(4));
const signed = (x: number) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(4)}`;
const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

/** Horizontal interval plot: point and 95% CI, zero line. Negative = better. */
function Forest({ rows }: { rows: { label: string; d: number; lo: number; hi: number; note?: string }[] }) {
  const min = Math.min(...rows.map((r) => r.lo), 0);
  const max = Math.max(...rows.map((r) => r.hi), 0);
  const pad = (max - min) * 0.08 || 0.001;
  const lo = min - pad, hi = max + pad;
  const x = (v: number) => ((v - lo) / (hi - lo)) * 100;
  return (
    <div className="space-y-2" role="list">
      {rows.map((r) => (
        <div key={r.label} role="listitem" className="grid grid-cols-1 gap-1 sm:grid-cols-[minmax(0,17rem)_1fr_11.5rem] sm:items-center sm:gap-3">
          <div className="text-sm text-ink">{r.label}{r.note && <span className="block text-2xs text-ink-3">{r.note}</span>}</div>
          <div className="relative h-5" aria-label={`${r.label}: ${signed(r.d)}, 95% interval ${signed(r.lo)} to ${signed(r.hi)}`}>
            <div className="absolute inset-y-0 w-px bg-ink-3" style={{ left: `${x(0)}%` }} aria-hidden />
            <div className="absolute top-1/2 h-0.5 -translate-y-1/2" aria-hidden
              style={{ left: `${x(r.lo)}%`, width: `${Math.max(x(r.hi) - x(r.lo), 0.5)}%`, background: r.hi < 0 ? "#2BD67B" : "#9AA0A9" }} />
            <div className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full" aria-hidden
              style={{ left: `${x(r.d)}%`, background: r.hi < 0 ? "#2BD67B" : "#F5D547" }} />
          </div>
          <div className="num whitespace-nowrap text-right text-xs text-ink-2">{signed(r.d)} <span className="text-ink-3">[{signed(r.lo)}, {signed(r.hi)}]</span></div>
        </div>
      ))}
      <p className="pt-1 text-2xs text-ink-3">Change in Brier score, model minus reference. Left of the line = model is better. Bars are 95% intervals from a series-clustered bootstrap; green = whole interval below zero.</p>
    </div>
  );
}

export default function ExperimentsView() {
  const q = useQuery<Summary>({
    queryKey: ["experiments", "walk-forward"],
    queryFn: async () => {
      const r = await fetch("/experiments/walk-forward.json", { cache: "no-store" });
      if (!r.ok) throw new Error(`Experiment summary not found (${r.status})`);
      return r.json();
    },
    staleTime: Infinity,
  });
  const [comp, setComp] = useState(0);

  if (q.isLoading) return <Loading label="Loading experiment results" />;
  if (q.error || !q.data) return <ErrorState error={(q.error as Error) || new Error("No data")} />;
  const s = q.data;
  const years = s.windows.map((w) => w.test_year);
  const c = s.pooled.comparisons[comp] ?? s.pooled.comparisons[0];
  const best = (m: Record<string, Metric>) => Math.min(...MAIN.map((k) => m[k]?.brier ?? 1));

  return (
    <>
      <PageHeader eyebrow="Research" title="Experiments"
        description={<>Walk-forward test over {years.length} years: does more information beat Elo, year after year? Models are re-tuned and refit for every year and scored on games they never saw. New to the terms? See the <Link className="link" href="/faq">FAQ and glossary</Link>.</>} />

      <Card className="mb-3 border-l-2 border-l-cyan" title="Read this first">
        <p className="text-sm leading-relaxed text-ink-2">
          Most roster and player-Elo features use the five players who actually played. That lineup is visible when the game starts (in the draft), but usually not days before. Models marked <b className="text-ink">previous lineup</b> or <b className="text-ink">pre-match</b> use only the players from each team&apos;s last game, so they can be used before match day. The published model on the <Link className="link" href="/predictions">prediction lab</Link> does not use player data yet.
        </p>
      </Card>

      <Card title="What each step adds" eyebrow={`Pooled over ${years[0]}–${years[years.length - 1]} · ${s.pooled.n.toLocaleString()} test games`} className="mb-3">
        <Forest rows={s.pooled.comparisons.map((p) => ({
          label: p.question, d: p.brier_difference, lo: p.brier_ci95_low, hi: p.brier_ci95_high,
          note: `better in ${p.windows_better}/${years.length} years`,
        }))} />
      </Card>

      <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr]">
        <Card title="Brier score by test year" eyebrow="Lower is better">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-ink-3">
                <th className="py-1.5 pr-3 font-normal">Model</th>
                {years.map((y) => <th key={y} className="num px-2 text-right font-normal">{y}</th>)}
                <th className="num pl-2 text-right font-normal">Pooled</th>
              </tr></thead>
              <tbody>
                {MAIN.map((m) => (
                  <tr key={m} className="border-t border-line">
                    <td className="py-1.5 pr-3 text-ink">{LABEL[m]}</td>
                    {s.windows.map((w) => (
                      <td key={w.test_year} className={cx("num px-2 text-right", w.metrics[m]?.brier === best(w.metrics) ? "text-emerald" : "text-ink-2")}>{f4(w.metrics[m]?.brier)}</td>
                    ))}
                    <td className={cx("num pl-2 text-right", s.pooled.metrics[m]?.brier === best(s.pooled.metrics) ? "text-emerald" : "text-ink")}>{f4(s.pooled.metrics[m]?.brier)}</td>
                  </tr>
                ))}
                <tr className="border-t border-line text-ink-3">
                  <td className="py-1.5 pr-3">Test games</td>
                  {s.windows.map((w) => <td key={w.test_year} className="num px-2 text-right">{w.periods.test.n.toLocaleString()}</td>)}
                  <td className="num pl-2 text-right">{s.pooled.n.toLocaleString()}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-2xs text-ink-3">Green = best model that year. Pooled accuracy: calibrated Elo {pct(s.pooled.metrics.elo_cal.accuracy)}, form {pct(s.pooled.metrics.form.accuracy)}, pre-match {pct(s.pooled.metrics.prematch.accuracy)}, everything {pct(s.pooled.metrics.all.accuracy)}.</p>
        </Card>

        <Card title="Year by year" actions={
          <Select label="Comparison" value={String(comp)} onChange={(v) => setComp(+v)}
            options={s.pooled.comparisons.map((p, i) => ({ value: String(i), label: p.question }))} />
        }>
          <p className="mb-3 text-xs text-ink-3">{LABEL[c.model]} vs {LABEL[c.reference]}. Spread across years (SD): <span className="num">{c.window_sd?.toFixed(4) ?? "–"}</span></p>
          <Forest rows={s.windows.map((w) => {
            const x = w.comparisons.find((k) => k.model === c.model && k.reference === c.reference)!;
            return { label: String(w.test_year), d: x.difference, lo: x.ci95_low, hi: x.ci95_high };
          })} />
        </Card>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <Card title="Early in a patch vs later" eyebrow={`First ${s.design.patch_early_days} days after a patch appears`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-ink-3"><th className="py-1.5 font-normal">Games</th><th className="num text-right font-normal">n</th><th className="num text-right font-normal">Cal. Elo</th><th className="num text-right font-normal">Everything</th><th className="num text-right font-normal">Difference [95%]</th></tr></thead>
              <tbody>{s.patch_analysis.map((p) => (
                <tr key={p.group} className="border-t border-line">
                  <td className="py-1.5 text-ink">{p.group}</td><td className="num text-right text-ink-2">{p.n.toLocaleString()}</td>
                  <td className="num text-right text-ink-2">{f4(p.elo_cal_brier)}</td><td className="num text-right text-ink-2">{f4(p.all_brier)}</td>
                  <td className="num text-right text-ink-2">{signed(p.difference)} <span className="text-ink-3">[{signed(p.ci95_low)}, {signed(p.ci95_high)}]</span></td>
                </tr>))}</tbody>
            </table>
          </div>
          <p className="mt-2 text-2xs text-ink-3">Brier score. A patch&apos;s start is the first game on that patch in the data.</p>
        </Card>

        <Card title="Roster features">
          <dl className="space-y-2 text-sm">
            {s.features.roster.map((r) => (
              <div key={r.name}><dt className="num text-ink">{r.name}</dt><dd className="text-ink-2">{r.definition}</dd></div>
            ))}
            <div><dt className="num text-ink">player_elo_diff</dt><dd className="text-ink-2">Blue minus red player-level Elo: league level plus the mean rating of the five players who played.</dd></div>
            <div><dt className="num text-ink">player_elo_prev_diff</dt><dd className="text-ink-2">The same, rated on each team&apos;s previous lineup (pre-match).</dd></div>
          </dl>
          <p className="mt-2 text-2xs text-ink-3">All computed from strictly earlier games; tested by changing future lineups and results and checking that earlier values do not move.</p>
        </Card>
      </div>

      <Card title="Reproducibility" className="mt-3">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          {[
            ["Experiment", s.experiment_id],
            ["Run at", new Date(s.created_at).toUTCString()],
            ["Data fingerprint", s.data_fingerprint],
            ["Code checksum", s.code_sha256 + (s.git_commit ? ` · commit ${s.git_commit.slice(0, 7)}` : "")],
            ["Split", s.design.split_rule],
            ["Eligible games", `after ${s.design.eligibility.burn_in_days}-day burn-in; both teams ≥ ${s.design.eligibility.min_prior_games} earlier games`],
            ["Tuning", `${s.design.selection_metric}, per year`],
            ["Intervals", `${s.design.bootstrap.unit}; ${s.design.bootstrap.n_window} resamples per year, ${s.design.bootstrap.n_pooled} pooled; seed ${s.design.bootstrap.seed}`],
            ["Environment", `Python ${s.environment.python}; ${Object.entries(s.environment.packages).map(([k, v]) => `${k} ${v}`).join(", ")}`],
            ["Re-run", "python -m machine_learning.experiments.walk_forward"],
          ].map(([k, v]) => (
            <div key={k}><dt className="text-2xs uppercase tracking-wide text-ink-3">{k}</dt><dd className="num break-words text-ink-2">{v}</dd></div>
          ))}
        </dl>
      </Card>
    </>
  );
}
