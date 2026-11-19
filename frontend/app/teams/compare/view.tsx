"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { TimeLine } from "@/components/charts/charts";
import { CHART } from "@/lib/chart-theme";
import { EntityPicker } from "@/components/ui/entity-picker";
import { LolOnly } from "@/components/ui/game-gate";
import { HubTabs } from "@/components/ui/hub-tabs";
import { Card, DataState, EmptyState, Loading, PageHeader, SourceNote, Stat } from "@/components/ui/primitives";
import { MatchTable } from "@/components/ui/tables";
import { useApi } from "@/hooks/use-api";
import type { MatchSummary, TeamSummary } from "@/lib/api";
import { fmtInt, fmtNum, fmtPct } from "@/lib/format";

interface H2H {
  team_a: TeamSummary; team_b: TeamSummary; games: number; wins_a: number; wins_b: number; matches: MatchSummary[];
  elo_history_a: { date: string; elo: number }[]; elo_history_b: { date: string; elo: number }[];
}

function mergeElo(a: H2H["elo_history_a"], b: H2H["elo_history_b"]) {
  const m = new Map<string, { date: string; a?: number; b?: number }>();
  a.forEach((p) => m.set(p.date.slice(0, 10), { ...(m.get(p.date.slice(0, 10)) || { date: p.date.slice(0, 10) }), a: Math.round(p.elo) }));
  b.forEach((p) => m.set(p.date.slice(0, 10), { ...(m.get(p.date.slice(0, 10)) || { date: p.date.slice(0, 10) }), b: Math.round(p.elo) }));
  return Array.from(m.values()).sort((x, y) => x.date.localeCompare(y.date));
}

function Inner() {
  const router = useRouter();
  const sp = useSearchParams();
  const a = sp.get("a") || "";
  const b = sp.get("b") || "";
  const set = (k: "a" | "b", v: string) => {
    const p = new URLSearchParams(sp.toString());
    p.set(k, v);
    router.replace(`/teams/compare?${p.toString()}`);
  };
  const q = useApi<H2H>(a && b ? "/teams/compare" : null, { game: "lol", a, b });
  return (
    <>
      <PageHeader index="03" eyebrow="Teams & Players" title="Compare teams" description="Head-to-head record in single games and Elo paths over time." />
      <HubTabs />
      <LolOnly>
        <div className="mb-6 grid gap-3 sm:grid-cols-2">
          <EntityPicker kind="teams" label="Team A" value={a} onChange={(s) => set("a", s)} />
          <EntityPicker kind="teams" label="Team B" value={b} onChange={(s) => set("b", s)} />
        </div>
        {!(a && b) ? <EmptyState title="Select two teams to compare" /> : (
          <DataState query={q}>
            {(d, meta) => (
              <>
                <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
                  <Stat label="Head-to-head games" value={fmtInt(d.games)} />
                  <Stat label={`${d.team_a.name} wins`} value={fmtInt(d.wins_a)} />
                  <Stat label={`${d.team_b.name} wins`} value={fmtInt(d.wins_b)} accent="violet" />
                  <Stat label="Current Elo gap" value={d.team_a.current_elo !== null && d.team_b.current_elo !== null ? fmtNum(d.team_a.current_elo - d.team_b.current_elo, 0) : "n/a"} accent="emerald" info="Team A minus Team B, after each team's last recorded game." />
                </div>
                <div className="grid gap-6 xl:grid-cols-3">
                  <Card className="xl:col-span-2" eyebrow="Elo" title="Rating paths">
                    <TimeLine data={mergeElo(d.elo_history_a, d.elo_history_b)} x="date" height={280}
                      series={[{ key: "a", label: d.team_a.name, color: CHART.cyan }, { key: "b", label: d.team_b.name, color: CHART.violet }]} />
                    <p className="mt-2 text-2xs text-ink-3">Breaks in a line are periods without games.</p>
                  </Card>
                  <Card eyebrow="Career" title="Overall records">
                    <div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th"></th><th className="th text-right">A</th><th className="th text-right">B</th></tr></thead>
                      <tbody>
                        {([["Games", fmtInt(d.team_a.n_matches), fmtInt(d.team_b.n_matches)], ["Win rate", fmtPct(d.team_a.win_rate), fmtPct(d.team_b.win_rate)],
                          ["Current Elo", fmtNum(d.team_a.current_elo, 0), fmtNum(d.team_b.current_elo, 0)], ["League", d.team_a.primary_league ?? "n/a", d.team_b.primary_league ?? "n/a"]] as const)
                          .map(([l, x, y]) => <tr key={l} className="border-b border-line-soft"><td className="td text-ink-2">{l}</td><td className="td num text-right">{x}</td><td className="td num text-right">{y}</td></tr>)}
                      </tbody></table></div>
                  </Card>
                </div>
                <Card className="mt-6" eyebrow="Head-to-head" title="Games between these teams">
                  {d.matches.length ? <MatchTable rows={d.matches} /> : <p className="text-sm text-ink-2">These teams have not played each other in the data.</p>}
                </Card>
                <SourceNote meta={meta} />
              </>
            )}
          </DataState>
        )}
      </LolOnly>
    </>
  );
}

export default function CompareTeams() {
  return <Suspense fallback={<Loading />}><Inner /></Suspense>;
}
