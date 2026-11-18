"use client";

import { MapPinOff } from "lucide-react";
import { GameSwitch, LolOnly } from "@/components/ui/game-gate";
import { Card, PageHeader, StatusBadge } from "@/components/ui/primitives";
import { RegionalModule } from "@/app/analytics/view";

const VARIABLES = [
  { name: "Player nationality", status: "unavailable", note: "Not a field in the source. Not inferred from names, languages or teams." },
  { name: "Team headquarters", status: "unavailable", note: "Not a field in the source." },
  { name: "Tournament host country", status: "unavailable", note: "Not a field in the source. Event names are not used to guess locations." },
  { name: "Competitive region (league)", status: "available", note: "The source `league` field (e.g. LCK, LEC). A league is a competitive circuit, not a country." },
  { name: "Prize money", status: "unavailable", note: "Not a field in the source." },
];

export default function GlobalIndexView() {
  return (
    <>
      <PageHeader index="06" eyebrow="Global Index" title="Geography of competition"
        description="Geographic analysis is limited to what the data actually records. This page explains what is and is not available, and uses the space for league-level (regional) analysis instead of a world map.">
        <GameSwitch />
      </PageHeader>
      <LolOnly>
        <Card className="mb-6" eyebrow="Coverage limitation" title={<span className="flex items-center gap-2"><MapPinOff size={16} className="text-amber" /> Why there is no world map</span>}>
          <p className="mb-4 max-w-3xl text-sm leading-relaxed text-ink-2">
            A map needs a country for each record. Oracle&apos;s Elixir match files record leagues, teams and players but not countries.
            Placing leagues on a map would mean guessing a single country for multi-country leagues (for example the LEC or the
            Pacific league), which would be misleading. The map will be added only if a verified country field becomes available.
          </p>
          <div className="-mx-4 overflow-x-auto sm:mx-0"><table className="w-full min-w-[560px]">
            <thead className="border-b border-line"><tr><th className="th">Variable</th><th className="th">Status</th><th className="th">Note</th></tr></thead>
            <tbody>{VARIABLES.map((v) => (
              <tr key={v.name} className="border-b border-line-soft"><td className="td font-medium">{v.name}</td>
                <td className="td"><StatusBadge status={v.status} label={v.status === "available" ? "Available" : "Not available"} /></td>
                <td className="td whitespace-normal text-xs text-ink-2">{v.note}</td></tr>))}</tbody></table></div>
        </Card>
        <RegionalModule />
      </LolOnly>
    </>
  );
}
