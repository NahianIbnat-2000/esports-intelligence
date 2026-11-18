"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Download } from "lucide-react";
import { GAMES, useGame } from "@/components/providers";
import { GameSwitch } from "@/components/ui/game-gate";
import { Card, DataState, Loading, PageHeader, Pagination, Select, SourceNote, cx } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import { buildUrl } from "@/lib/api";
import { POSITIONS, fmtDateTime } from "@/lib/format";
import { EntityPicker } from "@/components/ui/entity-picker";

interface DatasetInfo { key: string; label: string; columns: { name: string; description: string }[] }
interface Rows { columns: string[]; rows: Record<string, unknown>[] }

function cell(v: unknown, col: string) {
  if (v === null || v === undefined) return <span className="text-ink-3">null</span>;
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("en-US") : v.toFixed(3);
  if ((col === "date" || col.endsWith("_date") || col.endsWith("_game")) && typeof v === "string") return fmtDateTime(v);
  return String(v);
}

function Inner() {
  const sp = useSearchParams();
  const { game } = useGame();
  const datasets = useApi<DatasetInfo[]>("/data-explorer/datasets");
  const [dataset, setDataset] = useState(sp.get("dataset") || "matches");
  const [q, setQ] = useState(sp.get("q") || "");
  const [search, setSearch] = useState(sp.get("q") || "");
  const [league, setLeague] = useState("");
  const [dateFrom, setFrom] = useState("");
  const [dateTo, setTo] = useState("");
  const [season, setSeason] = useState("");
  const [tournament, setTournament] = useState("");
  const [team, setTeam] = useState<{ slug: string; name: string }>({ slug: "", name: sp.get("team") || "" });
  const [player, setPlayer] = useState<{ slug: string; name: string }>({ slug: "", name: "" });
  const [position, setPosition] = useState("");
  const [sort, setSort] = useState<string | null>(null);
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [showDict, setShowDict] = useState(false);
  const info = datasets.data?.data?.find((d) => d.key === dataset);
  const visible = useMemo(() => (info?.columns || []).map((c) => c.name).filter((c) => !hidden.has(c)), [info, hidden]);
  useEffect(() => { setPage(1); }, [dataset, search, league, dateFrom, dateTo, sort, order, game, season, tournament, team, player, position]);
  useEffect(() => { setHidden(new Set()); setSort(null); }, [dataset]);
  useEffect(() => { const t = setTimeout(() => setSearch(q), 300); return () => clearTimeout(t); }, [q]);
  const filters = useApi<{ leagues: { league: string }[]; years: number[] }>("/tournaments/filters", { game }, game === "lol");
  const tours = useApi<{ name: string }[]>("/tournaments", { game, league, year: season, page_size: 200, sort: "recent" }, game === "lol" && !!(league || season));
  const params = { dataset, game, q: search, league, date_from: dateFrom || undefined, date_to: dateTo ? `${dateTo}T23:59:59Z` : undefined,
    sort: sort || undefined, order, columns: visible.join(","), season: season || undefined, tournament: tournament || undefined,
    team: team.name || undefined, player: player.name || undefined, position: position || undefined };
  const hasCol = (c: string) => (info?.columns || []).some((x) => x.name === c);
  const data = useApi<Rows>("/data-explorer", { ...params, page, page_size: 50 }, !!info);
  const toggleSort = (c: string) => { if (sort === c) setOrder(order === "asc" ? "desc" : "asc"); else { setSort(c); setOrder("desc"); } };

  return (
    <>
      <PageHeader index="08" eyebrow="Data Explorer" title="Inspect the records"
        description="Browse the processed tables behind every chart. Missing values are shown as null. Exports include at most 5,000 rows and must keep the source attribution (Oracle's Elixir; game statistics © Riot Games; non-commercial use).">
        <GameSwitch />
      </PageHeader>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Select label="Dataset" value={dataset} onChange={setDataset} options={(datasets.data?.data || [{ key: "matches", label: "Matches" }]).map((d) => ({ value: d.key, label: d.label }))} />
        <label className="flex flex-col gap-1"><span className="eyebrow">Search names</span><input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="team, player, tournament" /></label>
        <Select label="League" value={league} onChange={setLeague} options={[{ value: "", label: "All leagues" }, ...(filters.data?.data?.leagues || []).map((l) => ({ value: l.league, label: l.league }))]} />
        <label className="flex flex-col gap-1"><span className="eyebrow">From</span><input type="date" className="input" value={dateFrom} onChange={(e) => setFrom(e.target.value)} /></label>
        <label className="flex flex-col gap-1"><span className="eyebrow">To</span><input type="date" className="input" value={dateTo} onChange={(e) => setTo(e.target.value)} /></label>
      </div>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Select label="Season" value={season} onChange={setSeason} options={[{ value: "", label: "All seasons" }, ...(filters.data?.data?.years || []).map((y) => ({ value: String(y), label: String(y) }))]} />
        <Select label={league || season ? "Tournament" : "Tournament (pick league or season first)"} value={tournament} onChange={setTournament}
          options={[{ value: "", label: "All tournaments" }, ...(tours.data?.data || []).map((t) => ({ value: t.name, label: t.name }))]} />
        <div>{hasCol("team") || hasCol("blue_team") ? <EntityPicker kind="teams" label="Team" value={team.slug} onChange={(slug, name) => setTeam({ slug, name })} minMatches={1} /> : <p className="eyebrow pt-6 text-ink-3">Team filter n/a</p>}</div>
        <div>{hasCol("player") ? <EntityPicker kind="players" label="Player" value={player.slug} onChange={(slug, name) => setPlayer({ slug, name })} minMatches={1} /> : <p className="eyebrow pt-6 text-ink-3">Player filter: player games only</p>}</div>
        <Select label="Role" value={position} onChange={setPosition} options={[{ value: "", label: hasCol("position") ? "All roles" : "Role: player games only" }, ...Object.entries(POSITIONS).map(([v, l]) => ({ value: v, label: l }))]} />
      </div>
      {(team.name || player.name || tournament || season || position) && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-xs text-ink-2">Active filters:
          {[["season", season], ["tournament", tournament], ["team", team.name], ["player", player.name], ["role", position]].filter(([, v]) => v).map(([k, v]) => <span key={k} className="rounded border border-line px-2 py-0.5">{k}: {v}</span>)}
          <button className="link" onClick={() => { setSeason(""); setTournament(""); setTeam({ slug: "", name: "" }); setPlayer({ slug: "", name: "" }); setPosition(""); }}>clear</button>
        </div>
      )}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <details className="relative">
          <summary className="btn cursor-pointer list-none">Columns ({visible.length}/{info?.columns.length || 0})</summary>
          <div className="absolute z-20 mt-1 max-h-80 w-64 overflow-y-auto rounded-md border border-line bg-bg-elev p-2 shadow-card">
            {(info?.columns || []).map((c) => (
              <label key={c.name} className="flex items-center gap-2 px-1 py-1 text-sm">
                <input type="checkbox" checked={!hidden.has(c.name)} onChange={() => { const h = new Set(hidden); if (h.has(c.name)) h.delete(c.name); else h.add(c.name); setHidden(h); }} />
                {c.name}
              </label>
            ))}
          </div>
        </details>
        <button className="btn" onClick={() => setShowDict(!showDict)} aria-expanded={showDict}>Data dictionary</button>
        <a className={cx("btn", (game !== "lol" || data.data?.meta.data_status !== "available") && "pointer-events-none opacity-50")}
          href={buildUrl("/data-explorer/export", params)} aria-disabled={game !== "lol"}><Download size={14} /> Export CSV</a>
      </div>
      {showDict && info && (
        <Card className="mb-4" title={`Dictionary: ${info.label}`}>
          <dl className="grid gap-x-6 gap-y-2 md:grid-cols-2">{info.columns.map((c) => <div key={c.name}><dt className="font-mono text-xs text-cyan">{c.name}</dt><dd className="text-xs text-ink-2">{c.description}</dd></div>)}</dl>
        </Card>
      )}
      <DataState query={data} gameName={GAMES.find((g) => g.slug === game)?.name} isEmpty={(d) => d.rows.length === 0}>
        {(d, meta) => (
          <Card>
            <div className="-mx-4 overflow-x-auto sm:mx-0">
              <table className="w-full">
                <thead className="border-b border-line"><tr>{d.columns.map((c) => (
                  <th key={c} className="th" aria-sort={sort === c ? (order === "asc" ? "ascending" : "descending") : undefined}>
                    <button className="inline-flex items-center gap-1 uppercase hover:text-ink" onClick={() => toggleSort(c)}>{c}{sort === c && (order === "asc" ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}</button>
                  </th>))}</tr></thead>
                <tbody>{d.rows.map((r, i) => <tr key={i} className="border-b border-line-soft hover:bg-bg-elev/40">{d.columns.map((c) => <td key={c} className="td">{cell(r[c], c)}</td>)}</tr>)}</tbody>
              </table>
            </div>
            {meta.pagination && <Pagination page={meta.pagination.page} pages={meta.pagination.pages} total={meta.pagination.total} onPage={setPage} />}
            <SourceNote meta={meta} extra={meta.attribution || undefined} />
          </Card>
        )}
      </DataState>
    </>
  );
}

export default function DataExplorerView() {
  return <Suspense fallback={<Loading />}><Inner /></Suspense>;
}
