"use client";

import Link from "next/link";
import { AlertTriangle, ChevronRight, Database, Info, Loader2, PlugZap } from "lucide-react";
import type { ReactNode } from "react";
import type { Meta } from "@/lib/api";
import { fmtDateTime, fmtPeriod } from "@/lib/format";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ children, className, title, eyebrow, actions, info }: {
  children: ReactNode; className?: string; title?: ReactNode; eyebrow?: string; actions?: ReactNode; info?: string;
}) {
  return (
    <section className={cx("card card-pad min-w-0", className)}>
      {(title || eyebrow || actions) && (
        <header className="-mx-4 -mt-4 mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-line-soft px-4 pb-3 pt-3 sm:-mx-5 sm:-mt-5 sm:px-5">
          <div className="min-w-0">
            {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
            {title && (
              <h2 className="panel-title flex items-center gap-2">
                {title}
                {info && <InfoTip text={info} />}
              </h2>
            )}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <button type="button" aria-label={text} className="text-ink-3 hover:text-cyan">
        <Info size={14} />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-6 z-30 hidden w-72 -translate-x-1/2 rounded-md border border-line bg-bg-elev p-3 text-xs font-normal leading-relaxed text-ink-2 shadow-card group-focus-within:block group-hover:block"
      >
        {text}
      </span>
    </span>
  );
}

export function PageHeader({ index, eyebrow, title, description, children }: {
  index?: string; eyebrow: string; title: string; description?: ReactNode; children?: ReactNode;
}) {
  return (
    <header className="mb-6 border-b border-line pb-5">
      <p className="eyebrow mb-2 flex items-center gap-2">
        {index && <span className="text-cyan">{index}</span>}
        {index && <span className="h-px w-6 bg-line" />}
        {eyebrow}
      </p>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-semibold text-ink sm:text-3xl">{title}</h1>
          {description && <p className="mt-2 text-sm leading-relaxed text-ink-2">{description}</p>}
        </div>
        {children}
      </div>
    </header>
  );
}

export function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex flex-wrap items-center gap-1 text-xs text-ink-2">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <ChevronRight size={12} className="text-ink-3" />}
          {it.href ? <Link href={it.href} className="hover:text-cyan">{it.label}</Link> : <span className="text-ink">{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export function Stat({ label, value, sub, accent, info }: {
  label: string; value: ReactNode; sub?: ReactNode; accent?: "cyan" | "violet" | "emerald"; info?: string;
}) {
  const bar = { cyan: "bg-cyan", violet: "bg-violet", emerald: "bg-emerald" }[accent || "cyan"];
  return (
    <div className="card relative overflow-hidden p-4">
      <span className={cx("absolute left-0 top-0 h-full w-[2px]", bar)} aria-hidden />
      <p className="eyebrow flex items-center gap-1.5">{label}{info && <InfoTip text={info} />}</p>
      <p className="num mt-2 text-2xl font-semibold text-ink sm:text-[1.7rem]">{value}</p>
      {sub && <p className="mt-1 text-xs text-ink-2">{sub}</p>}
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  active: "border-emerald/40 bg-emerald/10 text-emerald",
  historical: "border-cyan/40 bg-cyan/10 text-cyan",
  available: "border-cyan/40 bg-cyan/10 text-cyan",
  integration_pending: "border-amber/40 bg-amber/10 text-amber",
  unavailable: "border-danger/40 bg-danger/10 text-danger",
  empty: "border-danger/40 bg-danger/10 text-danger",
  insufficient_data: "border-amber/40 bg-amber/10 text-amber",
  demo: "border-violet/40 bg-violet/10 text-violet",
  trained: "border-emerald/40 bg-emerald/10 text-emerald",
  completed: "border-emerald/40 bg-emerald/10 text-emerald",
  proposed: "border-violet/40 bg-violet/10 text-violet",
};
const STATUS_LABEL: Record<string, string> = {
  integration_pending: "Integration pending", insufficient_data: "Insufficient data", historical: "Historical",
  available: "Historical", empty: "No data loaded",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-2xs font-semibold uppercase tracking-wider",
      STATUS_STYLE[status] || "border-line text-ink-2")}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {label || STATUS_LABEL[status] || status.replace(/_/g, " ")}
    </span>
  );
}

export function Loading({ label = "Loading data" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-10 text-sm text-ink-2">
      <Loader2 size={16} className="animate-spin text-cyan" /> {label}...
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-md bg-bg-elev", className)} aria-hidden />;
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-card border border-danger/30 bg-danger/5 p-5">
      <p className="flex items-center gap-2 text-sm font-medium text-danger"><AlertTriangle size={16} /> Could not load this data</p>
      <p className="text-sm text-ink-2">{error.message}</p>
      {onRetry && <button className="btn" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function EmptyState({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-card border border-dashed border-line bg-bg-2/60 p-6">
      <div className="text-ink-3">{icon || <Database size={20} />}</div>
      <p className="text-sm font-semibold text-ink">{title}</p>
      {children && <div className="max-w-2xl text-sm leading-relaxed text-ink-2">{children}</div>}
    </div>
  );
}

export function NoDataLoaded() {
  return (
    <EmptyState title="No historical data has been imported yet">
      <p>
        This section shows only values calculated from imported Oracle&apos;s Elixir files. Download the yearly CSV
        files from <a className="link" href="https://oracleselixir.com/tools/downloads" target="_blank" rel="noreferrer">oracleselixir.com</a> and
        run <code className="rounded bg-bg-elev px-1.5 py-0.5 text-xs">make data FILES=&quot;...&quot;</code> (see docs/runbook.md).
      </p>
    </EmptyState>
  );
}

export function IntegrationPending({ game }: { game: string }) {
  return (
    <EmptyState title={`${game}: verified data integration pending`} icon={<PlugZap size={20} className="text-amber" />}>
      <p>
        Provider adapters for this game are built (GRID, PandaScore), but no verified credentials or endpoints are
        configured. No statistics are shown until a real integration is connected. Switch to League of Legends to
        explore historical data.
      </p>
    </EmptyState>
  );
}

/** Wraps a query result: loading, error, integration pending, empty, then content. */
export function DataState<T>({ query, children, gameName, isEmpty }: {
  query: { data?: { data: T | null; meta: Meta }; error: Error | null; isLoading: boolean; refetch: () => void };
  children: (data: T, meta: Meta) => ReactNode;
  gameName?: string;
  isEmpty?: (data: T) => boolean;
}) {
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} onRetry={query.refetch} />;
  const env = query.data;
  if (!env) return <Loading />;
  if (env.meta.data_status === "integration_pending") return <IntegrationPending game={gameName || "This game"} />;
  if (env.meta.data_status === "empty" || env.data === null) return <NoDataLoaded />;
  if (isEmpty && isEmpty(env.data)) return <EmptyState title="No records match these filters" />;
  return <>{children(env.data, env.meta)}</>;
}

export function SourceNote({ meta, extra }: { meta?: Meta | null; extra?: string }) {
  if (!meta) return null;
  return (
    <p className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line-soft pt-3 text-2xs text-ink-3">
      <span>Source: {meta.source || "n/a"}{meta.data_type === "historical" ? " (historical archive, not live)" : ""}</span>
      {meta.sample_period?.start && <span>Sample: {fmtPeriod(meta.sample_period)}</span>}
      <span>Generated {fmtDateTime(meta.generated_at)}</span>
      {extra && <span>{extra}</span>}
    </p>
  );
}

export function Segmented<T extends string>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border border-line bg-bg-2 p-0.5">
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={cx("rounded px-2.5 py-1 text-xs font-medium transition-colors",
            value === o.value ? "bg-bg-elev text-cyan" : "text-ink-2 hover:text-ink")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Select({ label, value, onChange, options, className }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; className?: string;
}) {
  return (
    <label className={cx("flex flex-col gap-1", className)}>
      <span className="eyebrow">{label}</span>
      <select className="input pr-8" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

export function Pagination({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (p: number) => void }) {
  return (
    <div className="mt-4 flex items-center justify-between gap-3 text-xs text-ink-2">
      <span>{total.toLocaleString("en-US")} records</span>
      <div className="flex items-center gap-2">
        <button className="btn h-8" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
        <span className="num">{page} / {pages}</span>
        <button className="btn h-8" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button>
      </div>
    </div>
  );
}

export function WinLoss({ r }: { r: number }) {
  return (
    <span className={cx("inline-flex h-5 w-5 items-center justify-center rounded text-2xs font-bold",
      r === 1 ? "bg-emerald/15 text-emerald" : "bg-danger/15 text-danger")} aria-label={r === 1 ? "win" : "loss"}>
      {r === 1 ? "W" : "L"}
    </span>
  );
}
