"use client";

import Link from "next/link";
import { Bars } from "@/components/charts/charts";
import { DownloadCsv } from "@/components/ui/download";
import { Breadcrumbs, Card, DataState, PageHeader, SourceNote, StatusBadge } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import { fmtDateTime, fmtInt, fmtPct } from "@/lib/format";
import type { DQ } from "@/app/overview-view";

interface Report extends DQ {
  pipeline_counts: Record<string, unknown> | null;
  inspections: { filename: string; n_rows: number; n_unique_gameid: number; expected_columns_absent: string[] }[] | null;
  cleaning_procedure: Record<string, unknown> | null;
  exclusions_by_reason?: { reason: string; rows: number }[];
  exclusions_by_file?: { source_file: string; rows: number }[];
  missing_values: { table: string; column: string; share_missing: number | null }[];
  games_without_split: number;
  unmatched_by_league: { league: string | null; teams_without_source_id: number }[];
  known_limitations: string[];
}

export default function DataQualityView() {
  const q = useApi<Report>("/data-quality", { game: "lol" });
  return (
    <>
      <Breadcrumbs items={[{ label: "Overview", href: "/" }, { label: "Data quality report" }]} />
      <PageHeader eyebrow="Data quality" title="Data quality report"
        description="Every figure comes from the last pipeline run (data/reports/data_quality_report.json and exclusions.csv) or from the database. Rows are only removed for a recorded reason." />
      <DataState query={q}>
        {(d, meta) => (
          <div className="space-y-3">
            <div className="grid gap-3 xl:grid-cols-3">
              <Card title="Pipeline counts">
                <div className="overflow-x-auto"><table className="w-full"><tbody>
                  {([["Rows read", fmtInt(d.rows_retrieved)], ["Exact duplicate rows", fmtInt(d.duplicate_rows_exact)],
                    ["Conflicting duplicate rows", fmtInt(d.duplicate_rows_conflicting)], ["Games excluded (invalid structure)", fmtInt(d.games_excluded)],
                    ["Rows excluded in total", fmtInt(d.rows_excluded_total)], ["Games loaded", fmtInt(d.games_loaded)],
                    ["Games without a split name", fmtInt(d.games_without_split)]] as const).map(([l, v]) => (
                    <tr key={l} className="border-b border-line-soft"><td className="py-1.5 text-xs text-ink-2">{l}</td><td className="num py-1.5 text-right">{v}</td></tr>))}
                </tbody></table></div>
              </Card>
              <Card title="Exclusions by reason" actions={<DownloadCsv rows={d.exclusions_by_reason || []} filename="exclusions_by_reason" />}>
                <div className="overflow-x-auto"><table className="w-full"><tbody>
                  {(d.exclusions_by_reason || []).map((r) => <tr key={r.reason} className="border-b border-line-soft"><td className="py-1.5 pr-2 text-xs text-ink-2">{r.reason}</td><td className="num py-1.5 text-right">{fmtInt(r.rows)}</td></tr>)}
                </tbody></table></div>
                <p className="mt-2 text-2xs text-ink-3">Rows, not games: one excluded game removes all its rows. Row-level list: data/reports/exclusions.csv.</p>
              </Card>
              <Card title="Last ingestion run">
                {d.last_run ? (
                  <>
                    <p className="mb-2 text-xs text-ink-2">Run <span className="font-mono">{d.last_run.run_id}</span></p>
                    <ul className="space-y-1 text-xs">{d.last_run.stages.map((s, i) => (
                      <li key={i} className="flex items-center justify-between"><span>{s.stage}</span><span className="flex items-center gap-2 text-ink-3">{fmtDateTime(s.at)} <StatusBadge status={s.status === "error" ? "unavailable" : s.status === "warning" ? "insufficient_data" : "completed"} label={s.status} /></span></li>))}</ul>
                  </>
                ) : <p className="text-sm text-ink-2">No run logged.</p>}
              </Card>
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              <Card title="Missing values in important columns" info="Share of rows where the value is null. Nulls are never replaced by zero.">
                <Bars data={d.missing_values.map((m) => ({ col: `${m.table}: ${m.column}`, share: m.share_missing ?? 0 }))} x="col" series={[{ key: "share", label: "Share missing" }]} layout="vertical" height={320} yFormat={(v) => fmtPct(v)} />
              </Card>
              <Card title="Unmatched identifiers" info={d.definitions.teams_without_source_id}>
                <p className="mb-2 text-sm">{fmtInt(d.teams_without_source_id)} teams and {fmtInt(d.players_without_source_id)} players have no source id and are matched by name.</p>
                <div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th">Main league</th><th className="th text-right">Teams without id</th></tr></thead><tbody>
                  {d.unmatched_by_league.map((r) => <tr key={String(r.league)} className="border-b border-line-soft"><td className="td">{r.league ?? "n/a"}</td><td className="td num text-right">{r.teams_without_source_id}</td></tr>)}
                </tbody></table></div>
              </Card>
            </div>
            <Card title="Files inspected" info="Columns the pipeline expects but did not find are created as null for that file.">
              <div className="-mx-4 overflow-x-auto sm:mx-0"><table className="w-full min-w-[620px]"><thead className="border-b border-line"><tr><th className="th">File</th><th className="th text-right">Rows</th><th className="th text-right">Game ids</th><th className="th">Expected columns absent</th></tr></thead><tbody>
                {(d.inspections || []).map((f) => <tr key={f.filename} className="border-b border-line-soft"><td className="td font-mono text-xs">{f.filename}</td><td className="td num text-right">{fmtInt(f.n_rows)}</td><td className="td num text-right">{fmtInt(f.n_unique_gameid)}</td><td className="td text-xs text-ink-2">{f.expected_columns_absent.length ? f.expected_columns_absent.join(", ") : "none"}</td></tr>)}
              </tbody></table></div>
            </Card>
            <Card title="Known limitations">
              <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink-2">{d.known_limitations.map((k) => <li key={k}>{k}</li>)}</ul>
              <p className="mt-3 text-xs text-ink-3">Cleaning rules and file provenance: <Link className="link" href="/data-sources">Data provenance</Link>.</p>
            </Card>
            <SourceNote meta={meta} />
          </div>
        )}
      </DataState>
    </>
  );
}
