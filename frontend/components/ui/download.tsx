"use client";

import { Download } from "lucide-react";

/** Downloads the aggregated rows behind a chart as CSV. Only derived
 * aggregates computed by this platform are offered here. Missing values are
 * written as empty cells, never as zero. */
export function DownloadCsv({ rows, filename, label = "CSV" }: { rows: Record<string, unknown>[]; filename: string; label?: string }) {
  const disabled = !rows || rows.length === 0;
  const onClick = () => {
    const cols = Array.from(rows.reduce((s, r) => { Object.keys(r).forEach((k) => s.add(k)); return s; }, new Set<string>()));
    const esc = (v: unknown) => {
      if (v === null || v === undefined) return "";
      const s = typeof v === "object" ? JSON.stringify(v) : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <button type="button" className="btn h-8 px-2.5 text-xs" onClick={onClick} disabled={disabled} aria-label={`Download ${filename} as CSV`}>
      <Download size={13} /> {label}
    </button>
  );
}
