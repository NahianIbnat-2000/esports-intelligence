"use client";

import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { Bars, Reliability, ScatterPlot, TimeLine } from "@/components/charts/charts";
import { Breadcrumbs, Card, DataState, PageHeader, SourceNote, StatusBadge } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import type { CalibrationBin } from "@/lib/api";
import { fmtDate, fmtInt, fmtNum, fmtPct } from "@/lib/format";

interface Report {
  slug: string; title: string; status: string; status_note: string | null; research_question: string; motivation: string;
  methodology: string[]; limitations: string[]; references: string[]; findings: string[]; interpretation: string | null;
  data?: { source: string; files: { filename: string; sha256: string; coverage_start: string | null; coverage_end: string | null; rows_accepted: number | null }[] };
  sample_period?: Record<string, unknown>;
  results: Record<string, unknown> | null;
}

function Section({ n, title, children }: { n: string; title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line py-6">
      <h2 className="mb-3 flex items-baseline gap-3 text-lg font-semibold"><span className="num text-sm text-cyan">{n}</span>{title}</h2>
      <div className="max-w-3xl text-sm leading-relaxed text-ink-2">{children}</div>
    </section>
  );
}

export default function ReportView() {
  const { slug } = useParams<{ slug: string }>();
  const q = useApi<Report>(`/research/${slug}`, { game: "lol" });
  return (
    <>
      <Breadcrumbs items={[{ label: "Research", href: "/research" }, { label: q.data?.data?.title || slug }]} />
      <DataState query={q}>
        {(r, meta) => (
          <article>
            <PageHeader eyebrow="Research report" title={r.title} description={r.research_question}>
              <div className="flex flex-col items-end gap-1"><StatusBadge status={r.status} /><span className="text-2xs text-ink-3">Generated {fmtDate(meta.generated_at)}</span></div>
            </PageHeader>
            {r.status === "proposed" && <p className="mb-4 rounded-md border border-violet/30 bg-violet/5 p-3 text-sm text-violet">Proposed research. {r.status_note} No results are shown until the analysis has been run on real data.</p>}
            <Section n="1" title="Research question"><p>{r.research_question}</p></Section>
            <Section n="2" title="Motivation"><p>{r.motivation}</p></Section>
            <Section n="3" title="Data and sample">
              <p>{r.data?.source || "Oracle's Elixir professional League of Legends match data."}</p>
              {r.data?.files?.length ? (
                <ul className="mt-2 list-disc pl-5">{r.data.files.map((f) => <li key={f.sha256}><span className="font-mono text-xs">{f.filename}</span> (sha256 {f.sha256}...), {fmtDate(f.coverage_start)} to {fmtDate(f.coverage_end)}, {fmtInt(f.rows_accepted)} rows accepted</li>)}</ul>
              ) : <p className="mt-2">No files imported yet.</p>}
              {r.sample_period && <SamplePeriod p={r.sample_period} />}
            </Section>
            <Section n="4" title="Methodology"><ul className="list-disc space-y-1.5 pl-5">{r.methodology.map((m) => <li key={m}>{m}</li>)}</ul></Section>
            <Section n="5" title="Results">
              {r.status !== "completed" ? <p>Not available: the analysis has not been run.</p> : (
                <>
                  <ul className="mb-5 space-y-2">{r.findings.map((f) => <li key={f} className="border-l-2 border-cyan/50 pl-3 text-ink">{f}</li>)}</ul>
                  <ResultCharts slug={r.slug} results={r.results} />
                </>
              )}
            </Section>
            <Section n="6" title="Interpretation"><p>{r.interpretation || "Not available until results exist."}</p></Section>
            <Section n="7" title="Limitations"><ul className="list-disc space-y-1.5 pl-5">{r.limitations.map((m) => <li key={m}>{m}</li>)}</ul></Section>
            <Section n="8" title="References"><ol className="list-decimal space-y-1.5 pl-5 text-xs">{r.references.map((m) => <li key={m}>{m}</li>)}</ol></Section>
            <SourceNote meta={meta} />
          </article>
        )}
      </DataState>
    </>
  );
}

function SamplePeriod({ p }: { p: Record<string, unknown> }) {
  const parts = ["train", "validation", "test"].filter((k) => p[k] && typeof p[k] === "object") as ("train" | "validation" | "test")[];
  if (parts.length === 0) {
    const sp = p as { start?: string; end?: string };
    return sp.start ? <p className="mt-2">Sample period: {fmtDate(sp.start)} to {fmtDate(sp.end)}.</p> : null;
  }
  return (
    <div className="mt-3 overflow-x-auto"><table className="w-full max-w-lg"><thead className="border-b border-line"><tr><th className="th">Split</th><th className="th">Period</th><th className="th text-right">Games</th><th className="th text-right">Blue win %</th></tr></thead>
      <tbody>{parts.map((k) => { const s = p[k] as { n: number; start: string; end: string; blue_win_rate: number }; return (
        <tr key={k} className="border-b border-line-soft"><td className="td capitalize">{k}</td><td className="td">{fmtDate(s.start)} to {fmtDate(s.end)}</td><td className="td num text-right">{fmtInt(s.n)}</td><td className="td num text-right">{fmtPct(s.blue_win_rate)}</td></tr>); })}</tbody></table></div>
  );
}

function ResultCharts({ slug, results }: { slug: string; results: Record<string, unknown> | null }) {
  if (!results) return null;
  if (slug === "can-machine-learning-beat-elo") {
    const table = results.model_table as { model: string; brier: number; log_loss: number; roc_auc: number; accuracy: number }[];
    const cal = results.calibration as Record<string, CalibrationBin[]>;
    const grid = (results.elo_grid || []) as { k: number; carryover_shrink: number; validation_log_loss: number }[];
    const shrinks = Array.from(new Set(grid.map((g) => g.carryover_shrink)));
    const ks = Array.from(new Set(grid.map((g) => g.k))).sort((a, b) => a - b);
    const sens = ks.map((k) => Object.fromEntries([["k", String(k)], ...shrinks.map((s) => [`s${s}`, grid.find((g) => g.k === k && g.carryover_shrink === s)?.validation_log_loss])]));
    const kl = ((results.k_league_curve || []) as { k_league: number; validation_log_loss: number }[]).map((g) => ({ k_league: String(g.k_league), loss: g.validation_log_loss }));
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Test-period scores" className="lg:col-span-2">
          <div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th">Model</th><th className="th text-right">Brier</th><th className="th text-right">Log loss</th><th className="th text-right">ROC-AUC</th><th className="th text-right">Accuracy</th></tr></thead>
            <tbody>{table.map((m) => <tr key={m.model} className="border-b border-line-soft"><td className="td">{m.model}</td><td className="td num text-right">{fmtNum(m.brier, 4)}</td><td className="td num text-right">{fmtNum(m.log_loss, 4)}</td><td className="td num text-right">{fmtNum(m.roc_auc, 3)}</td><td className="td num text-right">{fmtPct(m.accuracy)}</td></tr>)}</tbody></table></div>
        </Card>
        <Card title="Reliability diagram"><Reliability models={Object.entries(cal).map(([k, bins]) => ({ label: k, bins }))} height={300} /></Card>
        <Card title="Elo sensitivity: validation log loss by K-factor" info="Lines are season carry-over shrinkage values. The selected configuration has the lowest validation log loss.">
          <TimeLine data={sens} x="k" height={300} series={shrinks.map((s) => ({ key: `s${s}`, label: `shrink ${s}` }))} />
        </Card>
        {kl.length > 1 && (
          <Card title="League offsets: validation log loss by k_league" className="lg:col-span-2" info="k_league = 0 is flat Elo. Larger values let league levels move more after each game between leagues.">
            <TimeLine data={kl} x="k_league" height={240} series={[{ key: "loss", label: "Validation log loss" }]} />
          </Card>
        )}
      </div>
    );
  }
  if (slug === "competitive-balance") {
    const cb = results.competitive_balance as { by_year: { year: number; n_tournaments: number; median_noll_scully: number; median_gini_wins: number }[] };
    const pl = results.placements as { available: boolean; distribution: { rank: string; share: number }[] } | null;
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Median Noll-Scully ratio and Gini of wins by season"><TimeLine data={cb.by_year.filter((y) => y.n_tournaments >= 20)} x="year" series={[{ key: "median_noll_scully", label: "Median Noll-Scully" }, { key: "median_gini_wins", label: "Median Gini of wins" }]} reference={{ y: 1, label: "chance level (Noll-Scully)" }} /></Card>
        {pl?.available && <Card title="Regular-season rank of the champion"><Bars data={pl.distribution} x="rank" series={[{ key: "share", label: "Share of splits" }]} yFormat={(v) => fmtPct(v, 0)} /></Card>}
        <p className="text-2xs text-ink-3 lg:col-span-2">Seasons with at least 20 splits. Lorenz curves per split and league comparisons: Analytics, module C.</p>
      </div>
    );
  }
  if (slug === "evolution-of-team-performance") {
    const p = results.persistence as { scatter_sample: Record<string, unknown>[] };
    const tr = results.season_trends as { by_year: Record<string, number>[] } | null;
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Win % in split t vs t+1 (sample of pairs)"><ScatterPlot data={p.scatter_sample || []} x="wp_t" y="wp_t1" xLabel="Win % t" yLabel="Win % t+1" diagonal format={(v) => fmtPct(v, 0)} /></Card>
        {tr && <Card title="Spread of team win % by year (10th, median, 90th percentile)"><TimeLine data={tr.by_year} x="year" yFormat={(v) => fmtPct(v, 0)} series={[{ key: "wp_p90", label: "90th" }, { key: "wp_p50", label: "Median" }, { key: "wp_p10", label: "10th" }]} /></Card>}
        <p className="text-2xs text-ink-3 lg:col-span-2">Elo trajectories of individual teams: Analytics, module A, and each team page.</p>
      </div>
    );
  }
  if (slug === "concentration-of-tournament-success") {
    const leagues = (results.leagues || []) as Record<string, unknown>[];
    return <Card title="HHI of derived titles by league"><Bars data={leagues} x="league" series={[{ key: "hhi_titles", label: "HHI" }]} layout="vertical" height={Math.max(220, leagues.length * 28)} /></Card>;
  }
  return null;
}
