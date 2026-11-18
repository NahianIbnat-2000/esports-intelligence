"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { GAMES, useGame } from "@/components/providers";
import { GameSwitch } from "@/components/ui/game-gate";
import { DataState, PageHeader, SourceNote, StatusBadge } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";

interface ReportItem { slug: string; title: string; research_question: string; status: string; status_note: string | null; n_findings: number }

export default function ResearchView() {
  const { game } = useGame();
  const q = useApi<ReportItem[]>("/research", { game });
  return (
    <>
      <PageHeader index="07" eyebrow="Research" title="Research publications"
        description="Reports are built from the platform's own analysis outputs. Findings are generated from computed numbers by fixed rules. A report whose analysis has not been run is labelled 'proposed' and shows no results.">
        <GameSwitch />
      </PageHeader>
      <DataState query={q} gameName={GAMES.find((g) => g.slug === game)?.name}>
        {(rows, meta) => (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              {rows.map((r, i) => (
                <Link key={r.slug} href={`/research/${r.slug}`} className="card card-pad group flex flex-col gap-3 transition-colors hover:border-cyan/40">
                  <div className="flex items-center justify-between">
                    <span className="num text-2xs text-ink-3">REPORT {String(i + 1).padStart(2, "0")}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  <h2 className="text-lg font-semibold leading-snug group-hover:text-cyan">{r.title}</h2>
                  <p className="text-sm leading-relaxed text-ink-2">{r.research_question}</p>
                  {r.status_note && <p className="text-xs text-amber">{r.status_note}</p>}
                  <span className="mt-auto inline-flex items-center gap-1 text-xs text-cyan">Read <ArrowUpRight size={13} /></span>
                </Link>
              ))}
            </div>
            <SourceNote meta={meta} />
          </>
        )}
      </DataState>
    </>
  );
}
