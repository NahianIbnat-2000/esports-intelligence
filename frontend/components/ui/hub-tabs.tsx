"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cx } from "@/components/ui/primitives";

const TABS = [
  { href: "/teams", label: "Teams" },
  { href: "/players", label: "Players" },
  { href: "/teams/compare", label: "Compare teams" },
  { href: "/players/compare", label: "Compare players" },
];

export function HubTabs() {
  const path = usePathname();
  return (
    <nav aria-label="Teams and players" className="mb-5 flex flex-wrap gap-1 border-b border-line">
      {TABS.map((t) => (
        <Link key={t.href} href={t.href} aria-current={path === t.href ? "page" : undefined}
          className={cx("-mb-px border-b-2 px-3 py-2 text-sm", path === t.href ? "border-cyan text-ink" : "border-transparent text-ink-2 hover:text-ink")}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
