"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Card, EmptyState, Loading, PageHeader } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import type { PlayerSummary, TeamSummary, TournamentSummary } from "@/lib/api";
import { POSITIONS, fmtDate, fmtInt } from "@/lib/format";

function Inner() {
  const q = useSearchParams().get("q") || "";
  const teams = useApi<TeamSummary[]>("/teams", { game: "lol", q, page_size: 10, sort: "matches" }, !!q);
  const players = useApi<PlayerSummary[]>("/players", { game: "lol", q, page_size: 10, sort: "matches" }, !!q);
  const tours = useApi<TournamentSummary[]>("/tournaments", { game: "lol", q, page_size: 10 }, !!q);
  const err = teams.error || players.error || tours.error;
  return (
    <>
      <PageHeader eyebrow="Search" title={q ? `Results for "${q}"` : "Search"} description="Searches team, player and tournament names in the League of Legends archive." />
      {!q ? <EmptyState title="Type a name in the search box" /> : err ? <EmptyState title="Search failed">{err.message}</EmptyState> : (
        <div className="grid gap-3 lg:grid-cols-3">
          <Card title="Teams">{teams.isLoading ? <Loading /> : (teams.data?.data || []).length === 0 ? <p className="text-sm text-ink-2">No teams.</p> :
            <ul className="divide-y divide-line-soft">{teams.data!.data!.map((t) => <li key={t.slug} className="flex justify-between py-2 text-sm"><Link className="hover:text-cyan" href={`/teams/${t.slug}`}>{t.name}</Link><span className="text-xs text-ink-3">{t.primary_league} | {fmtInt(t.n_matches)}</span></li>)}</ul>}</Card>
          <Card title="Players">{players.isLoading ? <Loading /> : (players.data?.data || []).length === 0 ? <p className="text-sm text-ink-2">No players.</p> :
            <ul className="divide-y divide-line-soft">{players.data!.data!.map((p) => <li key={p.slug} className="flex justify-between py-2 text-sm"><Link className="hover:text-cyan" href={`/players/${p.slug}`}>{p.name}</Link><span className="text-xs text-ink-3">{p.primary_position ? POSITIONS[p.primary_position] : ""} | {p.latest_team ?? ""}</span></li>)}</ul>}</Card>
          <Card title="Tournaments">{tours.isLoading ? <Loading /> : (tours.data?.data || []).length === 0 ? <p className="text-sm text-ink-2">No tournaments.</p> :
            <ul className="divide-y divide-line-soft">{tours.data!.data!.map((t) => <li key={t.slug} className="flex justify-between py-2 text-sm"><Link className="hover:text-cyan" href={`/tournaments/${t.slug}`}>{t.name}</Link><span className="text-xs text-ink-3">{fmtDate(t.start_date)}</span></li>)}</ul>}</Card>
        </div>
      )}
    </>
  );
}

export default function SearchView() {
  return <Suspense fallback={<Loading />}><Inner /></Suspense>;
}
