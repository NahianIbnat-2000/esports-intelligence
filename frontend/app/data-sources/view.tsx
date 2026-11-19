"use client";

import Link from "next/link";
import { Card, DataState, PageHeader, StatusBadge } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import { fmtDate, fmtDateTime, fmtInt } from "@/lib/format";

interface Prov {
  sources: { key: string; name: string; url: string; data_type: string; license_note: string; attribution: string | null }[];
  dataset_versions: { filename: string; sha256: string; size_bytes: number | null; original_location: string; collected_at: string; processed_at: string;
    coverage_start: string | null; coverage_end: string | null; rows_raw: number | null; rows_accepted: number | null; rows_excluded: number | null; validation_status: string;
    cleaning_procedure: Record<string, string | string[]> | null }[];
  quality_report: { run_id: string; generated_at: string; counts: Record<string, unknown>; data_completeness: Record<string, number> } | null;
  providers: { provider: string; games: string[]; configured: boolean; verified_endpoints: string[]; documentation: string; env_var: string; state: string }[];
}

export default function DataSourcesView() {
  const q = useApi<Prov>("/data-provenance");
  return (
    <>
      <PageHeader eyebrow="Documentation" title="Data provenance" description="Where every record comes from, when it was collected, how it was transformed, and what is known to be missing. Raw source files are kept unchanged and are not redistributed; the pipeline rebuilds everything from them." />
      <DataState query={{ ...q, data: q.data ? { ...q.data, meta: { ...q.data.meta, data_status: "available" } } : undefined }}>
        {(d) => (
          <div className="space-y-6">
            <Card title="Sources">
              <div className="space-y-4">{d.sources.map((s) => (
                <div key={s.key} className="border-b border-line-soft pb-4 last:border-0">
                  <p className="flex items-center gap-2 font-medium">{s.name} <StatusBadge status={s.data_type === "historical" ? "historical" : "integration_pending"} /></p>
                  <a className="link text-xs" href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
                  <p className="mt-1 text-sm text-ink-2">{s.license_note}</p>
                  {s.attribution && <p className="mt-1 text-xs text-ink-3">Attribution: {s.attribution}</p>}
                </div>))}</div>
            </Card>
            <Card title="Imported files">
              {d.dataset_versions.length === 0 ? <p className="text-sm text-ink-2">No files imported yet.</p> : (
                <div className="-mx-4 overflow-x-auto sm:mx-0"><table className="w-full min-w-[820px]">
                  <thead className="border-b border-line"><tr><th className="th">File</th><th className="th">SHA-256</th><th className="th">Collected</th><th className="th">Coverage</th><th className="th text-right">Rows raw</th><th className="th text-right">Accepted</th><th className="th text-right">Excluded</th><th className="th">Processed</th><th className="th">Validation</th></tr></thead>
                  <tbody>{d.dataset_versions.map((f) => (
                    <tr key={f.sha256} className="border-b border-line-soft"><td className="td font-mono text-xs">{f.filename}</td><td className="td font-mono text-xs text-ink-3">{f.sha256.slice(0, 12)}</td><td className="td text-xs">{fmtDateTime(f.collected_at)}</td>
                      <td className="td text-xs">{fmtDate(f.coverage_start)} to {fmtDate(f.coverage_end)}</td><td className="td num text-right">{fmtInt(f.rows_raw)}</td>
                      <td className="td num text-right">{fmtInt(f.rows_accepted)}</td><td className="td num text-right">{fmtInt(f.rows_excluded)}</td>
                      <td className="td text-xs">{fmtDateTime(f.processed_at)}</td><td className="td"><StatusBadge status={f.validation_status.startsWith("passed") ? "available" : "unavailable"} label={f.validation_status.replace(/_/g, " ")} /></td></tr>))}</tbody></table></div>
              )}
              {d.quality_report && (
                <details className="mt-4"><summary className="cursor-pointer text-sm text-cyan">Data quality report (run {d.quality_report.run_id})</summary>
                  <pre className="mt-2 max-h-96 overflow-auto rounded-md bg-bg-2 p-3 text-2xs text-ink-2">{JSON.stringify(d.quality_report.counts, null, 2)}</pre></details>
              )}
            </Card>
            {d.dataset_versions[0]?.cleaning_procedure && (
              <Card title="Transformations and cleaning rules" info="Stored with every imported file (dataset_versions.cleaning_procedure).">
                <dl className="grid gap-x-6 gap-y-3 md:grid-cols-2">
                  {Object.entries(d.dataset_versions[0].cleaning_procedure).map(([k, v]) => (
                    <div key={k}><dt className="font-mono text-xs text-cyan">{k}</dt>
                      <dd className="mt-0.5 text-xs leading-relaxed text-ink-2">{Array.isArray(v) ? v.join("; ") : String(v)}</dd></div>))}
                </dl>
                <p className="mt-4 text-xs text-ink-3">Excluded observations and missing values: <Link className="link" href="/data-quality">Data quality report</Link>. Raw files: data/raw/oracles_elixir (unchanged, SHA-256 in manifest.json); cleaned rows: data/intermediate; analytical tables: data/processed.</p>
              </Card>
            )}
            <Card title="External provider adapters">
              <div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th">Provider</th><th className="th">Games</th><th className="th">Key set</th><th className="th">Verified endpoints</th><th className="th">State</th></tr></thead>
                <tbody>{d.providers.map((p) => (
                  <tr key={p.provider} className="border-b border-line-soft"><td className="td"><a className="link" href={p.documentation} target="_blank" rel="noreferrer">{p.provider}</a></td>
                    <td className="td text-xs">{p.games.join(", ")}</td><td className="td text-xs">{p.configured ? "yes" : `no (${p.env_var})`}</td>
                    <td className="td text-xs">{p.verified_endpoints.length || "none"}</td><td className="td"><StatusBadge status={p.state} /></td></tr>))}</tbody></table></div>
              <p className="mt-3 text-xs text-ink-3">Keys are read on the server only and never sent to the browser.</p>
            </Card>
          </div>
        )}
      </DataState>
    </>
  );
}
