"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { TimeLine } from "@/components/charts/charts";
import { Breadcrumbs, Card, DataState, PageHeader, SourceNote, Stat, WinLoss } from "@/components/ui/primitives";
import { MatchTable } from "@/components/ui/tables";
import { useApi } from "@/hooks/use-api";
import type { MatchSummary, TeamSummary } from "@/lib/api";
import { POSITIONS, fmtDate, fmtInt, fmtNum, fmtPct } from "@/lib/format";

interface Detail {
  team: TeamSummary;
  elo_history: { date: string; elo: number }[];
  recent_matches: MatchSummary[];
  recent_form: number[];
  tournaments: { slug: string; name: string; year: number; start_date: string; games: number; wins: number; win_rate: number | null }[];
  head_to_head: { opponent_slug: string; opponent: string; games: number; wins: number; losses: number }[];
  roster_latest_tournament: { player_slug: string; player: string; position: string; games_played: number }[];
  side_split: { side: string; games: number; wins: number; win_rate: number | null }[];
  averages: { golddiff_at_15: number | null; dragons: number | null; barons: number | null; towers: number | null; duration_minutes: number | null; n_games_with_15min_data: number };
  notes: string[];
}

export default function TeamDetail() {
  const { slug } = useParams<{ slug: string }>();
  const q = useApi<Detail>(`/teams/${slug}`, { game: "lol" });
  return (
    <>
      <Breadcrumbs items={[{ label: "Teams", href: "/teams" }, { label: q.data?.data?.team.name || slug }]} />
      <DataState query={q}>
        {(d, meta) => {
          const t = d.team;
          const elo = d.elo_history.map((p) => ({ date: p.date.slice(0, 10), elo: Math.round(p.elo) }));
          return (
            <>
              <PageHeader eyebrow={`Team | ${t.primary_league ?? "league n/a"}`} title={t.name}
                description={`Recorded from ${fmtDate(t.first_match_date)} to ${fmtDate(t.last_match_date)}.`}>
                <Link href={`/teams/compare?a=${t.slug}`} className="btn">Compare</Link>
              </PageHeader>
              <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-5">
                <Stat label="Games" value={fmtInt(t.n_matches)} />
                <Stat label="Win rate" value={fmtPct(t.win_rate)} accent="emerald" />
                <Stat label="Current Elo" value={fmtNum(t.current_elo, 0)} info="Rating after the team's last recorded game. Inactive teams keep their last rating." />
                <Stat label="Gold diff @15" value={fmtNum(d.averages.golddiff_at_15, 0)} accent="violet" info={`Average team gold difference at 15:00 over ${d.averages.n_games_with_15min_data} games with this data.`} />
                <div className="card p-4">
                  <p className="eyebrow">Recent form</p>
                  <div className="mt-3 flex flex-wrap gap-1" aria-label="Last 10 results, oldest first">{d.recent_form.map((r, i) => <WinLoss key={i} r={r} />)}</div>
                </div>
              </div>
              <div className="grid gap-6 xl:grid-cols-3">
                <Card className="xl:col-span-2" eyebrow="Performance trend" title="Elo rating over time"
                  info="Elo after each game. Every team starts at 1500; regions are linked only through international games.">
                  {elo.length ? <TimeLine data={elo} x="date" series={[{ key: "elo", label: "Elo" }]} reference={{ y: 1500, label: "start 1500" }} height={280} />
                    : <p className="text-sm text-ink-2">Elo has not been computed yet.</p>}
                </Card>
                <Card eyebrow="Roster" title="Players in latest tournament" info={d.notes[0]}>
                  {d.roster_latest_tournament.length === 0 ? <p className="text-sm text-ink-2">No player rows recorded.</p> : (
                    <ul className="divide-y divide-line-soft">
                      {d.roster_latest_tournament.map((p) => (
                        <li key={p.player_slug + p.position} className="flex items-center justify-between py-2 text-sm">
                          <Link href={`/players/${p.player_slug}`} className="hover:text-cyan">{p.player}</Link>
                          <span className="text-xs text-ink-2">{POSITIONS[p.position] ?? p.position} | {p.games_played} games</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    {d.side_split.map((s) => (
                      <div key={s.side} className="rounded-md border border-line bg-bg-2 p-2.5">
                        <p className="eyebrow">{s.side} side</p>
                        <p className="num text-lg">{fmtPct(s.win_rate)}</p>
                        <p className="text-2xs text-ink-3">{s.games} games</p>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
              <div className="mt-6 grid gap-6 xl:grid-cols-2">
                <Card eyebrow="Tournament history" title="By tournament">
                  <div className="max-h-96 overflow-y-auto">
                    <div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th">Tournament</th><th className="th text-right">W-L</th><th className="th text-right">Win %</th></tr></thead>
                      <tbody>{d.tournaments.map((x) => (
                        <tr key={x.slug} className="border-b border-line-soft"><td className="td"><Link className="hover:text-cyan" href={`/tournaments/${x.slug}`}>{x.name}</Link></td>
                          <td className="td num text-right">{x.wins}-{x.games - x.wins}</td><td className="td num text-right">{fmtPct(x.win_rate)}</td></tr>))}</tbody></table></div>
                  </div>
                </Card>
                <Card eyebrow="Head-to-head" title="Most frequent opponents">
                  <div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th">Opponent</th><th className="th text-right">Games</th><th className="th text-right">W-L</th><th className="th"></th></tr></thead>
                    <tbody>{d.head_to_head.map((h) => (
                      <tr key={h.opponent_slug} className="border-b border-line-soft"><td className="td"><Link className="hover:text-cyan" href={`/teams/${h.opponent_slug}`}>{h.opponent}</Link></td>
                        <td className="td num text-right">{h.games}</td><td className="td num text-right">{h.wins}-{h.losses}</td>
                        <td className="td text-right"><Link className="link text-xs" href={`/teams/compare?a=${t.slug}&b=${h.opponent_slug}`}>details</Link></td></tr>))}</tbody></table></div>
                </Card>
              </div>
              <Card className="mt-6" eyebrow="Match history" title="Last 20 games"
                actions={<Link className="link text-xs" href={`/data-explorer?dataset=team_games&team=${encodeURIComponent(t.name)}`}>All games in Data Explorer</Link>}>
                <MatchTable rows={d.recent_matches} highlightTeam={t.slug} />
              </Card>
              {d.notes.slice(1).map((n) => <p key={n} className="mt-3 text-xs text-amber">{n}</p>)}
              <SourceNote meta={meta} />
            </>
          );
        }}
      </DataState>
    </>
  );
}
