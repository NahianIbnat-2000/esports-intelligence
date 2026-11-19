"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { TimeLine } from "@/components/charts/charts";
import { Breadcrumbs, Card, DataState, PageHeader, Select, SourceNote, Stat, WinLoss } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import type { PlayerSummary } from "@/lib/api";
import { POSITIONS, fmtDate, fmtInt, fmtNum } from "@/lib/format";

type Agg = Record<string, number | null>;
interface Detail {
  player: PlayerSummary;
  career: Agg;
  by_year: Agg[];
  team_history: { team_slug: string; team: string; tournament: string; tournament_slug: string; position: string; games_played: number; first: string; last: string }[];
  recent_games: { date: string; tournament: string; team: string; result: number; kills: number | null; deaths: number | null; assists: number | null; champion: string | null; dpm: number | null; cspm: number | null; position: string }[];
  metric_definitions: Record<string, string>;
  notes: string[];
}

const TREND_METRICS = ["kda", "dpm", "cspm", "earned_gpm", "damage_share", "vspm", "golddiff_at_15"];

export default function PlayerDetail() {
  const { slug } = useParams<{ slug: string }>();
  const q = useApi<Detail>(`/players/${slug}`, { game: "lol" });
  const [metric, setMetric] = useState("kda");
  return (
    <>
      <Breadcrumbs items={[{ label: "Players", href: "/players" }, { label: q.data?.data?.player.name || slug }]} />
      <DataState query={q}>
        {(d, meta) => {
          const p = d.player;
          const c = d.career;
          return (
            <>
              <PageHeader eyebrow={`Player | ${p.primary_position ? POSITIONS[p.primary_position] : "position n/a"}`} title={p.name}
                description={<>Latest team: {p.latest_team_slug ? <Link className="link" href={`/teams/${p.latest_team_slug}`}>{p.latest_team}</Link> : "n/a"}. Recorded {fmtDate(p.first_match_date)} to {fmtDate(p.last_match_date)}.</>}>
                <Link href={`/players/compare?a=${p.slug}`} className="btn">Compare</Link>
              </PageHeader>
              <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
                <Stat label="Games" value={fmtInt(c.games)} />
                <Stat label="KDA" value={fmtNum(c.kda)} info={d.metric_definitions.kda} />
                <Stat label="Damage / min" value={fmtNum(c.dpm, 0)} accent="violet" info={d.metric_definitions.dpm} />
                <Stat label="CS / min" value={fmtNum(c.cspm)} accent="violet" info={d.metric_definitions.cspm} />
                <Stat label="Gold diff @15" value={fmtNum(c.golddiff_at_15, 0)} accent="emerald" info={d.metric_definitions.golddiff_at_15} />
                <Stat label="Detailed-stat games" value={fmtInt(c.games_with_detailed_stats)} accent="emerald" info={d.notes[0]} />
              </div>
              <div className="grid gap-6 xl:grid-cols-3">
                <Card className="xl:col-span-2" eyebrow="Career progression" title="By calendar year"
                  actions={<Select label="Metric" value={metric} onChange={setMetric} className="w-44"
                    options={TREND_METRICS.map((m) => ({ value: m, label: m.replace(/_/g, " ") }))} />}
                  info={d.metric_definitions[metric]}>
                  <TimeLine data={d.by_year.map((r) => ({ year: String(r.year), value: r[metric] }))} x="year" series={[{ key: "value", label: metric }]} height={240} />
                  <div className="mt-3 overflow-x-auto"><div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr>
                    <th className="th">Year</th><th className="th text-right">Games</th><th className="th text-right">K/D/A</th><th className="th text-right">KDA</th><th className="th text-right">DPM</th><th className="th text-right">CSPM</th></tr></thead>
                    <tbody>{d.by_year.map((r) => (
                      <tr key={r.year} className="border-b border-line-soft"><td className="td num">{r.year}</td><td className="td num text-right">{fmtInt(r.games)}</td>
                        <td className="td num text-right">{fmtNum(r.kills, 1)}/{fmtNum(r.deaths, 1)}/{fmtNum(r.assists, 1)}</td><td className="td num text-right">{fmtNum(r.kda)}</td>
                        <td className="td num text-right">{fmtNum(r.dpm, 0)}</td><td className="td num text-right">{fmtNum(r.cspm)}</td></tr>))}</tbody></table></div></div>
                </Card>
                <Card eyebrow="Teams" title="Team history" info="Observed appearances per tournament, not contract records.">
                  <ul className="max-h-[420px] divide-y divide-line-soft overflow-y-auto">
                    {d.team_history.map((h, i) => (
                      <li key={i} className="py-2 text-sm">
                        <Link href={`/teams/${h.team_slug}`} className="font-medium hover:text-cyan">{h.team}</Link>
                        <p className="text-xs text-ink-2"><Link className="hover:text-cyan" href={`/tournaments/${h.tournament_slug}`}>{h.tournament}</Link> | {POSITIONS[h.position] ?? h.position} | {h.games_played} games</p>
                      </li>))}
                  </ul>
                </Card>
              </div>
              <Card className="mt-6" eyebrow="Match history" title="Last 20 games">
                <div className="-mx-4 overflow-x-auto sm:mx-0"><table className="w-full min-w-[640px]"><thead className="border-b border-line"><tr>
                  <th className="th">Date</th><th className="th">Tournament</th><th className="th">Team</th><th className="th">Champion</th><th className="th"></th><th className="th text-right">K/D/A</th><th className="th text-right">DPM</th><th className="th text-right">CSPM</th></tr></thead>
                  <tbody>{d.recent_games.map((g, i) => (
                    <tr key={i} className="border-b border-line-soft"><td className="td text-ink-2">{fmtDate(g.date)}</td><td className="td">{g.tournament}</td><td className="td">{g.team}</td>
                      <td className="td">{g.champion ?? "n/a"}</td><td className="td"><WinLoss r={g.result} /></td>
                      <td className="td num text-right">{g.kills ?? "n/a"}/{g.deaths ?? "n/a"}/{g.assists ?? "n/a"}</td>
                      <td className="td num text-right">{fmtNum(g.dpm, 0)}</td><td className="td num text-right">{fmtNum(g.cspm)}</td></tr>))}</tbody></table></div>
              </Card>
              <SourceNote meta={meta} />
            </>
          );
        }}
      </DataState>
    </>
  );
}
