"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { GAMES, useGame } from "@/components/providers";
import { GameSwitch } from "@/components/ui/game-gate";
import { HubTabs } from "@/components/ui/hub-tabs";
import { Card, DataState, Loading, PageHeader, Pagination, Select, SourceNote } from "@/components/ui/primitives";
import { TeamTable } from "@/components/ui/tables";
import { useApi } from "@/hooks/use-api";
import type { TeamSummary } from "@/lib/api";

function TeamsInner() {
  const params = useSearchParams();
  const { game } = useGame();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [league, setLeague] = useState("");
  const [sort, setSort] = useState(params.get("sort") || "matches");
  const [minMatches, setMin] = useState("10");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [search, league, sort, minMatches, game]);
  useEffect(() => { const t = setTimeout(() => setSearch(q), 300); return () => clearTimeout(t); }, [q]);
  const filters = useApi<{ leagues: { league: string }[] }>("/tournaments/filters", { game }, game === "lol");
  const list = useApi<TeamSummary[]>("/teams", { game, q: search, league, sort, min_matches: minMatches, page, page_size: 25 });

  return (
    <>
      <PageHeader index="03" eyebrow="Teams & Players" title="Teams"
        description="Teams are identified by the source team id, so renamed organisations keep one record. Win rate counts single games. Elo is the rating after the team's last recorded game.">
        <GameSwitch />
      </PageHeader>
      <HubTabs />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1"><span className="eyebrow">Search</span>
          <input className="input" placeholder="Team name" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <Select label="Primary league" value={league} onChange={setLeague}
          options={[{ value: "", label: "All leagues" }, ...(filters.data?.data?.leagues || []).map((l) => ({ value: l.league, label: l.league }))]} />
        <Select label="Sort" value={sort} onChange={setSort} options={[
          { value: "matches", label: "Most games" }, { value: "elo", label: "Current Elo" }, { value: "win_rate", label: "Win rate" },
          { value: "recent", label: "Most recent" }, { value: "name", label: "Name" }]} />
        <Select label="Minimum games" value={minMatches} onChange={setMin}
          options={["1", "10", "25", "50", "100"].map((v) => ({ value: v, label: `${v}+` }))} />
      </div>
      <DataState query={list} gameName={GAMES.find((g) => g.slug === game)?.name} isEmpty={(d) => d.length === 0}>
        {(rows, meta) => (
          <Card>
            <TeamTable rows={rows} startRank={(page - 1) * 25 + 1} showRank={sort !== "name"} />
            {meta.pagination && <Pagination page={meta.pagination.page} pages={meta.pagination.pages} total={meta.pagination.total} onPage={setPage} />}
            <SourceNote meta={meta} extra="Win rates from small samples are noisy; use the minimum-games filter." />
          </Card>
        )}
      </DataState>
    </>
  );
}

export default function TeamsView() {
  return <Suspense fallback={<Loading />}><TeamsInner /></Suspense>;
}
