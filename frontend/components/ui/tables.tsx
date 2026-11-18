"use client";

import Link from "next/link";
import type { MatchSummary, TeamSummary } from "@/lib/api";
import { fmtDate, fmtDuration, fmtInt, fmtNum, fmtPct } from "@/lib/format";
import { cx } from "@/components/ui/primitives";

export function MatchTable({ rows, compact, highlightTeam }: { rows: MatchSummary[]; compact?: boolean; highlightTeam?: string }) {
  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full min-w-[640px]">
        <thead className="border-b border-line">
          <tr>
            <th className="th">Date</th>
            {!compact && <th className="th">Tournament</th>}
            <th className="th">Blue</th>
            <th className="th">Red</th>
            <th className="th">Winner</th>
            <th className="th text-right">Length</th>
            <th className="th"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => (
            <tr key={m.id} className="border-b border-line-soft hover:bg-bg-elev/40">
              <td className="td text-ink-2">{fmtDate(m.match_date)}</td>
              {!compact && (
                <td className="td"><Link className="hover:text-cyan" href={`/tournaments/${m.tournament_slug}`}>{m.tournament}</Link>
                  {m.playoffs && <span className="ml-2 text-2xs uppercase text-violet">playoffs</span>}</td>
              )}
              <td className={cx("td", m.winner_slug === m.blue_team_slug && "font-semibold")}>
                <Link className={cx("hover:text-cyan", highlightTeam === m.blue_team_slug && "text-cyan")} href={`/teams/${m.blue_team_slug}`}>{m.blue_team}</Link></td>
              <td className={cx("td", m.winner_slug === m.red_team_slug && "font-semibold")}>
                <Link className={cx("hover:text-cyan", highlightTeam === m.red_team_slug && "text-cyan")} href={`/teams/${m.red_team_slug}`}>{m.red_team}</Link></td>
              <td className="td"><span className="text-emerald">{m.winner}</span></td>
              <td className="td num text-right text-ink-2">{fmtDuration(m.duration_seconds)}</td>
              <td className="td text-right"><Link href={`/matches/${m.id}`} className="text-2xs font-semibold text-cyan hover:underline">Match centre</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TeamTable({ rows, startRank = 1, showRank = true }: { rows: TeamSummary[]; startRank?: number; showRank?: boolean }) {
  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full min-w-[560px]">
        <thead className="border-b border-line">
          <tr>
            {showRank && <th className="th w-10">#</th>}
            <th className="th">Team</th>
            <th className="th">League</th>
            <th className="th text-right">Games</th>
            <th className="th text-right">Win rate</th>
            <th className="th text-right">Elo</th>
            <th className="th text-right">Last game</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t, i) => (
            <tr key={t.slug} className="border-b border-line-soft hover:bg-bg-elev/40">
              {showRank && <td className="td num text-ink-3">{startRank + i}</td>}
              <td className="td"><Link className="font-medium hover:text-cyan" href={`/teams/${t.slug}`}>{t.name}</Link></td>
              <td className="td text-ink-2">{t.primary_league ?? "n/a"}</td>
              <td className="td num text-right">{fmtInt(t.n_matches)}</td>
              <td className="td num text-right">{fmtPct(t.win_rate)}</td>
              <td className="td num text-right text-violet">{fmtNum(t.current_elo, 0)}</td>
              <td className="td text-right text-ink-2">{fmtDate(t.last_match_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
