"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { Bars, TimeLine } from "@/components/charts/charts";
import { GAMES, useGame } from "@/components/providers";
import { GameSwitch } from "@/components/ui/game-gate";
import { Card, DataState, InfoTip, PageHeader, Select, SourceNote, Stat, StatusBadge } from "@/components/ui/primitives";
import { MatchTable, TeamTable } from "@/components/ui/tables";
import { useApi } from "@/hooks/use-api";
import type { Comparison, MatchSummary, TeamSummary } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtInt, fmtNum, fmtPct, fmtPeriod } from "@/lib/format";

interface Overview {
  kpis: { matches: number | null; teams: number | null; players: number | null; tournaments: number | null; leagues: number | null;
    coverage_start: string | null; coverage_end: string | null; prize_money: null };
  top_teams: TeamSummary[];
  top_teams_definition?: string;
  recent_matches: MatchSummary[];
  matches_per_month: { month: string; matches: number }[];
  matches_by_league: { league: string; matches: number }[];
  research: { models: Record<string, { display_name: string; brier: number; accuracy: number; log_loss: number; f1: number | null; n_test: number }>;
    best_by_brier: string; best_by_accuracy: string; best_by_f1: string; vs_elo_brier: Record<string, Comparison | null>;
    logreg_vs_elo_brier: Comparison | null; test_period: { start: string; end: string; n: number }; version: string; note: string } | null;
  latest_ingestion: string | null;
  coverage?: { by_calendar_year: { year: number; games: number }[]; by_league: { league: string; games: number }[]; other_leagues: { leagues: number; games: number }; definition: string };
  data_quality?: DQ;
  elo_method?: EloMethod | null;
}
export interface DQ {
  games_loaded: number; duplicate_rows_exact: number | null; duplicate_rows_conflicting: number | null; rows_retrieved: number | null;
  rows_excluded_total: number | null; games_excluded: number | null; invalid_game_ids: number | null; partial_games: number;
  partial_share: number | null; team_games_missing_15min_stats_share: number | null; teams_without_source_id: number;
  players_without_source_id: number; last_run: { run_id: string; status: string; stages: { stage: string; status: string; at: string }[] } | null;
  definitions: Record<string, string>;
}
interface EloMethod { version: string; initial: number; k: number; carryover_shrink: number; k_league: number;
  blue_win_prob_equal_elo: number | null; data_start: string; data_end: string; train_end: string; validation_end: string; selection: string }

export default function OverviewView() {
  const { game } = useGame();
  const [league, setLeague] = useState("");
  const q = useApi<Overview>("/overview", { game, league });
  const filters = useApi<{ leagues: { league: string; n_tournaments: number }[] }>("/tournaments/filters", { game }, game === "lol");
  const gameName = GAMES.find((g) => g.slug === game)?.name;

  return (
    <>
      <PageHeader index="01" eyebrow="Overview" title="Professional esports, measured."
        description="A research platform for competitive gaming data. Every figure on this page is calculated from imported historical records; nothing is estimated or filled in. It currently covers professional League of Legends from Oracle's Elixir.">
        <div className="flex flex-wrap items-end gap-3">
          <GameSwitch />
          {game === "lol" && (
            <Select label="League filter" value={league} onChange={setLeague} className="w-44"
              options={[{ value: "", label: "All leagues" }, ...(filters.data?.data?.leagues || []).map((l) => ({ value: l.league, label: l.league }))]} />
          )}
        </div>
      </PageHeader>

      <DataState query={q} gameName={gameName}>
        {(d, meta) => (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center gap-3 text-xs text-ink-2">
              <StatusBadge status="historical" />
              <span>Coverage {fmtPeriod({ start: d.kpis.coverage_start, end: d.kpis.coverage_end })}</span>
              <span className="text-ink-3">|</span>
              <span>Last import {fmtDateTime(d.latest_ingestion)}</span>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              <Stat label="Games recorded" value={fmtInt(d.kpis.matches)} sub="single games (maps)" info="One row per game (Oracle's Elixir gameid). Best-of series are not combined." />
              <Stat label="Teams indexed" value={fmtInt(d.kpis.teams)} accent="violet" />
              <Stat label="Players indexed" value={fmtInt(d.kpis.players)} accent="violet" />
              <Stat label="Tournaments" value={fmtInt(d.kpis.tournaments)} sub={`${fmtInt(d.kpis.leagues)} leagues`} />
              <Stat label="Latest game" value={<span className="text-lg">{fmtDate(d.kpis.coverage_end)}</span>} accent="emerald" />
              <Stat label="Prize money" value={<span className="text-lg text-ink-2">Unavailable</span>} accent="emerald"
                info="The source data has no prize money field. No prize figure is estimated." />
            </div>

            {d.coverage && (
              <div className="grid gap-6 xl:grid-cols-5">
                <Card className="xl:col-span-2" eyebrow="Data coverage" title="Games by calendar year" info={d.coverage.definition}>
                  <Bars data={d.coverage.by_calendar_year} x="year" series={[{ key: "games", label: "Games" }]} height={220} />
                  <p className="mt-2 text-2xs text-ink-3">Earliest game {fmtDate(d.kpis.coverage_start)}, latest {fmtDate(d.kpis.coverage_end)}. {fmtInt(d.kpis.leagues)} leagues represented.</p>
                </Card>
                <Card className="xl:col-span-3" eyebrow="Data coverage" title="Games by competition region (15 largest leagues)" info={d.coverage.definition}>
                  <Bars data={d.coverage.by_league} x="league" series={[{ key: "games", label: "Games" }]} layout="vertical" height={Math.max(260, d.coverage.by_league.length * 24)} />
                  {d.coverage.other_leagues.leagues > 0 && <p className="mt-2 text-2xs text-ink-3">Plus {fmtInt(d.coverage.other_leagues.games)} games in {d.coverage.other_leagues.leagues} smaller leagues and events.</p>}
                </Card>
              </div>
            )}
            <div className="grid gap-6 xl:grid-cols-5">
              {d.data_quality && <QualityPanel q={d.data_quality} />}
              {d.elo_method && <EloPanel m={d.elo_method} />}
            </div>

            <div className="grid gap-6 xl:grid-cols-5">
              <Card className="xl:col-span-3" eyebrow="Competitive performance" title="Team rankings by Elo"
                info={d.top_teams_definition}
                actions={<Link href="/teams?sort=elo" className="link text-xs">All teams</Link>}>
                {d.top_teams.length ? <TeamTable rows={d.top_teams} /> : <p className="text-sm text-ink-2">No team meets the activity rule for this filter.</p>}
              </Card>
              <Card className="xl:col-span-2" eyebrow="Research highlight" title="Can machine learning beat Elo?">
                {d.research ? <ResearchHighlight r={d.research} /> : (
                  <p className="text-sm leading-relaxed text-ink-2">
                    Models are not trained yet, so no result is shown. Run <code className="text-xs">make models</code> after
                    importing data. <Link className="link" href="/research/can-machine-learning-beat-elo">Read the study design</Link>.
                  </p>
                )}
              </Card>
            </div>

            <div className="grid gap-6 xl:grid-cols-5">
              <Card className="xl:col-span-5" eyebrow="Historical trend" title={`Games per month${league ? ` (${league})` : ""}`}
                info="Count of recorded games per calendar month. Gaps reflect the competitive calendar and source coverage.">
                <TimeLine data={d.matches_per_month} x="month" series={[{ key: "matches", label: "Games" }]} height={240} />
              </Card>

            </div>

            <Card eyebrow="Recent results" title={`Latest recorded games${league ? ` (${league})` : ""}`}
              actions={<Link href="/data-explorer" className="link text-xs">Explore all games</Link>}>
              <MatchTable rows={d.recent_matches} />
            </Card>
            <SourceNote meta={meta} />
          </div>
        )}
      </DataState>
    </>
  );
}

function ResearchHighlight({ r }: { r: NonNullable<Overview["research"]> }) {
  const order = ["baseline_50", "baseline_prevalence", "elo", "elo_logit", "logreg"].filter((k) => r.models[k]);
  const name = (k: string) => r.models[k]?.display_name.split(" (")[0] ?? k;
  const c = r.vs_elo_brier?.logreg;
  return (
    <div className="space-y-4">
      <p className="text-xs text-ink-2">Out-of-sample test period {fmtDate(r.test_period?.start)} to {fmtDate(r.test_period?.end)}, {fmtInt(r.models.elo?.n_test)} games, model version {r.version}. Lower Brier is better; 0.25 = coin flip.</p>
      <div className="grid grid-cols-3 gap-2">
        {([["Best by Brier", r.best_by_brier], ["Best by accuracy", r.best_by_accuracy], ["Best by F1", r.best_by_f1]] as const).map(([l, k]) => (
          <div key={l} className="rounded-md border border-line bg-bg-2 p-2"><p className="eyebrow">{l}</p><p className="mt-1 text-xs font-medium text-ink">{name(k)}</p></div>
        ))}
      </div>
      <div className="overflow-x-auto"><table className="w-full">
        <thead><tr className="border-b border-line"><th className="th">Model</th><th className="th text-right">Brier</th><th className="th text-right">Acc.</th><th className="th text-right">F1</th></tr></thead>
        <tbody>
          {order.map((k) => (
            <tr key={k} className={`border-b border-line-soft ${k.startsWith("baseline") ? "text-ink-2" : ""}`}>
              <td className="td text-xs">{name(k)}</td>
              <td className="td num text-right">{fmtNum(r.models[k].brier, 4)}</td>
              <td className="td num text-right">{(r.models[k].accuracy * 100).toFixed(1)}%</td>
              <td className="td num text-right">{fmtNum(r.models[k].f1, 3)}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
      {c && (
        <p className="text-xs leading-relaxed text-ink-2">
          Logistic minus Elo Brier: <span className="num text-ink">{c.difference >= 0 ? "+" : ""}{c.difference.toFixed(5)}</span>, 95% CI {c.ci95_low.toFixed(5)} to {c.ci95_high.toFixed(5)} (paired bootstrap over series).{" "}
          {c.ci95_high < 0
            ? `Statistically better; the gain is ${(Math.abs(c.difference) / r.models.elo.brier * 100).toFixed(2)}% of the Elo Brier score${Math.abs(c.difference) / r.models.elo.brier < 0.01 ? ", small in practice" : ""}.`
            : c.ci95_low > 0 ? "Worse; the interval excludes zero." : "No clear difference: the interval includes zero."}
        </p>
      )}
      <p className="text-2xs leading-relaxed text-amber">{r.note}{r.best_by_f1.startsWith("baseline") ? " Here a constant baseline has the highest F1, because it predicts \"blue wins\" for every game." : ""}</p>
      <Link href="/research/can-machine-learning-beat-elo" className="link inline-flex items-center gap-1 text-sm">Full report <ArrowUpRight size={14} /></Link>
    </div>
  );
}

function QualityPanel({ q }: { q: DQ }) {
  const rows: [string, string, string?][] = [
    ["Rows read from source files", fmtInt(q.rows_retrieved)],
    ["Duplicate rows (exact / conflicting)", `${fmtInt(q.duplicate_rows_exact)} / ${fmtInt(q.duplicate_rows_conflicting)}`],
    ["Invalid games excluded", fmtInt(q.invalid_game_ids), q.definitions.invalid_game_ids],
    ["Rows excluded in total", fmtInt(q.rows_excluded_total)],
    ["Partial games (stats missing)", `${fmtInt(q.partial_games)} (${fmtPct(q.partial_share)})`, q.definitions.partial_games],
    ["Team games without 15-min stats", fmtPct(q.team_games_missing_15min_stats_share)],
    ["Teams / players without source id", `${fmtInt(q.teams_without_source_id)} / ${fmtInt(q.players_without_source_id)}`, q.definitions.teams_without_source_id],
  ];
  return (
    <Card className="xl:col-span-2" eyebrow="Data quality" title="Data quality indicators"
      actions={<Link href="/data-quality" className="link text-xs">Full report</Link>}>
      <div className="overflow-x-auto"><table className="w-full"><tbody>
        {rows.map(([l, v, info]) => (
          <tr key={l} className="border-b border-line-soft"><td className="py-1.5 pr-2 text-xs text-ink-2">{l}{info && <span className="ml-1 align-middle"><InfoTip text={info} /></span>}</td><td className="num py-1.5 text-right text-sm">{v}</td></tr>
        ))}
      </tbody></table></div>
      <p className="mt-3 flex items-center gap-2 text-2xs text-ink-3">Last ingestion run:
        {q.last_run ? <StatusBadge status={q.last_run.status === "ok" ? "completed" : "unavailable"} label={q.last_run.status === "ok" ? `ok, ${q.last_run.stages.length} stages` : "error"} /> : "n/a"}</p>
    </Card>
  );
}

function EloPanel({ m }: { m: EloMethod }) {
  return (
    <Card className="xl:col-span-3" eyebrow="Methodology" title="How the Elo ratings are calculated">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 text-xs leading-relaxed text-ink-2">
          <div className="rounded-md border border-line bg-bg-2 p-3 font-mono text-[12px] text-ink">
            <p>E<sub>A</sub> = 1 / (1 + 10<sup>(R<sub>B</sub> − R<sub>A</sub>)/400</sup>)</p>
            <p className="mt-1">R<sub>A,new</sub> = R<sub>A,old</sub> + K (S<sub>A</sub> − E<sub>A</sub>)</p>
          </div>
          <p>E<sub>A</sub> is team A&apos;s expected score (its win probability), S<sub>A</sub> is 1 for a win and 0 for a loss. Ratings update after every game, in time order, from the first game in the data ({fmtDate(m.data_start)}).</p>
          <div className="overflow-x-auto"><table className="w-full"><tbody>
            {([["Initial rating", fmtNum(m.initial, 0)], ["K-factor", fmtNum(m.k, 0)], ["League step k_league", fmtNum(m.k_league, 0)],
              ["Season shrinkage", fmtNum(m.carryover_shrink, 2)], ["Model version", m.version]] as const).map(([l, v]) => (
              <tr key={l} className="border-b border-line-soft"><td className="py-1 text-ink-2">{l}</td><td className="num py-1 text-right text-ink">{v}</td></tr>))}
          </tbody></table></div>
          <p className="text-2xs text-ink-3">{m.selection} Validation ended {fmtDate(m.validation_end)}.</p>
        </div>
        <div className="text-xs leading-relaxed text-ink-2">
          <p className="eyebrow mb-2">Deviations from the standard formula</p>
          <ul className="list-disc space-y-1.5 pl-4">
            <li><b className="text-ink">League offsets.</b> R = league level + team component. Games between leagues also move both league levels by k_league (S − E). New teams start at their league&apos;s level.</li>
            <li><b className="text-ink">New season.</b> At a team&apos;s first game of a calendar year, its team component shrinks toward its league level by the shrinkage factor.</li>
            <li><b className="text-ink">Same-time games</b> are processed as one batch using ratings from before the batch.</li>
            <li><b className="text-ink">Side advantage</b> is not in the Elo formula. The calibrated Elo model estimates it: with equal ratings blue wins {fmtPct(m.blue_win_prob_equal_elo)}.</li>
            <li><b className="text-ink">Inactive teams</b> keep their last rating (no decay); the Overview ranking only lists teams active in the last 180 days of data.</li>
            <li><b className="text-ink">Historical ratings</b> are recomputed from scratch on every pipeline run, so they depend only on games before each date.</li>
          </ul>
        </div>
      </div>
    </Card>
  );
}
