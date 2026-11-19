"use client";

import { useApi } from "@/hooks/use-api";
import { cx } from "@/components/ui/primitives";

interface TickerItem {
  key: string; label: string; display: string; delta: number | null; delta_display: string | null;
  direction: "up" | "down" | null; good_when: "up" | "down" | null; definition: string;
}

/** Scrolling strip of headline indicators, all computed from the loaded data (GET /ticker). */
export function Ticker() {
  const q = useApi<{ as_of: string | null; items: TickerItem[]; note: string }>("/ticker", { game: "lol" });
  const items = q.data?.data?.items ?? [];
  if (!items.length) return <div className="h-7 border-b border-line bg-black" aria-hidden />;

  const row = (copy: number) =>
    items.map((it) => {
      const tone = it.direction === null || it.good_when === null ? "text-ink-2"
        : (it.direction === it.good_when) ? "text-emerald" : "text-danger";
      return (
        <span key={`${copy}-${it.key}`} title={it.definition}
          className="flex shrink-0 items-center gap-2 border-r border-line px-4 font-mono text-[11.5px]">
          <span className="text-ink-3">{it.label}</span>
          <span className="text-ink">{it.display}</span>
          {it.delta_display && (
            <span className={cx(it.good_when ? tone : "text-ink-2")}>
              {it.direction === "up" ? "▲" : it.direction === "down" ? "▼" : ""} {it.delta_display}
            </span>
          )}
        </span>
      );
    });

  return (
    <div className="ticker relative h-7 overflow-hidden border-b border-line bg-black" role="region"
      aria-label="Headline indicators from the data" tabIndex={0}>
      <div className="ticker-track flex h-full w-max items-center">
        {row(0)}
        <span aria-hidden className="flex">{row(1)}</span>
      </div>
      <span className="pointer-events-none absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-black to-transparent" />
    </div>
  );
}
