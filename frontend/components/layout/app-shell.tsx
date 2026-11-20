"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { CalendarDays, ChevronDown, ChevronsRight, Menu, Search, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { VISIBLE_GAMES, useGame, type GameSlug } from "@/components/providers";
import { cx } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import { API_URL, type GameInfo } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { onSlowRequests } from "@/lib/snapshot";
import { Ticker } from "@/components/layout/ticker";

type NavItem = { href: string; label: string };
type NavGroup = { label: string; href: string; items: NavItem[]; match: string[] };

/** Top navigation: each group has a dropdown and a second-row sub navigation. */
export const NAV_GROUPS: NavGroup[] = [
  { label: "Dashboard", href: "/", match: ["/", "/data-quality", "/data-sources"],
    items: [{ href: "/", label: "Overview" }, { href: "/data-quality", label: "Data quality" }, { href: "/data-sources", label: "Data provenance" }] },
  { label: "Matches", href: "/matches", match: ["/matches", "/tournaments", "/global-index"],
    items: [{ href: "/matches", label: "Match centre" }, { href: "/tournaments", label: "Tournaments" }, { href: "/global-index", label: "Global index" }] },
  { label: "Teams & Players", href: "/teams", match: ["/teams", "/players", "/search"],
    items: [{ href: "/teams", label: "Teams" }, { href: "/players", label: "Players" }, { href: "/teams/compare", label: "Compare teams" }, { href: "/players/compare", label: "Compare players" }] },
  { label: "Statistics", href: "/analytics", match: ["/analytics", "/data-explorer"],
    items: [{ href: "/analytics", label: "Analytics" }, { href: "/data-explorer", label: "Data explorer" }] },
  { label: "Predictions", href: "/predictions", match: ["/predictions"],
    items: [{ href: "/predictions", label: "Model lab" }] },
  { label: "Research", href: "/research", match: ["/research", "/experiments", "/methodology", "/documentation", "/faq"],
    items: [{ href: "/research", label: "Reports" }, { href: "/experiments", label: "Experiments" }, { href: "/methodology", label: "Methodology" }, { href: "/documentation", label: "Documentation" }, { href: "/faq", label: "FAQ & glossary" }] },
];

const isIn = (path: string, h: string) => (h === "/" ? path === "/" : path === h || path.startsWith(h + "/"));
const activeGroup = (path: string) => NAV_GROUPS.find((g) => g.match.some((h) => isIn(path, h)));
const activeItem = (path: string, g?: NavGroup) =>
  g?.items.filter((i) => isIn(path, i.href)).sort((a, b) => b.href.length - a.href.length)[0];

/** Original emblem: shield with a rising data line. */
export function Emblem({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <defs>
        <linearGradient id="em-g" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#F4C55A" />
          <stop offset="1" stopColor="#B9821F" />
        </linearGradient>
      </defs>
      <path d="M20 2 L35 8 V19 C35 28 28.5 34.5 20 38 C11.5 34.5 5 28 5 19 V8 Z" fill="#14161C" stroke="url(#em-g)" strokeWidth="2" />
      <path d="M11 25 L16.5 19 L21 22 L29 12" fill="none" stroke="url(#em-g)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="29" cy="12" r="2.4" fill="#FF9F1C" />
    </svg>
  );
}

function Logo() {
  return (
    <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="Esports Intelligence home">
      <Emblem size={36} />
      <span className="leading-tight xl:hidden 2xl:block">
        <span className="block font-display text-[14px] font-bold uppercase tracking-wide text-ink">Esports Intelligence</span>
        <span className="block text-2xs text-ink-3">Beyond the Game. Inside the Data.</span>
      </span>
    </Link>
  );
}

function GroupMenu({ g, path }: { g: NavGroup; path: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const active = activeGroup(path) === g;
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const key = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", key); };
  }, [open]);
  return (
    <div ref={ref} className="relative" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((o) => !o)}
        className={cx("flex h-10 items-center gap-1 border-b-2 px-3 text-[13px] font-semibold transition-colors",
          active ? "border-cyan text-ink" : "border-transparent text-ink-2 hover:text-ink")}>
        {g.label}
        <ChevronDown size={13} className={cx("transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div role="menu" className="absolute left-0 top-full z-40 min-w-[190px] rounded-card border border-line bg-bg-elev py-1 shadow-card">
          {g.items.map((i) => (
            <Link key={i.href} role="menuitem" href={i.href}
              className={cx("block px-3 py-2 text-sm", activeItem(path, g) === i ? "text-cyan" : "text-ink-2 hover:bg-bg-card hover:text-ink")}>
              {i.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function SearchButton() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (q.trim()) { router.push(`/search?q=${encodeURIComponent(q.trim())}`); setOpen(false); }
  };
  return (
    <div className="relative">
      <button type="button" className="flex h-9 w-9 items-center justify-center text-ink-2 hover:text-ink" aria-label="Search" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Search size={15} />
      </button>
      {open && (
        <form onSubmit={submit} role="search" className="absolute right-0 top-11 z-40 w-72 rounded-card border border-line bg-bg-elev p-2 shadow-card">
          <label htmlFor="global-search" className="sr-only">Search teams, players and tournaments</label>
          <input id="global-search" autoFocus className="input" placeholder="Search teams, players, tournaments" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
      )}
    </div>
  );
}

function GameSwitch() {
  const { game, setGame } = useGame();
  const games = useApi<GameInfo[]>("/games");
  const status = (slug: string) => games.data?.data?.find((g) => g.slug === slug)?.status;
  return (
    <div role="radiogroup" aria-label="Select game" className="flex items-center gap-0.5 px-1">
      {VISIBLE_GAMES.map((g) => {
        const s = status(g.slug);
        return (
          <button key={g.slug} role="radio" aria-checked={game === g.slug} onClick={() => setGame(g.slug as GameSlug)}
            title={`${g.name}${s ? `: ${s.replace(/_/g, " ")}` : ""}`}
            className={cx("relative h-7 rounded-sm px-2 text-2xs font-bold uppercase tracking-wider transition-colors",
              game === g.slug ? "bg-cyan/15 text-cyan" : "text-ink-3 hover:text-ink")}>
            {g.short}
            {s && s !== "historical" && s !== "active" && <span className="absolute right-0.5 top-0.5 h-1 w-1 rounded-full bg-amber" />}
          </button>
        );
      })}
    </div>
  );
}

function DataDate() {
  const { game } = useGame();
  const q = useApi<GameInfo[]>("/games");
  const g = q.data?.data?.find((x) => x.slug === game);
  return (
    <div className="flex items-center gap-2 px-1" title={g?.status === "historical" ? "Historical archive, not live data" : undefined}>
      <CalendarDays size={18} className="text-ink-2" />
      <div className="leading-tight">
        <p className="text-2xs text-ink-3">{q.error ? "API unreachable" : g?.status === "historical" ? "Archive through" : "Data status"}</p>
        <p className="text-xs font-semibold text-ink">{g?.coverage_end ? fmtDate(g.coverage_end) : g ? g.status.replace(/_/g, " ") : "..."}</p>
      </div>
    </div>
  );
}

function Header() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);
  const grp = activeGroup(path);
  const item = activeItem(path, grp);
  return (
    <>
    <header className="sticky top-0 z-30 border-b border-line bg-bg/95 backdrop-blur">
      <Ticker />
      <div className="mx-auto flex max-w-[1600px] items-center gap-4 px-4 pt-2 sm:px-6">
        <Logo />
        <nav aria-label="Main" className="hidden flex-1 items-center lg:flex">
          {NAV_GROUPS.map((g) => <GroupMenu key={g.label} g={g} path={path} />)}
        </nav>
        <div className="ml-auto hidden items-center gap-3 lg:flex">
          <div className="flex items-center rounded-card border border-cyan/40 bg-bg-2">
            <SearchButton />
            {VISIBLE_GAMES.length > 1 && <><span className="h-5 w-px bg-line" /><GameSwitch /></>}
          </div>
          <DataDate />
          <Link href="/predictions" className="flex h-9 items-center gap-6 rounded-card bg-cyan px-4 text-[13px] font-semibold text-black hover:bg-cyan/85">
            Predict a match <ChevronsRight size={16} />
          </Link>
        </div>
        <button className="btn ml-auto h-9 w-9 p-0 lg:hidden" aria-label="Open navigation" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(true)}>
          <Menu size={18} />
        </button>
      </div>
      {/* second row: pages of the active group */}
      <div className="mx-auto hidden max-w-[1600px] items-center gap-5 px-4 pb-2 pl-[68px] sm:px-6 sm:pl-[76px] lg:flex">
        {grp?.items.map((i) => (
          <Link key={i.href} href={i.href}
            className={cx("text-xs font-medium", item === i ? "text-ink" : "text-ink-3 hover:text-ink-2")}>{i.label}</Link>
        ))}
      </div>
    </header>
    {/* outside <header>: its backdrop blur would trap a position:fixed drawer inside the header bar */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation" id="mobile-nav">
          <button className="absolute inset-0 bg-black/70" aria-label="Close navigation" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 right-0 w-80 max-w-[88vw] overflow-y-auto border-l border-line bg-bg-2 p-4">
            <div className="mb-4 flex items-center justify-between">
              <Emblem size={30} />
              <button className="btn h-8 w-8 p-0" aria-label="Close navigation" onClick={() => setOpen(false)}><X size={16} /></button>
            </div>
            <div className="mb-4 flex items-center justify-between rounded-card border border-line bg-bg p-1">
              <SearchButton />{VISIBLE_GAMES.length > 1 && <GameSwitch />}
            </div>
            <nav aria-label="Main mobile" className="space-y-4">
              {NAV_GROUPS.map((g) => (
                <div key={g.label}>
                  <p className="eyebrow mb-1 text-cyan">{g.label}</p>
                  {g.items.map((i) => (
                    <Link key={i.href} href={i.href} className={cx("block rounded-sm px-2 py-1.5 text-sm", isIn(path, i.href) && item === i ? "bg-bg-elev text-ink" : "text-ink-2")}>{i.label}</Link>
                  ))}
                </div>
              ))}
            </nav>
            <div className="mt-6 border-t border-line pt-4"><DataDate /></div>
          </div>
        </div>
      )}
    </>
  );
}

function Footer() {
  return (
    <footer className="mt-16 border-t border-line py-6 text-xs text-ink-3">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p>Esports Intelligence v1.3. League of Legends data: Oracle&apos;s Elixir (Tim Sevenhuysen). Game statistics © Riot Games. Not affiliated with Riot Games.</p>
        <nav aria-label="Footer" className="flex flex-wrap gap-4">
          <Link href="/methodology" className="hover:text-cyan">Methodology</Link>
          <Link href="/data-sources" className="hover:text-cyan">Data provenance</Link>
          <Link href="/data-quality" className="hover:text-cyan">Data quality</Link>
          <Link href="/documentation" className="hover:text-cyan">Documentation</Link>
          <a href={`${API_URL}/docs`} className="hover:text-cyan" target="_blank" rel="noreferrer">API reference</a>
        </nav>
      </div>
    </footer>
  );
}

/** Shown while a live API request takes longer than 3 s (free hosting sleeps when idle). */
function WakeNotice() {
  const [slow, setSlow] = useState(0);
  useEffect(() => onSlowRequests(setSlow), []);
  if (!slow) return null;
  return (
    <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-50 max-w-sm rounded-card border border-amber/40 bg-bg-elev p-3 text-xs text-ink-2 shadow-card">
      <p className="flex items-center gap-2 font-semibold text-amber"><span className="h-2 w-2 animate-pulse rounded-full bg-amber" />Waking up the live server</p>
      <p className="mt-1">This page needs the live API, which sleeps when nobody has used it for a while. The first request can take up to a minute; later ones are fast.</p>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-bg-elev focus:px-3 focus:py-2">Skip to content</a>
      <Header />
      <main id="main" className="mx-auto min-w-0 max-w-[1600px] px-4 py-6 sm:px-6 lg:py-7">
        {children}
        <Footer />
      </main>
      <WakeNotice />
    </div>
  );
}
