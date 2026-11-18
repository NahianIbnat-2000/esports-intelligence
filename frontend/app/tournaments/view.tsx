"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bars } from "@/components/charts/charts";
import { GAMES, useGame } from "@/components/providers";
import { GameSwitch } from "@/components/ui/game-gate";
import { Card, DataState, PageHeader, Pagination, Select, SourceNote } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import type { TournamentSummary } from "@/lib/api";
import { fmtDate, fmtInt } from "@/lib/format";

export default function TournamentsView() {
  const { game } = useGame();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [league, setLeague] = useState("");
  const [year, setYear] = useState("");
  const [sort, setSort] = useState("recent");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [search, league, year, sort, game]);
  useEffect(() => {
    const t = setTimeout(() => setSearch(q), 300);
    return () => clearTimeout(t);
  }, [q]);
  const filters = useApi<{ leagues: { league: string; n_tournaments: number }[]; years: number[] }>("/tournaments/filters", { game }, game === "lol");
  const list = useApi<TournamentSummary[]>("/tournaments", { game, q: search, league, year, sort, page, page_size: 25 });

  return (
    <>
      <PageHeader index="02" eyebrow="Tournaments" title="Tournament directory"
        description="Each tournament is one league split (league + year + split) as recorded in the source. Champions are derived from the last playoff game in the data, not from an official register. Upcoming events are not listed: this is a historical archive.">
        <GameSwitch />
      </PageHeader>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1"><span className="eyebrow">Search</span>
          <input className="input" placeholder="e.g. LCK 2024" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <Select label="League" value={league} onChange={setLeague}
          options={[{ value: "", label: "All leagues" }, ...(filters.data?.data?.leagues || []).map((l) => ({ value: l.league, label: `${l.league} (${l.n_tournaments})` }))]} />
        <Select label="Year" value={year} onChange={setYear}
          options={[{ value: "", label: "All years" }, ...(filters.data?.data?.years || []).map((y) => ({ value: String(y), label: String(y) }))]} />
        <Select label="Sort" value={sort} onChange={setSort}
          options={[{ value: "recent", label: "Most recent" }, { value: "matches", label: "Most games" }, { value: "name", label: "Name" }]} />
      </div>
      <DataState query={list} gameName={GAMES.find((g) => g.slug === game)?.name} isEmpty={(d) => d.length === 0}>
        {(rows, meta) => (
          <>
            <Card>
              <div className="-mx-4 overflow-x-auto sm:mx-0">
                <table className="w-full min-w-[720px]">
                  <thead className="border-b border-line"><tr>
                    <th className="th">Tournament</th><th className="th">League</th><th className="th">Dates</th>
                    <th className="th text-right">Games</th><th className="th text-right">Teams</th><th className="th">Derived champion</th>
                  </tr></thead>
                  <tbody>
                    {rows.map((t) => (
                      <tr key={t.slug} className="border-b border-line-soft hover:bg-bg-elev/40">
                        <td className="td"><Link className="font-medium hover:text-cyan" href={`/tournaments/${t.slug}`}>{t.name}</Link></td>
                        <td className="td text-ink-2">{t.league}</td>
                        <td className="td text-ink-2">{fmtDate(t.start_date)} to {fmtDate(t.end_date)}</td>
                        <td className="td num text-right">{fmtInt(t.n_matches)}</td>
                        <td className="td num text-right">{fmtInt(t.n_teams)}</td>
                        <td className="td">{t.derived_champion_slug ? <Link className="text-emerald hover:underline" href={`/teams/${t.derived_champion_slug}`}>{t.derived_champion}</Link> : <span className="text-ink-3">{t.has_playoffs ? "n/a" : "no playoffs in data"}</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {meta.pagination && <Pagination page={meta.pagination.page} pages={meta.pagination.pages} total={meta.pagination.total} onPage={setPage} />}
            </Card>
            {(filters.data?.data?.leagues?.length || 0) > 0 && (
              <Card className="mt-6" eyebrow="Distribution" title="Tournaments per league"
                info="Number of league splits per league code in the imported data.">
                <Bars data={(filters.data?.data?.leagues || []).slice(0, 20)} x="league" series={[{ key: "n_tournaments", label: "Tournaments" }]} height={260} />
              </Card>
            )}
            <SourceNote meta={meta} />
          </>
        )}
      </DataState>
    </>
  );
}
