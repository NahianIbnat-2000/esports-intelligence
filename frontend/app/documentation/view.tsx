"use client";

import Link from "next/link";
import { Card, PageHeader } from "@/components/ui/primitives";
import { API_URL } from "@/lib/api";

const DOCS = [
  ["README.md", "Overview, quick start and project structure"],
  ["docs/runbook.md", "Importing Oracle's Elixir files and rebuilding data, models and analysis"],
  ["docs/architecture.md", "System design and component responsibilities"],
  ["docs/database.md", "Tables, keys and relationships"],
  ["docs/api.md", "Endpoint reference and response envelope"],
  ["docs/data_sources.md", "Sources, licensing and provider integration status"],
  ["docs/data_dictionary.md", "Column definitions"],
  ["docs/methodology.md", "Cleaning, Elo, models, evaluation and indicators"],
  ["docs/deployment.md", "Vercel, Render and PostgreSQL deployment"],
  ["docs/DEVELOPMENT_REPORT.md", "What is implemented, tested and still open"],
  ["docs/RESULTS_2020_2026.md", "Results of the run on Oracle's Elixir 2020-2026"],
];

export default function DocumentationView() {
  return (
    <>
      <PageHeader eyebrow="Documentation" title="Documentation" description="Technical documentation ships with the source code in the docs/ folder." />
      <div className="grid gap-3 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Project documents">
          <ul className="divide-y divide-line-soft">{DOCS.map(([f, d]) => <li key={f} className="flex flex-wrap justify-between gap-2 py-2.5 text-sm"><span className="font-mono text-xs text-cyan">{f}</span><span className="text-ink-2">{d}</span></li>)}</ul>
        </Card>
        <Card title="API">
          <p className="text-sm text-ink-2">Interactive OpenAPI documentation is served by the backend.</p>
          <a className="btn btn-primary mt-3" href={`${API_URL}/docs`} target="_blank" rel="noreferrer">Open API reference</a>
          <p className="mt-4 text-sm text-ink-2">See also <Link className="link" href="/methodology">Methodology</Link> and <Link className="link" href="/data-sources">Data sources</Link>.</p>
        </Card>
      </div>
    </>
  );
}
