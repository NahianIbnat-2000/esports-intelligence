"use client";

import { useEffect, useId, useState } from "react";
import { useApi } from "@/hooks/use-api";
import type { PlayerSummary, TeamSummary } from "@/lib/api";
import { cx } from "@/components/ui/primitives";

type Kind = "teams" | "players";

/** Accessible search-and-select for a team or player (by slug). */
export function EntityPicker({ kind, label, value, onChange, minMatches = 5 }: {
  kind: Kind; label: string; value: string; onChange: (slug: string, name: string) => void; minMatches?: number;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(text), 250);
    return () => clearTimeout(t);
  }, [text]);
  const q = useApi<(TeamSummary | PlayerSummary)[]>(`/${kind}`, { game: "lol", q: debounced, page_size: 12, min_matches: minMatches, sort: "matches" }, open);
  const selected = useApi<TeamSummary | { player: PlayerSummary } | { team: TeamSummary }>(value ? `/${kind}/${value}` : null, { game: "lol" });
  const selName = (() => {
    const d = selected.data?.data as { team?: TeamSummary; player?: PlayerSummary } | undefined;
    return d?.team?.name || d?.player?.name || value;
  })();

  return (
    <div className="relative">
      <label htmlFor={id} className="eyebrow mb-1 block">{label}</label>
      <input id={id} className="input" role="combobox" aria-expanded={open} aria-controls={`${id}-list`} autoComplete="off"
        placeholder={value ? selName : `Search ${kind}`} value={open ? text : value ? selName : ""}
        onFocus={() => { setOpen(true); setText(""); }} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={(e) => setText(e.target.value)} />
      {open && (
        <ul id={`${id}-list`} role="listbox" className="absolute z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-line bg-bg-elev py-1 shadow-card">
          {q.isLoading && <li className="px-3 py-2 text-xs text-ink-3">Searching...</li>}
          {q.error && <li className="px-3 py-2 text-xs text-danger">{q.error.message}</li>}
          {q.data?.meta.data_status === "empty" && <li className="px-3 py-2 text-xs text-ink-3">No data loaded.</li>}
          {(q.data?.data || []).map((e) => (
            <li key={e.slug} role="option" aria-selected={e.slug === value}>
              <button type="button" onMouseDown={(ev) => ev.preventDefault()} onClick={() => { onChange(e.slug, e.name); setOpen(false); }}
                className={cx("flex w-full items-center justify-between px-3 py-1.5 text-left text-sm hover:bg-bg-card", e.slug === value && "text-cyan")}>
                <span>{e.name}</span>
                <span className="text-2xs text-ink-3">
                  {"primary_league" in e ? e.primary_league : (e as PlayerSummary).primary_position} | {e.n_matches} games
                </span>
              </button>
            </li>
          ))}
          {q.data?.data && q.data.data.length === 0 && <li className="px-3 py-2 text-xs text-ink-3">No match.</li>}
        </ul>
      )}
    </div>
  );
}
