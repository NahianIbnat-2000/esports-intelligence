"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRight } from "lucide-react";
import { Crest, TEAM_A, TEAM_B } from "@/components/ui/match-bits";
import { Card, DataState, PageHeader, Pagination, Select, SourceNote, cx } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import { fmtDate } from "@/lib/format";

interface SeriesRow {
  id: number; start: string; end: string; tournament: string; tournament_slug: string; league: string; playoffs: boolean;
  team_a: string; team_a_slug: string; team_b: string; team_b_slug: string; wins_a: number; wins_b: number; n_games: number;
  winner_slug: string | null; games: { id: number; winner_slug: string | null }[];
}

export default function Matches() {
  const [league, setLeague] = useState("");
  const [page, setPage] = useState(1);
  const filters = useApi<{ leagues: { league: string; n_tournaments: number }[] }>("/tournaments/filters", { game: "lol" });
  const q = useApi<SeriesRow[]>("/series", { game: "lol", league: league || undefined, page, page_size: 30 });
  return (
    <>
      <PageHeader eyebrow="Matches" title="Match centre"
        description="Every recorded series, newest first. Open a game for Elo changes, pre-game probabilities, player lines, team stats and objectives.">
        <Select label="League" className="w-48" value={league} onChange={(v) => { setLeague(v); setPage(1); }}
          options={[{ value: "", label: "All leagues" }, ...(filters.data?.data?.leagues ?? []).map((l) => ({ value: l.league, label: l.league }))]} />
      </PageHeader>
      <DataState query={q} isEmpty={(d) => d.length === 0}>
        {(rows, meta) => (
          <Card title="Series">
            <ul className="divide-y divide-line-soft">
              {rows.map((s) => {
                const aWon = s.winner_slug === s.team_a_slug, bWon = s.winner_slug === s.team_b_slug;
                const last = s.games[s.games.length - 1];
                return (
                  <li key={s.id}>
                  {/* phones: compact two-line row */}
                  <Link href={`/matches/${last.id}`} className="flex items-center gap-3 py-2.5 sm:hidden">
                    <span className="min-w-0 flex-1">
                      <span className="block text-2xs text-ink-3">{fmtDate(s.end)} · {s.league}{s.playoffs ? " · PO" : ""}</span>
                      <span className="mt-0.5 flex items-center gap-2 text-sm">
                        <span className={cx("truncate", aWon ? "font-semibold text-ink" : "text-ink-2")}>{s.team_a}</span>
                        <span className="num shrink-0 font-bold"><span className={aWon ? "text-ink" : "text-ink-3"}>{s.wins_a}</span><span className="mx-1 text-ink-3">:</span><span className={bWon ? "text-ink" : "text-ink-3"}>{s.wins_b}</span></span>
                        <span className={cx("truncate", bWon ? "font-semibold text-ink" : "text-ink-2")}>{s.team_b}</span>
                      </span>
                    </span>
                    <ChevronRight size={14} className="shrink-0 text-ink-3" />
                  </Link>
                  <div className="hidden items-center gap-3 py-2.5 sm:grid sm:grid-cols-[110px_1fr_auto_1fr_auto] sm:px-2">
                    <span className="text-2xs text-ink-3">{fmtDate(s.end)}<br /><span className="text-ink-2">{s.league}</span>{s.playoffs && <span className="ml-1 text-cyan">PO</span>}</span>
                    <Link href={`/matches/${last.id}`} className="group contents">
                      <span className="flex items-center justify-end gap-2 text-sm">
                        <span className={cx("truncate", aWon ? "font-semibold text-ink" : "text-ink-2")}>{s.team_a}</span>
                        <Crest name={s.team_a} color={TEAM_A} size={24} />
                      </span>
                      <span className="num w-16 text-center text-base font-bold">
                        <span className={aWon ? "text-ink" : "text-ink-3"}>{s.wins_a}</span>
                        <span className="mx-1.5 text-ink-3">:</span>
                        <span className={bWon ? "text-ink" : "text-ink-3"}>{s.wins_b}</span>
                      </span>
                      <span className="flex items-center gap-2 text-sm">
                        <Crest name={s.team_b} color={TEAM_B} size={24} />
                        <span className={cx("truncate", bWon ? "font-semibold text-ink" : "text-ink-2")}>{s.team_b}</span>
                      </span>
                    </Link>
                    <span className="flex items-center justify-end gap-1">
                      {s.games.map((g, i) => (
                        <Link key={g.id} href={`/matches/${g.id}`} title={`Game ${i + 1}`}
                          className="flex h-6 w-6 items-center justify-center rounded-sm border border-line text-[10px] font-semibold hover:border-cyan"
                          style={{ color: g.winner_slug === s.team_a_slug ? TEAM_A : TEAM_B }}>
                          G{i + 1}
                        </Link>
                      ))}
                      <ChevronRight size={14} className="ml-1 text-ink-3" />
                    </span>
                  </div>
                  </li>
                );
              })}
            </ul>
            {meta?.pagination && <Pagination page={page} pages={meta.pagination.pages} total={meta.pagination.total} onPage={setPage} />}
            <SourceNote meta={meta} extra="Gold = first-listed team, green = second. G1, G2... open single games, coloured by their winner. Crests are generated from team names; no logos are used." />
          </Card>
        )}
      </DataState>
    </>
  );
}
