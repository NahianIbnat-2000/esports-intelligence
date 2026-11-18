"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { GAMES, useGame } from "@/components/providers";
import { GameSwitch } from "@/components/ui/game-gate";
import { HubTabs } from "@/components/ui/hub-tabs";
import { Card, DataState, PageHeader, Pagination, Select, SourceNote } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import type { PlayerSummary } from "@/lib/api";
import { POSITIONS, fmtDate, fmtInt } from "@/lib/format";

export default function PlayersView() {
  const { game } = useGame();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("");
  const [sort, setSort] = useState("matches");
  const [minMatches, setMin] = useState("10");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [search, position, sort, minMatches, game]);
  useEffect(() => { const t = setTimeout(() => setSearch(q), 300); return () => clearTimeout(t); }, [q]);
  const list = useApi<PlayerSummary[]>("/players", { game, q: search, position, sort, min_matches: minMatches, page, page_size: 25 });
  return (
    <>
      <PageHeader index="03" eyebrow="Teams & Players" title="Players"
        description="Players are identified by the source player id. Team affiliation is the team they most recently played for in the data. Positions: top, jungle, mid, bot, support.">
        <GameSwitch />
      </PageHeader>
      <HubTabs />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1"><span className="eyebrow">Search</span>
          <input className="input" placeholder="Player name" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <Select label="Position" value={position} onChange={setPosition}
          options={[{ value: "", label: "All positions" }, ...Object.entries(POSITIONS).map(([v, l]) => ({ value: v, label: l }))]} />
        <Select label="Sort" value={sort} onChange={setSort} options={[{ value: "matches", label: "Most games" }, { value: "recent", label: "Most recent" }, { value: "name", label: "Name" }]} />
        <Select label="Minimum games" value={minMatches} onChange={setMin} options={["1", "10", "25", "50", "100"].map((v) => ({ value: v, label: `${v}+` }))} />
      </div>
      <DataState query={list} gameName={GAMES.find((g) => g.slug === game)?.name} isEmpty={(d) => d.length === 0}>
        {(rows, meta) => (
          <Card>
            <div className="-mx-4 overflow-x-auto sm:mx-0">
              <table className="w-full min-w-[600px]">
                <thead className="border-b border-line"><tr><th className="th">Player</th><th className="th">Position</th><th className="th">Latest team</th><th className="th text-right">Games</th><th className="th text-right">Last game</th></tr></thead>
                <tbody>{rows.map((p) => (
                  <tr key={p.slug} className="border-b border-line-soft hover:bg-bg-elev/40">
                    <td className="td"><Link className="font-medium hover:text-cyan" href={`/players/${p.slug}`}>{p.name}</Link></td>
                    <td className="td text-ink-2">{p.primary_position ? POSITIONS[p.primary_position] : "n/a"}</td>
                    <td className="td">{p.latest_team_slug ? <Link className="hover:text-cyan" href={`/teams/${p.latest_team_slug}`}>{p.latest_team}</Link> : "n/a"}</td>
                    <td className="td num text-right">{fmtInt(p.n_matches)}</td>
                    <td className="td text-right text-ink-2">{fmtDate(p.last_match_date)}</td>
                  </tr>))}</tbody>
              </table>
            </div>
            {meta.pagination && <Pagination page={meta.pagination.page} pages={meta.pagination.pages} total={meta.pagination.total} onPage={setPage} />}
            <SourceNote meta={meta} />
          </Card>
        )}
      </DataState>
    </>
  );
}
