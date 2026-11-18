"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { Crest, TEAM_A, TEAM_B } from "@/components/ui/match-bits";
import { Card, DataState, PageHeader, Pagination, Select, SourceNote, cx } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import type { MatchSummary } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";

export default function Matches() {
  const [league, setLeague] = useState("");
  const [page, setPage] = useState(1);
  const filters = useApi<{ leagues: { league: string; n_tournaments: number }[] }>("/tournaments/filters", { game: "lol" });
  const q = useApi<MatchSummary[]>("/matches", { game: "lol", league: league || undefined, page, page_size: 30 });
  return (
    <>
      <PageHeader eyebrow="Matches" title="Match centre"
        description="Every recorded game, newest first. Open a game for Elo changes, pre-game probabilities, player lines, team stats and objectives." >
        <Select label="League" className="w-48" value={league} onChange={(v) => { setLeague(v); setPage(1); }}
          options={[{ value: "", label: "All leagues" }, ...(filters.data?.data?.leagues ?? []).map((l) => ({ value: l.league, label: l.league }))]} />
      </PageHeader>
      <DataState query={q} isEmpty={(d) => d.length === 0}>
        {(rows, meta) => (
          <Card title="Games">
            <ul className="divide-y divide-line-soft">
              {rows.map((m) => {
                const blueWon = m.winner_slug === m.blue_team_slug;
                return (
                  <li key={m.id}>
                    <Link href={`/matches/${m.id}`} className="group grid grid-cols-[1fr_auto] items-center gap-3 py-2.5 hover:bg-bg-elev/40 sm:grid-cols-[110px_1fr_auto_1fr_90px_20px] sm:px-2">
                      <span className="hidden text-2xs text-ink-3 sm:block">{fmtDate(m.match_date)}<br /><span className="text-ink-2">{m.league}</span>{m.playoffs && <span className="ml-1 text-cyan">PO</span>}</span>
                      <span className="flex items-center justify-end gap-2 text-sm">
                        <span className={cx("truncate", blueWon ? "font-semibold text-ink" : "text-ink-2")}>{m.blue_team}</span>
                        <Crest name={m.blue_team} color={TEAM_A} size={24} />
                      </span>
                      <span className="num hidden w-16 text-center text-sm font-bold sm:block">
                        <span className={blueWon ? "text-ink" : "text-ink-3"}>{blueWon ? 1 : 0}</span>
                        <span className="mx-1.5 text-ink-3">:</span>
                        <span className={!blueWon ? "text-ink" : "text-ink-3"}>{blueWon ? 0 : 1}</span>
                      </span>
                      <span className="hidden items-center gap-2 text-sm sm:flex">
                        <Crest name={m.red_team} color={TEAM_B} size={24} />
                        <span className={cx("truncate", !blueWon ? "font-semibold text-ink" : "text-ink-2")}>{m.red_team}</span>
                      </span>
                      <span className="hidden text-right text-2xs text-ink-3 sm:block">{m.game_in_series ? `Game ${m.game_in_series} · ` : ""}{fmtDuration(m.duration_seconds)}</span>
                      <ChevronRight size={14} className="text-ink-3 group-hover:text-cyan" />
                    </Link>
                  </li>
                );
              })}
            </ul>
            {meta?.pagination && <Pagination page={page} pages={meta.pagination.pages} total={meta.pagination.total} onPage={setPage} />}
            <SourceNote meta={meta} extra="Gold = blue side, green = red side. Crests are generated from team names; no logos are used." />
          </Card>
        )}
      </DataState>
    </>
  );
}
