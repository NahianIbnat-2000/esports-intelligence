"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { EntityPicker } from "@/components/ui/entity-picker";
import { LolOnly } from "@/components/ui/game-gate";
import { HubTabs } from "@/components/ui/hub-tabs";
import { Card, DataState, EmptyState, InfoTip, Loading, PageHeader, SourceNote } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import { POSITIONS, fmtInt, fmtNum, fmtPct } from "@/lib/format";
import { cx } from "@/components/ui/primitives";

type Side = Record<string, number | string | null>;
interface Cmp { player_a: Side; player_b: Side; metric_definitions: Record<string, string>; notes: string[] }

const ROWS: { key: string; label: string; fmt: (v: number | null) => string; higherBetter?: boolean }[] = [
  { key: "games", label: "Games", fmt: (v) => fmtInt(v) },
  { key: "kills", label: "Kills / game", fmt: (v) => fmtNum(v), higherBetter: true },
  { key: "deaths", label: "Deaths / game", fmt: (v) => fmtNum(v), higherBetter: false },
  { key: "assists", label: "Assists / game", fmt: (v) => fmtNum(v), higherBetter: true },
  { key: "kda", label: "KDA", fmt: (v) => fmtNum(v), higherBetter: true },
  { key: "dpm", label: "Damage / min", fmt: (v) => fmtNum(v, 0), higherBetter: true },
  { key: "damage_share", label: "Damage share", fmt: (v) => fmtPct(v), higherBetter: true },
  { key: "cspm", label: "CS / min", fmt: (v) => fmtNum(v), higherBetter: true },
  { key: "earned_gpm", label: "Earned gold / min", fmt: (v) => fmtNum(v, 0), higherBetter: true },
  { key: "vspm", label: "Vision / min", fmt: (v) => fmtNum(v), higherBetter: true },
  { key: "golddiff_at_15", label: "Gold diff @15", fmt: (v) => fmtNum(v, 0), higherBetter: true },
];

function Inner() {
  const router = useRouter();
  const sp = useSearchParams();
  const a = sp.get("a") || "";
  const b = sp.get("b") || "";
  const set = (k: "a" | "b", v: string) => {
    const p = new URLSearchParams(sp.toString());
    p.set(k, v);
    router.replace(`/players/compare?${p.toString()}`);
  };
  const q = useApi<Cmp>(a && b ? "/players/compare" : null, { game: "lol", a, b });
  return (
    <>
      <PageHeader index="03" eyebrow="Teams & Players" title="Compare players"
        description="Per-game career averages from the source. Metrics are only comparable within a position; the tool warns when positions differ." />
      <HubTabs />
      <LolOnly>
        <div className="mb-6 grid gap-3 sm:grid-cols-2">
          <EntityPicker kind="players" label="Player A" value={a} onChange={(s) => set("a", s)} />
          <EntityPicker kind="players" label="Player B" value={b} onChange={(s) => set("b", s)} />
        </div>
        {!(a && b) ? <EmptyState title="Select two players to compare" /> : (
          <DataState query={q}>
            {(d, meta) => (
              <Card>
                {d.notes.slice(1).map((n) => <p key={n} className="mb-4 rounded-md border border-amber/30 bg-amber/5 p-3 text-sm text-amber">{n}</p>)}
                <table className="w-full">
                  <thead className="border-b border-line"><tr><th className="th">Metric</th>
                    <th className="th text-right">{String(d.player_a.name)} <span className="text-ink-3">({POSITIONS[String(d.player_a.position)] ?? "n/a"})</span></th>
                    <th className="th text-right">{String(d.player_b.name)} <span className="text-ink-3">({POSITIONS[String(d.player_b.position)] ?? "n/a"})</span></th></tr></thead>
                  <tbody>{ROWS.map((r) => {
                    const va = d.player_a[r.key] as number | null;
                    const vb = d.player_b[r.key] as number | null;
                    const better = va === null || vb === null || r.higherBetter === undefined || va === vb ? 0 : (va > vb) === r.higherBetter ? 1 : 2;
                    return (
                      <tr key={r.key} className="border-b border-line-soft">
                        <td className="td text-ink-2"><span className="inline-flex items-center gap-1.5">{r.label}{d.metric_definitions[r.key] && <InfoTip text={d.metric_definitions[r.key]} />}</span></td>
                        <td className={cx("td num text-right", better === 1 && "text-emerald")}>{r.fmt(va)}</td>
                        <td className={cx("td num text-right", better === 2 && "text-violet")}>{r.fmt(vb)}</td>
                      </tr>);
                  })}</tbody>
                </table>
                <p className="mt-3 text-2xs text-ink-3">{d.notes[0]} Highlighted values are the higher (or, for deaths, lower) of the two; this is not a statistical test.</p>
                <SourceNote meta={meta} />
              </Card>
            )}
          </DataState>
        )}
      </LolOnly>
    </>
  );
}

export default function ComparePlayers() {
  return <Suspense fallback={<Loading />}><Inner /></Suspense>;
}
