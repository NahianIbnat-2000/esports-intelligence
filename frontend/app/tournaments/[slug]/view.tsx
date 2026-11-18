"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Breadcrumbs, Card, DataState, PageHeader, Segmented, SourceNote, Stat } from "@/components/ui/primitives";
import { MatchTable } from "@/components/ui/tables";
import { useApi } from "@/hooks/use-api";
import type { MatchSummary, TournamentSummary } from "@/lib/api";
import { fmtDate, fmtInt, fmtNum, fmtPct } from "@/lib/format";

interface Standing { team_slug: string; team: string; games: number; wins: number; losses: number; win_rate: number | null }
interface Detail {
  tournament: TournamentSummary;
  standings_regular_season: Standing[];
  standings_playoffs: Standing[];
  standings_all: Standing[];
  matches: MatchSummary[];
  matches_truncated: boolean;
  stats: { avg_duration_minutes: number | null; blue_win_rate: number | null };
  champion_note: string;
}

export default function TournamentDetail() {
  const { slug } = useParams<{ slug: string }>();
  const q = useApi<Detail>(`/tournaments/${slug}`, { game: "lol" });
  const [stage, setStage] = useState<"regular" | "playoffs" | "all">("regular");
  return (
    <>
      <Breadcrumbs items={[{ label: "Tournaments", href: "/tournaments" }, { label: q.data?.data?.tournament.name || slug }]} />
      <DataState query={q}>
        {(d, meta) => {
          const t = d.tournament;
          const table = stage === "regular" ? d.standings_regular_season : stage === "playoffs" ? d.standings_playoffs : d.standings_all;
          return (
            <>
              <PageHeader eyebrow={`${t.league} | ${t.year ?? ""} ${t.split ?? ""}`} title={t.name}
                description={`${fmtDate(t.start_date)} to ${fmtDate(t.end_date)}. Standings are win-loss records of single games; they may differ from official standings that count series.`} />
              <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Games" value={fmtInt(t.n_matches)} />
                <Stat label="Teams" value={fmtInt(t.n_teams)} accent="violet" />
                <Stat label="Avg game length" value={d.stats.avg_duration_minutes ? `${fmtNum(d.stats.avg_duration_minutes, 1)} min` : "n/a"} accent="violet" />
                <Stat label="Derived champion" value={<span className="text-lg">{t.derived_champion ?? "n/a"}</span>} accent="emerald" info={d.champion_note} />
              </div>
              <div className="grid gap-6 xl:grid-cols-5">
                <Card className="xl:col-span-2" eyebrow="Standings" title="Game win-loss"
                  actions={<Segmented label="Stage" value={stage} onChange={setStage} options={[
                    { value: "regular", label: "Regular" }, ...(t.has_playoffs ? [{ value: "playoffs" as const, label: "Playoffs" }] : []), { value: "all", label: "All" }]} />}>
                  {table.length === 0 ? <p className="text-sm text-ink-2">No games for this stage.</p> : (
                    <table className="w-full">
                      <thead className="border-b border-line"><tr><th className="th w-8">#</th><th className="th">Team</th><th className="th text-right">W</th><th className="th text-right">L</th><th className="th text-right">Win %</th></tr></thead>
                      <tbody>{table.map((s, i) => (
                        <tr key={s.team_slug} className="border-b border-line-soft">
                          <td className="td num text-ink-3">{i + 1}</td>
                          <td className="td"><Link className="hover:text-cyan" href={`/teams/${s.team_slug}`}>{s.team}</Link></td>
                          <td className="td num text-right">{s.wins}</td><td className="td num text-right">{s.losses}</td>
                          <td className="td num text-right">{fmtPct(s.win_rate)}</td>
                        </tr>))}</tbody>
                    </table>
                  )}
                  <p className="mt-3 text-2xs text-ink-3">Blue side won {fmtPct(d.stats.blue_win_rate)} of games in this tournament.</p>
                </Card>
                <Card className="xl:col-span-3" eyebrow="Results" title="Games" info={d.matches_truncated ? "Showing the latest 500 games. Use the Data Explorer for all games." : undefined}>
                  <div className="max-h-[560px] overflow-y-auto"><MatchTable rows={d.matches} compact /></div>
                </Card>
              </div>
              <p className="mt-4 text-xs text-ink-3">Prize distribution: not available in the source data.</p>
              <SourceNote meta={meta} />
            </>
          );
        }}
      </DataState>
    </>
  );
}
