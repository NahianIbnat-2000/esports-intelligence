"use client";

import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle } from "lucide-react";
import { Bars, Curves, Reliability, TimeLine } from "@/components/charts/charts";
import { GAMES, useGame } from "@/components/providers";
import { EntityPicker } from "@/components/ui/entity-picker";
import { GameSwitch } from "@/components/ui/game-gate";
import { Card, DataState, EmptyState, ErrorState, PageHeader, Pagination, Select, SourceNote, cx } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import { apiPost, type Comparison, type ModelInfo } from "@/lib/api";
import { CHART } from "@/lib/chart-theme";
import { fmtDate, fmtDateTime, fmtInt, fmtNum, fmtPct, fmtSigned } from "@/lib/format";

interface PredRes {
  team_a: { slug: string; name: string; elo: number; games_before: number; wins_before: number; last_game: string | null; recent_results: number[] };
  team_b: PredRes["team_a"];
  as_of: string; team_a_side: string; context: string;
  predictions: { model_key: string; display_name: string; version: string; status: string; prob_team_a: number | null; prob_team_b: number | null; reason: string | null }[];
  inputs: { features_team_a_on_blue: Record<string, number>; feature_note: string };
  generated_at: string; caveats: string[];
  explanation?: {
    elo_difference_a_minus_b: number;
    recent_form: { team_a: { games: number; wins: number }; team_b: { games: number; wins: number } };
    head_to_head_before_date: { games: number; wins_a: number; wins_b: number; last_meeting: string | null; note: string };
    side_advantage: { blue_win_prob_equal_teams: number; applied: string; note: string } | null;
    logreg_contributions: { orientation: string; intercept: number; logit: number; probability_team_a_on_blue: number; note: string;
      features: { feature: string; value: number; standardised: number; contribution_log_odds: number }[] } | null;
    summary: string[];
  };
}

function nextDay(iso: string) {
  const d = new Date(iso);
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

export default function PredictionsView() {
  const { game } = useGame();
  const models = useApi<ModelInfo[]>("/predictions/models", { game });
  return (
    <>
      <PageHeader index="05" eyebrow="Predictions" title="Match prediction laboratory"
        description="Out-of-sample win probabilities for a single game from three models: an Elo baseline, a calibrated Elo, and a logistic regression on pre-game features. Probabilities express uncertainty; they do not guarantee results.">
        <GameSwitch />
      </PageHeader>
      <DataState query={models} gameName={GAMES.find((g) => g.slug === game)?.name}>
        {(ms, meta) => {
          if (meta.data_status !== "available") {
            return <EmptyState title="Predictions are currently unavailable" icon={<AlertTriangle size={20} className="text-amber" />}>
              {ms[0]?.metrics?.reason || "Models have not been trained and evaluated yet."}</EmptyState>;
          }
          return <Lab models={ms} meta={meta} />;
        }}
      </DataState>
    </>
  );
}

function Lab({ models, meta }: { models: ModelInfo[]; meta: import("@/lib/api").Meta }) {
  const elo = models.find((m) => m.model_key === "elo")!;
  const valEnd = String(elo.periods?.validation_end || "");
  const dataEnd = String(elo.periods?.data_end || "");
  const minDate = valEnd ? nextDay(valEnd) : "";
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [asOf, setAsOf] = useState("");
  const [side, setSide] = useState("unknown");
  const [context, setContext] = useState("domestic");
  useEffect(() => { if (!asOf && dataEnd) setAsOf(nextDay(dataEnd)); }, [dataEnd, asOf]);
  const mut = useMutation<PredRes, Error>({
    mutationFn: () => apiPost<PredRes>("/predictions", { game: "lol", team_a: a, team_b: b, as_of: asOf, team_a_side: side, context }),
  });
  const submit = (e: FormEvent) => { e.preventDefault(); mut.mutate(); };
  const test = elo.periods?.test as { n: number; start: string; end: string } | undefined;

  return (
    <div className="space-y-6">
      <Card eyebrow="Request" title="Predict a single game">
        <form onSubmit={submit} className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <div className="xl:col-span-2"><EntityPicker kind="teams" label="Team A" value={a} onChange={(s) => setA(s)} minMatches={5} /></div>
          <div className="xl:col-span-2"><EntityPicker kind="teams" label="Team B" value={b} onChange={(s) => setB(s)} minMatches={5} /></div>
          <label className="flex flex-col gap-1"><span className="eyebrow">Prediction date</span>
            <input type="date" className="input" min={minDate} value={asOf} onChange={(e) => setAsOf(e.target.value)} required /></label>
          <Select label="Team A side" value={side} onChange={setSide} options={[{ value: "unknown", label: "Unknown (average)" }, { value: "blue", label: "Blue" }, { value: "red", label: "Red" }]} />
          <Select label="Competition context" value={context} onChange={setContext} className="xl:col-span-2" options={[{ value: "domestic", label: "Domestic league" }, { value: "international", label: "International event (MSI / Worlds)" }]} />
          <div className="flex items-end xl:col-span-4">
            <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={!a || !b || a === b || !asOf || mut.isPending}>
              {mut.isPending ? "Computing..." : "Request prediction"}
            </button>
            <p className="ml-3 text-2xs text-ink-3">Dates must be after {fmtDate(valEnd)} (end of validation). Only games before the date are used.</p>
          </div>
        </form>
        {mut.error && <div className="mt-4"><ErrorState error={mut.error} /></div>}
        {mut.data && <Result r={mut.data} />}
      </Card>

      <ModelEvaluation models={models} test={test} />
      <Uncertainty models={models} />
      <History team={a} />
      <SourceNote meta={meta} />
    </div>
  );
}

function ProbBar({ pa, labelA, labelB }: { pa: number; labelA: string; labelB: string }) {
  return (
    <div>
      <div className="flex h-7 overflow-hidden rounded-md border border-line" role="img" aria-label={`${labelA} ${fmtPct(pa)}, ${labelB} ${fmtPct(1 - pa)}`}>
        <div className="flex items-center bg-cyan/25 px-2 text-xs font-semibold text-cyan" style={{ width: `${pa * 100}%` }}>{pa >= 0.15 && fmtPct(pa)}</div>
        <div className="flex flex-1 items-center justify-end bg-violet/20 px-2 text-xs font-semibold text-violet">{pa <= 0.85 && fmtPct(1 - pa)}</div>
      </div>
    </div>
  );
}

function Result({ r }: { r: PredRes }) {
  return (
    <div className="mt-6 space-y-5 border-t border-line pt-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm"><span className="font-semibold text-cyan">{r.team_a.name}</span> vs <span className="font-semibold text-violet">{r.team_b.name}</span> as of {fmtDate(r.as_of)}</p>
        <p className="text-2xs text-ink-3">Generated {fmtDateTime(r.generated_at)} | side: {r.team_a_side} | context: {r.context}</p>
      </div>
      <div className="space-y-4">
        {r.predictions.map((p) => (
          <div key={p.model_key} className="grid items-center gap-2 md:grid-cols-[240px_1fr]">
            <div><p className="text-sm font-medium">{p.display_name}</p><p className="text-2xs text-ink-3">version {p.version}</p></div>
            {p.prob_team_a === null ? <p className="text-sm text-ink-2">Unavailable: {p.reason}</p> : <ProbBar pa={p.prob_team_a} labelA={r.team_a.name} labelB={r.team_b.name} />}
          </div>
        ))}
      </div>
      {r.explanation && <Explanation r={r} />}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-md border border-line bg-bg-2 p-4">
          <p className="eyebrow mb-2">Inputs (before {fmtDate(r.as_of)})</p>
          <table className="w-full text-sm"><tbody>
            {([["Elo", fmtNum(r.team_a.elo, 0), fmtNum(r.team_b.elo, 0)], ["Earlier games", fmtInt(r.team_a.games_before), fmtInt(r.team_b.games_before)],
              ["Win rate", fmtPct(r.team_a.wins_before / r.team_a.games_before), fmtPct(r.team_b.wins_before / r.team_b.games_before)],
              ["Last game", fmtDate(r.team_a.last_game), fmtDate(r.team_b.last_game)]] as const).map(([l, x, y]) => (
              <tr key={l} className="border-b border-line-soft"><td className="py-1.5 text-ink-2">{l}</td><td className="num py-1.5 text-right text-cyan">{x}</td><td className="num py-1.5 text-right text-violet">{y}</td></tr>))}
          </tbody></table>
          <p className="mt-3 text-2xs text-ink-3">{r.inputs.feature_note}</p>
          <div className="mt-2 grid grid-cols-2 gap-x-4 text-2xs text-ink-2">
            {Object.entries(r.inputs.features_team_a_on_blue).map(([k, v]) => <span key={k}>{k}: <span className="num text-ink">{fmtNum(v, 3)}</span></span>)}
          </div>
        </div>
        <div className="rounded-md border border-amber/30 bg-amber/5 p-4">
          <p className="eyebrow mb-2 text-amber">Limitations</p>
          <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-2">{r.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      </div>
    </div>
  );
}

function verdict(c?: Comparison, base = "Elo") {
  if (!c) return "n/a";
  if (c.ci95_high < 0) return `better than ${base} (CI excludes 0)`;
  if (c.ci95_low > 0) return `worse than ${base} (CI excludes 0)`;
  return "no clear difference (CI includes 0)";
}

const ORDER = ["baseline_50", "baseline_prevalence", "elo", "elo_logit", "logreg"];
const short = (m: ModelInfo) => m.display_name.split(" (")[0];

function Explanation({ r }: { r: PredRes }) {
  const e = r.explanation!;
  const c = e.logreg_contributions;
  const maxAbs = c ? Math.max(...c.features.map((f) => Math.abs(f.contribution_log_odds)), 0.01) : 1;
  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <div className="rounded-md border border-cyan/30 bg-cyan/5 p-4 lg:col-span-2">
        <p className="eyebrow mb-2 text-cyan">Why this prediction</p>
        <ul className="list-disc space-y-1.5 pl-4 text-xs leading-relaxed text-ink-2">{e.summary.map((t) => <li key={t}>{t}</li>)}</ul>
        <table className="mt-3 w-full text-xs"><tbody>
          <tr className="border-b border-line-soft"><td className="py-1 text-ink-2">Elo difference (A − B)</td><td className="num py-1 text-right">{fmtSigned(e.elo_difference_a_minus_b, 0)}</td></tr>
          <tr className="border-b border-line-soft"><td className="py-1 text-ink-2">Last 10 games (A / B)</td><td className="num py-1 text-right">{e.recent_form.team_a.wins}-{e.recent_form.team_a.games - e.recent_form.team_a.wins} / {e.recent_form.team_b.wins}-{e.recent_form.team_b.games - e.recent_form.team_b.wins}</td></tr>
          <tr className="border-b border-line-soft"><td className="py-1 text-ink-2">Head-to-head before date (A-B)</td><td className="num py-1 text-right">{e.head_to_head_before_date.games ? `${e.head_to_head_before_date.wins_a}-${e.head_to_head_before_date.wins_b}` : "no meetings"}</td></tr>
          <tr className="border-b border-line-soft"><td className="py-1 text-ink-2">Blue win % with equal teams</td><td className="num py-1 text-right">{e.side_advantage ? fmtPct(e.side_advantage.blue_win_prob_equal_teams) : "unavailable"}</td></tr>
        </tbody></table>
        <p className="mt-2 text-2xs text-ink-3">{e.head_to_head_before_date.note} {e.side_advantage?.note}</p>
      </div>
      <div className="rounded-md border border-line bg-bg-2 p-4 lg:col-span-3">
        <p className="eyebrow mb-2">Logistic regression: feature contributions ({c?.orientation ?? "unavailable"})</p>
        {c ? (
          <>
            <div className="space-y-1.5">
              {c.features.map((f) => (
                <div key={f.feature} className="grid grid-cols-[130px_1fr_70px] items-center gap-2 text-xs">
                  <span className="font-mono text-ink-2">{f.feature}</span>
                  <div className="relative h-4 rounded bg-bg-elev">
                    <span className="absolute inset-y-0 left-1/2 w-px bg-line" />
                    <span className={cx("absolute inset-y-0.5 rounded", f.contribution_log_odds >= 0 ? "left-1/2 bg-cyan/60" : "right-1/2 bg-violet/60")}
                      style={{ width: `${(Math.abs(f.contribution_log_odds) / maxAbs) * 50}%` }} />
                  </div>
                  <span className="num text-right">{fmtSigned(f.contribution_log_odds, 3)}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-2xs text-ink-3">Intercept {fmtSigned(c.intercept, 3)} + contributions = logit {fmtSigned(c.logit, 3)} → P(team A wins on blue) = {fmtPct(c.probability_team_a_on_blue)}. Cyan pushes towards team A, violet towards team B. {c.note}</p>
          </>
        ) : <p className="text-sm text-ink-2">Logistic model unavailable.</p>}
      </div>
    </div>
  );
}

function ModelEvaluation({ models, test }: { models: ModelInfo[]; test?: { n: number; start: string; end: string } }) {
  const ms = ORDER.map((k) => models.find((m) => m.model_key === k)).filter(Boolean) as ModelInfo[];
  const real = ms.filter((m) => !m.model_key.startsWith("baseline"));
  const lr = ms.find((m) => m.model_key === "logreg");
  const [tab, setTab] = useState("metrics");
  const [metric, setMetric] = useState("brier");
  const tabs = [["metrics", "Metrics"], ["calibration", "Calibration"], ["roc", "ROC curve"], ["confusion", "Confusion matrices"],
    ["distribution", "Probability distribution"], ["time", "By quarter"], ["league", "By region"], ["features", "Features"]];
  return (
    <Card eyebrow="Historical evaluation" title="Test-period evaluation"
      info="All models are scored once on the same test games. The test period was never used to choose or fit any model.">
      <p className="mb-3 text-xs text-ink-2">Test period {fmtDate(test?.start)} to {fmtDate(test?.end)}, {fmtInt(test?.n)} games. Trained {fmtDateTime(ms[0]?.trained_at)}, version {ms[0]?.version}. Baselines use no information about the teams.</p>
      <div role="tablist" className="mb-4 flex flex-wrap gap-1 border-b border-line">
        {tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
          className={cx("-mb-px border-b-2 px-2.5 py-1.5 text-xs", tab === k ? "border-cyan text-ink" : "border-transparent text-ink-2 hover:text-ink")}>{l}</button>)}
      </div>
      {tab === "metrics" && (
        <>
          <div className="-mx-4 overflow-x-auto sm:mx-0"><table className="w-full min-w-[820px]">
            <thead className="border-b border-line"><tr><th className="th">Model</th><th className="th text-right">Brier</th><th className="th text-right">Log loss</th><th className="th text-right">ECE</th><th className="th text-right">ROC-AUC</th><th className="th text-right">Accuracy</th><th className="th text-right">Precision</th><th className="th text-right">Recall</th><th className="th text-right">F1</th></tr></thead>
            <tbody>{ms.map((m) => { const t = m.metrics?.test; return (
              <tr key={m.model_key} className={cx("border-b border-line-soft", m.model_key.startsWith("baseline") && "text-ink-2")}><td className="td">{m.display_name}</td>
                <td className="td num text-right">{fmtNum(t?.brier, 4)}</td><td className="td num text-right">{fmtNum(t?.log_loss, 4)}</td>
                <td className="td num text-right">{fmtNum(t?.ece, 4)}</td><td className="td num text-right">{t?.roc_auc == null ? "n/a" : fmtNum(t.roc_auc, 3)}</td>
                <td className="td num text-right">{fmtPct(t?.accuracy)}</td><td className="td num text-right">{fmtPct(t?.precision)}</td>
                <td className="td num text-right">{fmtPct(t?.recall)}</td><td className="td num text-right">{fmtNum(t?.f1, 3)}</td></tr>); })}</tbody>
          </table></div>
          <p className="mt-3 text-2xs leading-relaxed text-ink-3">Brier, log loss and ECE (expected calibration error, 10 bins) judge the probabilities; lower is better. Accuracy, precision, recall and F1 use a 0.5 threshold with "blue wins" as the positive class. A constant prediction above 50% predicts "blue" for every game, so its recall is 100% and its F1 can beat real models: F1 is not a good guide here. ROC-AUC is undefined (n/a) for constant predictions.</p>
        </>
      )}
      {tab === "calibration" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Reliability models={real.map((m) => ({ label: short(m), bins: m.metrics?.calibration || [] }))} height={320} />
          <div>
            <Bars data={ms.map((m) => ({ model: short(m), ece: m.metrics?.test?.ece ?? null }))} x="model" series={[{ key: "ece", label: "Expected calibration error" }]} layout="vertical" height={220} />
            <p className="mt-2 text-2xs text-ink-3">Reliability: points on the diagonal = well calibrated; point size = games in the bin.{" "}
              {(real.find((m) => m.model_key === "elo")?.metrics?.test?.ece ?? 0) > (real.find((m) => m.model_key === "elo_logit")?.metrics?.test?.ece ?? 1)
                ? "Raw Elo has no side term and a fixed 400-point scale, so it is less calibrated than the calibrated Elo fitted to the same ratings." : ""}</p>
          </div>
        </div>
      )}
      {tab === "roc" && <Curves curves={real.map((m) => ({ label: short(m), points: (m.metrics?.roc || []) as unknown as Record<string, unknown>[] }))} x="fpr" y="tpr" xLabel="False positive rate" yLabel="True positive rate" diagonal height={320} />}
      {tab === "confusion" && (
        <div className="grid gap-3 md:grid-cols-3">{real.map((m) => { const c = m.metrics?.confusion || {}; return (
          <div key={m.model_key} className="rounded-md border border-line bg-bg-2 p-3">
            <p className="mb-2 text-xs font-medium">{short(m)}</p>
            <table className="w-full text-center text-xs"><thead><tr><th></th><th className="pb-1 text-2xs text-ink-3">Pred. red</th><th className="pb-1 text-2xs text-ink-3">Pred. blue</th></tr></thead><tbody>
              <tr><td className="pr-2 text-left text-2xs text-ink-3">Red won</td><td className="num rounded bg-emerald/10 py-2">{fmtInt(c.true_negative)}</td><td className="num rounded bg-danger/10 py-2">{fmtInt(c.false_positive)}</td></tr>
              <tr><td className="pr-2 text-left text-2xs text-ink-3">Blue won</td><td className="num rounded bg-danger/10 py-2">{fmtInt(c.false_negative)}</td><td className="num rounded bg-emerald/10 py-2">{fmtInt(c.true_positive)}</td></tr>
            </tbody></table>
          </div>); })}</div>
      )}
      {tab === "distribution" && (
        <>
          <Bars data={(ms.find((m) => m.model_key === "logreg")?.metrics?.probability_histogram || []).map((b, i) => ({
            bin: b.lower.toFixed(2), ...Object.fromEntries(real.map((m) => [short(m), m.metrics?.probability_histogram?.[i]?.n ?? 0])) }))}
            x="bin" series={real.map((m, i) => ({ key: short(m), label: short(m), color: CHART.series[i] }))} height={280} />
          <p className="mt-2 text-2xs text-ink-3">How confident each model is: number of test games by predicted probability that blue wins (bins of 0.05).</p>
        </>
      )}
      {tab === "time" && (
        <>
          <div className="mb-2 flex justify-end"><Select label="Metric" value={metric} onChange={setMetric} className="w-32" options={[{ value: "brier", label: "Brier" }, { value: "accuracy", label: "Accuracy" }]} /></div>
          <TimeLine data={(lr?.metrics?.temporal_breakdown || [])} x="period" height={260}
            series={[{ key: `elo_${metric}`, label: "Elo", color: CHART.cyan }, { key: `elo_logit_${metric}`, label: "Calibrated Elo", color: CHART.violet }, { key: `logreg_${metric}`, label: "Logistic", color: CHART.emerald }]} />
          <p className="mt-2 text-2xs text-ink-3">Quarters with at least 30 test games. Differences between quarters reflect the competitive calendar (e.g. international events) as much as the models.</p>
        </>
      )}
      {tab === "league" && (
        <div className="-mx-4 overflow-x-auto sm:mx-0"><table className="w-full min-w-[620px]"><thead className="border-b border-line"><tr><th className="th">League</th><th className="th text-right">Games</th><th className="th text-right">Elo Brier</th><th className="th text-right">Calibrated</th><th className="th text-right">Logistic</th><th className="th text-right">Logistic accuracy</th></tr></thead>
          <tbody>{(lr?.metrics?.league_breakdown || []).map((r) => (
            <tr key={String(r.league)} className="border-b border-line-soft"><td className="td">{String(r.league)}</td><td className="td num text-right">{fmtInt(r.n as number)}</td>
              <td className="td num text-right">{fmtNum(r.elo_brier as number, 4)}</td><td className="td num text-right">{fmtNum(r.elo_logit_brier as number, 4)}</td>
              <td className="td num text-right">{fmtNum(r.logreg_brier as number, 4)}</td><td className="td num text-right">{fmtPct(r.logreg_accuracy as number)}</td></tr>))}</tbody></table>
          <p className="mt-2 text-2xs text-ink-3">Leagues with at least 150 test games. Per-league differences are not tested statistically; small leagues are noisy.</p></div>
      )}
      {tab === "features" && <FeatureTable m={lr} />}
    </Card>
  );
}

function Uncertainty({ models }: { models: ModelInfo[] }) {
  const all: Record<string, Comparison> = {};
  models.forEach((m) => Object.assign(all, m.metrics?.comparisons || {}));
  const elo = models.find((m) => m.model_key === "elo");
  const lo = (elo?.hyperparameters?.league_offsets || null) as { selected_vs_flat_brier: Comparison; cross_league_only_brier?: Comparison; flat_test: { brier: number } } | null;
  const eloBrier = elo?.metrics?.test?.brier ?? 0;
  const rows: [string, Comparison | undefined][] = [
    ["Elo vs prevalence baseline", all["elo_vs_baseline_prevalence_brier"]],
    ["Elo with league offsets vs flat Elo", lo?.selected_vs_flat_brier],
    ["Calibrated Elo vs Elo", all["elo_logit_vs_elo_brier"]],
    ["Logistic vs Elo", all["logreg_vs_elo_brier"]],
    ["Logistic vs calibrated Elo", all["logreg_vs_elo_logit_brier"]],
    ["Logistic vs calibrated Elo (tournament clusters)", all["logreg_vs_elo_logit_brier_tournament_clusters"]],
    ["Logistic vs Elo (single-game resampling)", all["logreg_vs_elo_brier_single_game_bootstrap"]],
  ];
  return (
    <Card eyebrow="Statistical uncertainty" title="How sure are the differences?"
      info="Paired bootstrap: the same test games are resampled for both models (2,000 resamples). The main unit is the series (same tournament, same two teams, same UTC day), because games in one series are not independent.">
      <div className="-mx-4 overflow-x-auto sm:mx-0"><table className="w-full min-w-[860px]">
        <thead className="border-b border-line"><tr><th className="th">Comparison (Brier, model minus reference)</th><th className="th text-right">Point estimate</th><th className="th text-right">95% CI</th><th className="th">Resampling unit</th><th className="th text-right">Units</th><th className="th">Statistical</th><th className="th text-right">Practical size</th></tr></thead>
        <tbody>{rows.filter(([, c]) => c).map(([l, c]) => { const x = c!; const rel = eloBrier ? Math.abs(x.difference) / eloBrier : null; return (
          <tr key={l} className="border-b border-line-soft"><td className="td text-xs">{l}</td><td className="td num text-right">{fmtSigned(x.difference, 5)}</td>
            <td className="td num text-right">{fmtSigned(x.ci95_low, 5)} to {fmtSigned(x.ci95_high, 5)}</td><td className="td text-xs text-ink-2">{x.resampling_unit ?? "single game"}</td>
            <td className="td num text-right">{fmtInt(x.n_units)}</td>
            <td className="td text-xs">{x.ci95_high < 0 ? <span className="text-emerald">lower Brier, CI excludes 0</span> : x.ci95_low > 0 ? <span className="text-danger">higher Brier, CI excludes 0</span> : <span className="text-ink-2">CI includes 0</span>}</td>
            <td className="td num text-right text-xs">{rel === null ? "n/a" : `${(rel * 100).toFixed(2)}% of Elo Brier`}</td></tr>); })}</tbody>
      </table></div>
      <p className="mt-3 text-xs leading-relaxed text-ink-2"><b className="text-ink">Statistical vs practical significance.</b> An interval that excludes zero says the difference is unlikely to be resampling noise. It does not say the difference matters. With 10,000 test games, differences of a few thousandths of a Brier point can be "significant" while changing almost no predictions. The last column puts each difference against the Elo Brier score.</p>
      <p className="mt-2 text-2xs text-ink-3">Limitations: series are approximated (no series id in the source); one test period only (a single realisation of the future); models are fixed at the start of the test period rather than refitted as new games arrive.</p>
    </Card>
  );
}

function FeatureTable({ m }: { m?: ModelInfo }) {
  const coefs = (m?.hyperparameters?.coefficients || []) as { feature: string; coef_per_sd: number; odds_ratio_per_sd: number }[];
  const exp = m?.hyperparameters?.experimental_models as { decision: string; sample: string; results: { model: string; brier: number; log_loss: number; brier_vs_logistic?: number; ci95_low?: number; ci95_high?: number }[] } | undefined;
  if (!m) return null;
  return (
    <div className="overflow-x-auto">
      <p className="eyebrow mb-2">Logistic regression features (coefficients per 1 SD, fitted on train + validation)</p>
      <table className="w-full min-w-[620px]"><thead className="border-b border-line"><tr><th className="th">Feature</th><th className="th">Definition</th><th className="th text-right">Coef / SD</th><th className="th text-right">Odds ratio / SD</th></tr></thead>
        <tbody>{(m.feature_definitions || []).map((f) => { const c = coefs.find((x) => x.feature === f.name); return (
          <tr key={f.name} className="border-b border-line-soft"><td className="td font-mono text-xs">{f.name}</td><td className="td whitespace-normal text-xs text-ink-2">{f.definition}</td>
            <td className="td num text-right">{fmtNum(c?.coef_per_sd, 3)}</td><td className="td num text-right">{fmtNum(c?.odds_ratio_per_sd, 3)}</td></tr>); })}</tbody></table>
      <p className="mt-2 text-2xs text-ink-3">Features are correlated with each other (most carry information also in Elo), so individual coefficients should not be read as causal effects. Every feature is computed from games that ended before the predicted game.</p>
      {exp && (
        <div className="mt-4">
          <p className="eyebrow mb-2">Tree models: {exp.sample}</p>
          <table className="w-full min-w-[620px]"><thead className="border-b border-line"><tr><th className="th">Model</th><th className="th text-right">Validation Brier</th><th className="th text-right">Log loss</th><th className="th text-right">Brier vs logistic (95% CI)</th></tr></thead>
            <tbody>{exp.results.map((r) => <tr key={r.model} className="border-b border-line-soft"><td className="td text-xs">{r.model}</td><td className="td num text-right">{fmtNum(r.brier, 4)}</td><td className="td num text-right">{fmtNum(r.log_loss, 4)}</td>
              <td className="td num text-right text-xs">{r.brier_vs_logistic === undefined ? "reference" : `${fmtSigned(r.brier_vs_logistic, 5)} (${fmtSigned(r.ci95_low, 5)} to ${fmtSigned(r.ci95_high, 5)})`}</td></tr>)}</tbody></table>
          <p className="mt-2 text-xs text-ink-2">{exp.decision}</p>
        </div>
      )}
    </div>
  );
}

interface HistRow { match_id: number; date: string; tournament: string; league: string; blue_team: string; blue_team_slug: string; red_team: string; red_team_slug: string; blue_won: number; split: string; prob_blue_win: Record<string, number> }
interface Hist { rows: HistRow[]; versions: Record<string, string>; monthly: Record<string, number | string>[]; note: string }
function History({ team }: { team: string }) {
  const [split, setSplit] = useState("test");
  const [league, setLeague] = useState("");
  const [teamOnly, setTeamOnly] = useState(true);
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [split, league, team, teamOnly]);
  const filters = useApi<{ leagues: { league: string }[] }>("/tournaments/filters", { game: "lol" });
  const q = useApi<Hist>("/predictions/history", { game: "lol", team: teamOnly ? team : "", league, split, page, page_size: 25 });
  return (
    <Card eyebrow="Historical predictions" title="Stored out-of-sample predictions and outcomes"
      info="Predictions made for validation and test games using only information available before each game, shown next to the actual result.">
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        <Select label="Period" value={split} onChange={setSplit} options={[{ value: "test", label: "Test" }, { value: "validation", label: "Validation" }, { value: "", label: "Both" }]} />
        <Select label="League" value={league} onChange={setLeague} options={[{ value: "", label: "All leagues" }, ...(filters.data?.data?.leagues || []).map((l) => ({ value: l.league, label: l.league }))]} />
        <label className="flex items-end gap-2 pb-2 text-xs text-ink-2"><input type="checkbox" checked={teamOnly} onChange={() => setTeamOnly(!teamOnly)} disabled={!team} /> Only Team A {team ? "" : "(select a team above)"}</label>
      </div>
      <DataState query={q} isEmpty={(d) => d.rows.length === 0}>
        {(d, meta) => (
          <>
            {d.monthly.length > 1 && (
              <div className="mb-4">
                <p className="eyebrow mb-1">Brier score by month for this selection (months with 20+ games)</p>
                <TimeLine data={d.monthly} x="month" height={200}
                  series={[{ key: "elo_brier", label: "Elo", color: CHART.cyan }, { key: "elo_logit_brier", label: "Calibrated Elo", color: CHART.violet }, { key: "logreg_brier", label: "Logistic", color: CHART.emerald }]} />
              </div>
            )}
            <div className="-mx-4 overflow-x-auto sm:mx-0"><table className="w-full min-w-[860px]">
              <thead className="border-b border-line"><tr><th className="th">Date</th><th className="th">League</th><th className="th">Blue</th><th className="th">Red</th><th className="th text-right">P(blue) Elo</th><th className="th text-right">Calibrated</th><th className="th text-right">Logistic</th><th className="th">Winner</th><th className="th">Period</th></tr></thead>
              <tbody>{d.rows.map((r) => (
                <tr key={r.match_id} className="border-b border-line-soft">
                  <td className="td text-ink-2">{fmtDate(r.date)}</td><td className="td text-xs">{r.league}</td>
                  <td className="td"><Link className="hover:text-cyan" href={`/teams/${r.blue_team_slug}`}>{r.blue_team}</Link></td>
                  <td className="td"><Link className="hover:text-cyan" href={`/teams/${r.red_team_slug}`}>{r.red_team}</Link></td>
                  {(["elo", "elo_logit", "logreg"] as const).map((k) => { const p = r.prob_blue_win[k]; const right = p !== undefined && (p >= 0.5) === (r.blue_won === 1);
                    return <td key={k} className={cx("td num text-right", right ? "text-emerald" : "text-danger")}>{fmtPct(p)}</td>; })}
                  <td className="td">{r.blue_won ? r.blue_team : r.red_team}</td><td className="td text-xs text-ink-3">{r.split}</td>
                </tr>))}</tbody></table></div>
            {meta.pagination && <Pagination page={meta.pagination.page} pages={meta.pagination.pages} total={meta.pagination.total} onPage={setPage} />}
            <p className="mt-2 text-2xs text-ink-3">Model versions: {Object.entries(d.versions).map(([k, v]) => `${k} ${v}`).join(", ")}. Green = the side with the higher predicted probability won. {d.note}</p>
          </>
        )}
      </DataState>
    </Card>
  );
}
