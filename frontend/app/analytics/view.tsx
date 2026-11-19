"use client";

import Link from "next/link";
import { useState } from "react";
import { Bars, Curves, IntervalBars, ScatterPlot, TimeLine } from "@/components/charts/charts";
import { GAMES, useGame } from "@/components/providers";
import { DownloadCsv } from "@/components/ui/download";
import { GameSwitch } from "@/components/ui/game-gate";
import { Card, DataState, EmptyState, PageHeader, Select, SourceNote, cx } from "@/components/ui/primitives";
import { TeamTable } from "@/components/ui/tables";
import { useApi } from "@/hooks/use-api";
import type { TeamSummary } from "@/lib/api";
import { CHART } from "@/lib/chart-theme";
import { POSITIONS, fmtNum, fmtPct } from "@/lib/format";

const MODULES = [
  { key: "team", label: "A. Team performance" },
  { key: "player", label: "B. Player performance" },
  { key: "balance", label: "C. Competitive balance" },
  { key: "tournament", label: "D. Tournament performance" },
  { key: "historical", label: "E. Historical trends" },
  { key: "regional", label: "F. Regional analysis" },
] as const;
type ModuleKey = (typeof MODULES)[number]["key"];

export default function AnalyticsView() {
  const { game } = useGame();
  const [mod, setMod] = useState<ModuleKey>("team");
  return (
    <>
      <PageHeader index="04" eyebrow="Analytics" title="Statistical laboratory"
        description="Six modules, each answering one question. Every chart states its metric definition, sample and source. Use the CSV buttons to download the aggregated values behind a chart.">
        <GameSwitch />
      </PageHeader>
      <div role="tablist" aria-label="Analytics modules" className="mb-6 flex gap-1 overflow-x-auto border-b border-line">
        {MODULES.map((m) => (
          <button key={m.key} role="tab" aria-selected={mod === m.key} onClick={() => setMod(m.key)}
            className={cx("-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm", mod === m.key ? "border-cyan text-ink" : "border-transparent text-ink-2 hover:text-ink")}>
            {m.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {game !== "lol" ? <Gate game={game} /> : (
          <>
            {mod === "team" && <TeamModule />}
            {mod === "player" && <PlayerModule />}
            {mod === "balance" && <BalanceModule />}
            {mod === "tournament" && <TournamentModule />}
            {mod === "historical" && <HistoricalModule />}
            {mod === "regional" && <RegionalModule />}
          </>
        )}
      </div>
    </>
  );
}

function Gate({ game }: { game: string }) {
  const q = useApi<unknown>("/analytics/team-performance", { game });
  return <DataState query={q} gameName={GAMES.find((g) => g.slug === game)?.name}>{() => null}</DataState>;
}

/* ------------------------------------------------------------------ A */
function TeamModule() {
  const [league, setLeague] = useState("");
  const [minM, setMinM] = useState("30");
  const [scope, setScope] = useState("");
  const filters = useApi<{ leagues: { league: string }[] }>("/tournaments/filters", { game: "lol" });
  const q = useApi<{ teams: TeamSummary[]; n_teams: number; elo_histogram: { bin: string; teams: number }[]; definition: string;
    default_trajectory_teams?: string[]; default_trajectory_note?: string; ranking_scope_note?: string | null }>(
    "/analytics/team-performance", { game: "lol", league, min_matches: minM, scope: league ? "" : scope });
  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Select label="Primary league" value={league} onChange={setLeague} options={[{ value: "", label: "All leagues" }, ...(filters.data?.data?.leagues || []).map((l) => ({ value: l.league, label: l.league }))]} />
        <Select label="Minimum games" value={minM} onChange={setMinM} options={["10", "30", "60", "100"].map((v) => ({ value: v, label: `${v}+` }))} />
        {!league && <Select label="Ranking scope" value={scope} onChange={setScope}
          options={[{ value: "", label: "Active teams, linked leagues" }, { value: "all", label: "All teams" }]} />}
      </div>
      <DataState query={q}>
        {(d, meta) => (
          <div className="grid gap-3 xl:grid-cols-5">
            <Card className="xl:col-span-2" eyebrow="Distribution" title="Current Elo of teams" info={d.definition}
              actions={<DownloadCsv rows={d.elo_histogram} filename="elo_distribution" />}>
              <Bars data={d.elo_histogram} x="bin" series={[{ key: "teams", label: "Teams" }]} height={300} />
              <p className="mt-2 text-2xs text-ink-3">{d.n_teams} teams. Ratings of teams that stopped playing are frozen at their last value.</p>
            </Card>
            <Card className="xl:col-span-3" eyebrow="Ranking" title="Teams by current Elo" info={d.definition}
              actions={<DownloadCsv rows={d.teams as unknown as Record<string, unknown>[]} filename="team_performance" />}>
              {d.ranking_scope_note && <p className="-mt-1 mb-3 text-2xs text-ink-3">{d.ranking_scope_note}</p>}
              <div className="max-h-[420px] overflow-y-auto"><TeamTable rows={d.teams.slice(0, 50)} /></div>
            </Card>
            <div className="xl:col-span-5"><Trajectories slugs={d.default_trajectory_teams ?? d.teams.slice(0, 5).map((t) => t.slug)} note={d.default_trajectory_note} /></div>
            <div className="xl:col-span-5"><Consistency /></div>
            <div className="xl:col-span-5"><SourceNote meta={meta} /></div>
          </div>
        )}
      </DataState>
    </>
  );
}

function Trajectories({ slugs, note }: { slugs: string[]; note?: string }) {
  const q = useApi<{ slug: string; name: string; history: { date: string; elo: number }[] }[]>(slugs.length ? "/analytics/team-trajectories" : null, { game: "lol", teams: slugs.join(",") });
  const series = q.data?.data || [];
  const merged = new Map<string, Record<string, number | string>>();
  series.forEach((t) => t.history.forEach((p) => {
    const k = p.date.slice(0, 10);
    merged.set(k, { ...(merged.get(k) || { date: k }), [t.slug]: Math.round(p.elo) });
  }));
  const rows = Array.from(merged.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  return (
    <Card eyebrow="Elo trajectories" title="Rating paths of leading teams"
      info={`Elo (with league offsets) after each game. Gaps = no games in that period. ${note ?? ""}`}>
      {note && <p className="-mt-1 mb-3 text-2xs text-ink-3">{note} Use the league filter above to see another league.</p>}
      {series.length ? <TimeLine data={rows} x="date" connectNulls series={series.map((t, i) => ({ key: t.slug, label: t.name, color: CHART.series[i] }))} height={300} />
        : <p className="text-sm text-ink-2">No teams to show.</p>}
    </Card>
  );
}

interface Cons { definition: string; n_teams: number; teams: { name: string; slug: string; league: string; splits: number; mean_wp: number; sd_wp: number }[] }
function Consistency() {
  const q = useApi<{ team_consistency: Cons | null }>("/analytics/competitive-balance", { game: "lol" });
  const c = q.data?.data?.team_consistency;
  if (!c) return null;
  const top = [...c.teams].filter((t) => t.splits >= 8).sort((a, b) => b.mean_wp - a.mean_wp).slice(0, 12);
  return (
    <Card eyebrow="Consistency" title="Average level vs variability of split win %" info={c.definition}
      actions={<DownloadCsv rows={c.teams as unknown as Record<string, unknown>[]} filename="team_consistency" />}>
      <div className="grid gap-3 lg:grid-cols-2">
        <ScatterPlot data={c.teams} x="mean_wp" y="sd_wp" xLabel="Mean split win %" yLabel="SD of split win %" format={(v) => v.toFixed(2)} height={280} yDomain={[0, "auto"]} />
        <div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th">Team (8+ splits)</th><th className="th">League</th><th className="th text-right">Splits</th><th className="th text-right">Mean win %</th><th className="th text-right">SD</th></tr></thead>
          <tbody>{top.map((t) => <tr key={t.slug} className="border-b border-line-soft"><td className="td"><Link className="hover:text-cyan" href={`/teams/${t.slug}`}>{t.name}</Link></td><td className="td text-xs text-ink-2">{t.league}</td>
            <td className="td num text-right">{t.splits}</td><td className="td num text-right">{fmtPct(t.mean_wp)}</td><td className="td num text-right">{fmtNum(t.sd_wp, 3)}</td></tr>)}</tbody></table></div>
      </div>
      <p className="mt-2 text-2xs text-ink-3">{c.n_teams} teams (scatter shows up to 400 with the most splits). Win % in weak leagues is not comparable with win % in strong ones.</p>
    </Card>
  );
}

/* ------------------------------------------------------------------ B */
const PMETRICS = ["kda", "kill_participation", "dpm", "damage_share", "cspm", "earned_gpm", "gold_share", "vspm", "golddiff_at_15", "csdiff_at_15", "kills", "deaths", "assists"];
interface PP { metric: string; definition: string; n_players: number; min_games: number; summary: Record<string, number | null>;
  season_role_medians: Record<string, number>[]; season_role_definition: string;
  histogram: { lower: number; upper: number; players: number }[]; top: { slug: string; name: string; position: string; games: number; value: number }[]; notes: string[] }
function PlayerModule() {
  const [metric, setMetric] = useState("dpm");
  const [position, setPosition] = useState("mid");
  const [minM, setMinM] = useState("20");
  const q = useApi<PP>("/analytics/player-performance", { game: "lol", metric, position, min_matches: minM });
  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Select label="Metric" value={metric} onChange={setMetric} options={PMETRICS.map((m) => ({ value: m, label: m.replace(/_/g, " ") }))} />
        <Select label="Position" value={position} onChange={setPosition} options={[{ value: "", label: "All (not recommended)" }, ...Object.entries(POSITIONS).map(([v, l]) => ({ value: v, label: l }))]} />
        <Select label="Minimum games with metric" value={minM} onChange={setMinM} options={["10", "20", "50", "100"].map((v) => ({ value: v, label: `${v}+` }))} />
      </div>
      <DataState query={q} isEmpty={(d) => d.n_players === 0}>
        {(d, meta) => (
          <div className="grid gap-3 xl:grid-cols-5">
            <Card className="xl:col-span-3" eyebrow="Distribution" title={`Career average ${d.metric.replace(/_/g, " ")} per player`} info={d.definition}
              actions={<DownloadCsv rows={d.histogram} filename={`player_${d.metric}_distribution`} />}>
              <Bars data={d.histogram.map((h) => ({ ...h, bin: fmtNum(h.lower, d.metric.includes("share") ? 3 : 1) }))} x="bin" series={[{ key: "players", label: "Players" }]} height={280} />
              <div className="mt-3 grid grid-cols-5 gap-2 text-center">
                {(["p10", "p25", "median", "p75", "p90"] as const).map((k) => (
                  <div key={k} className="rounded-md border border-line bg-bg-2 p-2"><p className="eyebrow">{k}</p><p className="num text-sm">{fmtNum(d.summary[k], 2)}</p></div>
                ))}
              </div>
              {d.notes.map((n) => <p key={n} className="mt-3 text-xs text-amber">{n}</p>)}
            </Card>
            <Card className="xl:col-span-2" eyebrow="Leaders" title="Highest values" info={`${d.n_players} players with at least ${d.min_games} games where the metric is recorded. Highest is not always better (e.g. deaths).`}
              actions={<DownloadCsv rows={d.top} filename={`player_${d.metric}_top`} />}>
              <ol className="max-h-[380px] divide-y divide-line-soft overflow-y-auto">
                {d.top.map((p, i) => (
                  <li key={p.slug} className="flex items-center justify-between py-1.5 text-sm">
                    <span><span className="num mr-2 text-ink-3">{i + 1}</span><Link className="hover:text-cyan" href={`/players/${p.slug}`}>{p.name}</Link></span>
                    <span className="num text-violet">{fmtNum(p.value, 2)} <span className="text-2xs text-ink-3">({p.games})</span></span>
                  </li>))}
              </ol>
            </Card>
            <Card className="xl:col-span-5" eyebrow="Across seasons" title={`${d.metric.replace(/_/g, " ")} by role and calendar year`} info={d.season_role_definition}
              actions={<DownloadCsv rows={d.season_role_medians} filename={`player_${d.metric}_season_role`} />}>
              <TimeLine data={d.season_role_medians} x="year" height={260}
                series={Object.keys(POSITIONS).map((pos, i) => ({ key: pos, label: POSITIONS[pos], color: CHART.series[i] }))} />
              <p className="mt-2 text-2xs text-ink-3">Roles have different jobs (a support&apos;s low damage is not low performance), so read each line on its own.</p>
            </Card>
            <div className="xl:col-span-5"><SourceNote meta={meta} extra="Compare players in detail with the player comparison tool." /></div>
          </div>
        )}
      </DataState>
    </>
  );
}

/* ------------------------------------------------------------------ C */
interface CB {
  competitive_balance: { definition: string; n_tournaments: number; tournaments: Record<string, unknown>[]; by_year: { year: number; n_tournaments: number; median_noll_scully: number; median_gini_wins: number }[];
    by_league_year: { league: string; year: number; n_splits: number; noll_scully: number; gini_wins: number; hhi_win_share_normalised: number; n_teams: number }[] } | null;
  placements: { available: boolean; reason?: string; definition: string; n_splits: number; share_rs_first_wins_title: number; distribution: { rank: string; splits: number; share: number }[]; by_league: { league: string; splits: number; share_rs_first_wins_title: number }[] } | null;
  title_concentration: { definition: string; leagues: { league: string; n_tournaments_with_champion: number; distinct_champions: number; hhi_titles: number; top_team: string; top_team_titles: number; top_team_share: number }[] } | null;
  persistence: { available: boolean; reason?: string; definition: string; n_pairs?: number; pearson?: number; spearman?: number; ols_slope?: number; scatter_sample?: { wp_t: number; wp_t1: number }[] } | null;
  upset_rate: { available: boolean; definition: string; by_quarter: { quarter: string; n_games: number; upset_rate: number }[]; overall: number | null } | null;
}
function BalanceModule() {
  const q = useApi<CB>("/analytics/competitive-balance", { game: "lol" });
  const [league, setLeague] = useState("");
  return (
    <DataState query={q}>
      {(d, meta) => {
        const cb = d.competitive_balance;
        const leagues = Array.from(new Set((cb?.tournaments || []).map((t) => String(t.league)))).sort();
        const series = (cb?.tournaments || []).filter((t) => !league || t.league === league).map((t) => ({ name: `${t.league} ${t.year} ${t.split}`, noll_scully: t.noll_scully, gini: t.gini_wins }));
        return (
          <div className="grid gap-3 xl:grid-cols-2">
            {cb && <BalanceCompare cb={cb} />}
            {cb && <LorenzPanel cb={cb} />}
            {d.placements?.available && <Placements p={d.placements} />}
            <Card eyebrow="Within-season balance" title="Noll-Scully ratio by year (median across leagues)" info={cb?.definition}
              actions={<DownloadCsv rows={cb?.by_year || []} filename="noll_scully_by_year" />}>
              {cb && cb.by_year.length ? <TimeLine data={cb.by_year.filter((y) => y.n_tournaments >= 20)} x="year" series={[{ key: "median_noll_scully", label: "Median Noll-Scully" }]} reference={{ y: 1, label: "chance level = 1" }} height={260} />
                : <EmptyState title="Not enough tournaments" />}
              <p className="mt-2 text-2xs text-ink-3">Season years with at least 20 splits (a season that has only just started is left out).</p>
            </Card>
            <Card eyebrow="By tournament" title="Noll-Scully per league split" info="Higher = results more spread out than chance, i.e. less balanced."
              actions={<><Select label="League" value={league} onChange={setLeague} className="w-36" options={[{ value: "", label: "All" }, ...leagues.map((l) => ({ value: l, label: l }))]} />
                <DownloadCsv rows={cb?.tournaments || []} filename="competitive_balance_tournaments" /></>}>
              <Bars data={series.slice(-40)} x="name" series={[{ key: "noll_scully", label: "Noll-Scully" }]} height={260} />
              <p className="mt-1 text-2xs text-ink-3">Latest 40 splits for the selection.</p>
            </Card>
            <Card eyebrow="Predictability" title="Upset rate by quarter" info={d.upset_rate?.definition}
              actions={<DownloadCsv rows={d.upset_rate?.by_quarter || []} filename="upset_rate" />}>
              {d.upset_rate?.available ? <>
                <TimeLine data={d.upset_rate.by_quarter} x="quarter" series={[{ key: "upset_rate", label: "Upset rate" }]} yFormat={(v) => fmtPct(v)} height={240} />
                <p className="mt-2 text-xs text-ink-2">Overall: {fmtPct(d.upset_rate.overall)} of games won by the lower-rated team.</p>
              </> : <EmptyState title="Upset rate unavailable">Elo has not been computed yet.</EmptyState>}
            </Card>
            <Card eyebrow="Persistence" title="Win % in consecutive splits" info={d.persistence?.definition}>
              {d.persistence?.available ? <>
                <ScatterPlot data={d.persistence.scatter_sample || []} x="wp_t" y="wp_t1" xLabel="Win % split t" yLabel="Win % split t+1" diagonal format={(v) => fmtPct(v, 0)} height={260} />
                <p className="mt-2 text-xs text-ink-2">{d.persistence.n_pairs} pairs. Pearson {fmtNum(d.persistence.pearson)}, Spearman {fmtNum(d.persistence.spearman)}, OLS slope {fmtNum(d.persistence.ols_slope)}. Plot shows a random sample of up to 600 pairs.</p>
              </> : <EmptyState title="Persistence unavailable">{d.persistence?.reason}</EmptyState>}
            </Card>
            <div className="xl:col-span-2"><SourceNote meta={meta} /></div>
          </div>
        );
      }}
    </DataState>
  );
}

const BAL_METRICS = [
  { key: "noll_scully", label: "Noll-Scully ratio", note: "sd of win % / sd under coin flips; 1 = chance level" },
  { key: "gini_wins", label: "Gini of wins", note: "0 = every team the same number of wins" },
  { key: "hhi_win_share_normalised", label: "Normalised HHI of win shares", note: "0 = equal shares, 1 = one team has every win" },
];
function BalanceCompare({ cb }: { cb: NonNullable<CB["competitive_balance"]> }) {
  const leagueCounts = new Map<string, number>();
  cb.by_league_year.forEach((r) => leagueCounts.set(r.league, (leagueCounts.get(r.league) || 0) + r.n_splits));
  const leagues = Array.from(leagueCounts.entries()).filter(([, n]) => n >= 8).sort((a, b) => b[1] - a[1]).map(([l]) => l);
  const [sel, setSel] = useState<string[]>(["LCK", "LPL", "LEC", "LCS"].filter((l) => leagues.includes(l)));
  const [metric, setMetric] = useState("noll_scully");
  const years = Array.from(new Set(cb.by_league_year.map((r) => r.year))).sort();
  const rows = years.map((y) => Object.fromEntries([["year", String(y)], ...sel.map((l) => [l, cb.by_league_year.find((r) => r.league === l && r.year === y)?.[metric as "noll_scully"] ?? null])]));
  const m = BAL_METRICS.find((x) => x.key === metric)!;
  return (
    <Card className="xl:col-span-2" eyebrow="Compare leagues across seasons" title={`${m.label} by season`}
      info={`${cb.definition} Values are averages over the league's splits in each season year.`}
      actions={<><Select label="Measure" value={metric} onChange={setMetric} className="w-52" options={BAL_METRICS.map((x) => ({ value: x.key, label: x.label }))} />
        <DownloadCsv rows={cb.by_league_year as unknown as Record<string, unknown>[]} filename="balance_by_league_season" /></>}>
      <div className="mb-3 flex flex-wrap gap-1.5">{leagues.slice(0, 24).map((l) => (
        <button key={l} onClick={() => setSel(sel.includes(l) ? sel.filter((x) => x !== l) : [...sel, l].slice(-6))}
          className={cx("rounded border px-2 py-0.5 text-xs", sel.includes(l) ? "border-cyan/60 bg-cyan/10 text-cyan" : "border-line text-ink-2 hover:text-ink")}>{l}</button>))}</div>
      <TimeLine data={rows} x="year" series={sel.map((l, i) => ({ key: l, label: l, color: CHART.series[i] }))} height={280}
        reference={metric === "noll_scully" ? { y: 1, label: "chance level" } : undefined} />
      <p className="mt-2 text-2xs text-ink-3">Up to 6 leagues. Unit: one league split, regular season only. Share variable: each team&apos;s share of the split&apos;s wins ({m.note}). Season = the source&apos;s season label.</p>
    </Card>
  );
}

function LorenzPanel({ cb }: { cb: NonNullable<CB["competitive_balance"]> }) {
  const ts = cb.tournaments as { tournament_key: string; league: string; year: number; split: string; n_teams: number; gini_wins: number; lorenz_wins: { population_share: number; cumulative_share: number }[] | null }[];
  // default choices: full splits of major leagues (named split, 8+ teams)
  const majors = ts.filter((t) => ["LCK", "LPL", "LEC", "LCS"].includes(t.league) && t.split !== "Unspecified" && t.n_teams >= 8);
  const options = (majors.length ? majors : ts).slice().reverse();
  const [a, setA] = useState(options[0]?.tournament_key || "");
  const [b, setB] = useState(options.find((t) => t.league !== options[0]?.league)?.tournament_key || options[1]?.tournament_key || "");
  const pick = (k: string) => ts.find((t) => t.tournament_key === k);
  const curves = [a, b].map((k) => pick(k)).filter(Boolean).map((t) => ({ label: `${t!.league} ${t!.year} ${t!.split} (Gini ${t!.gini_wins.toFixed(3)})`, points: (t!.lorenz_wins || []) as unknown as Record<string, unknown>[] }));
  const opts = options.map((t) => ({ value: t.tournament_key, label: `${t.league} ${t.year} ${t.split}` }));
  return (
    <Card eyebrow="Lorenz curves" title="Cumulative share of wins held by the bottom x% of teams"
      info="Teams sorted from fewest to most regular-season wins. The diagonal = every team has the same number of wins; the further below, the more concentrated.">
      <div className="mb-3 grid grid-cols-2 gap-2"><Select label="Split A" value={a} onChange={setA} options={opts} /><Select label="Split B" value={b} onChange={setB} options={opts} /></div>
      <Curves curves={curves} x="population_share" y="cumulative_share" xLabel="Share of teams" yLabel="Share of wins" diagonal height={280} />
    </Card>
  );
}

function Placements({ p }: { p: NonNullable<CB["placements"]> }) {
  return (
    <Card eyebrow="Tournament placements" title="Regular-season rank of the eventual champion" info={p.definition}
      actions={<DownloadCsv rows={p.distribution} filename="champion_regular_season_rank" />}>
      <Bars data={p.distribution} x="rank" series={[{ key: "share", label: "Share of splits" }]} yFormat={(v) => fmtPct(v, 0)} height={220} />
      <p className="mt-2 text-xs text-ink-2">The best regular-season team won the derived title in <b className="text-ink">{fmtPct(p.share_rs_first_wins_title)}</b> of {p.n_splits} splits.</p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-2xs text-ink-3">{p.by_league.slice(0, 10).map((l) => <span key={l.league}>{l.league}: {fmtPct(l.share_rs_first_wins_title, 0)} ({l.splits})</span>)}</div>
    </Card>
  );
}

/* ------------------------------------------------------------------ D */
function TournamentModule() {
  const q = useApi<CB>("/analytics/competitive-balance", { game: "lol" });
  return (
    <DataState query={q}>
      {(d, meta) => {
        const tc = d.title_concentration;
        return (
          <div className="grid gap-3 xl:grid-cols-5">
            <Card className="xl:col-span-3" eyebrow="Concentration of success" title="Title concentration by league (HHI)" info={tc?.definition}
              actions={<DownloadCsv rows={(tc?.leagues || []).map(({ ...r }) => r)} filename="title_concentration" />}>
              {tc && tc.leagues.length ? <Bars data={tc.leagues} x="league" series={[{ key: "hhi_titles", label: "HHI of derived titles" }]} layout="vertical" height={Math.max(220, tc.leagues.length * 28)} />
                : <EmptyState title="Not enough splits with playoffs" />}
            </Card>
            <Card className="xl:col-span-2" eyebrow="Dominant teams" title="Most titles per league">
              <div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th">League</th><th className="th">Team</th><th className="th text-right">Titles</th><th className="th text-right">Winners</th></tr></thead>
                <tbody>{(tc?.leagues || []).map((l) => (
                  <tr key={l.league} className="border-b border-line-soft"><td className="td">{l.league}</td><td className="td">{l.top_team}</td>
                    <td className="td num text-right">{l.top_team_titles}/{l.n_tournaments_with_champion}</td><td className="td num text-right">{l.distinct_champions}</td></tr>))}</tbody></table></div>
              <p className="mt-3 text-2xs text-ink-3">Titles are derived (winner of the last playoff game). Prize money is not in the source, so prize concentration is not shown.</p>
            </Card>
            <div className="xl:col-span-5"><SourceNote meta={meta} /></div>
          </div>
        );
      }}
    </DataState>
  );
}

/* ------------------------------------------------------------------ E */
interface Hist {
  side_advantage: { definition: string; by_year: { year: number; n_games: number; blue_win_rate: number; ci95_low: number; ci95_high: number }[] } | null;
  duration_trend: { definition: string; n_missing: number; by_year: { year: number; mean_minutes: number; median_minutes: number }[] } | null;
  per_year: { year: number; matches: number; tournaments: number }[];
  matches_per_month: { month: string; matches: number }[];
  season_trends: { definition: string; by_year: Record<string, number>[] } | null;
}
function HistoricalModule() {
  const q = useApi<Hist>("/analytics/historical", { game: "lol" });
  return (
    <DataState query={q}>
      {(d, meta) => (
        <div className="grid gap-3 xl:grid-cols-2">
          <Card eyebrow="Side advantage" title="Blue-side win rate by year (95% Wilson interval)" info={d.side_advantage?.definition}
            actions={<DownloadCsv rows={d.side_advantage?.by_year || []} filename="blue_side_win_rate" />}>
            <IntervalBars data={d.side_advantage?.by_year || []} x="year" y="blue_win_rate" low="ci95_low" high="ci95_high" reference={0.5} yFormat={(v) => fmtPct(v)} height={260} />
          </Card>
          <Card eyebrow="Game length" title="Average and median game length by year" info={d.duration_trend?.definition}
            actions={<DownloadCsv rows={d.duration_trend?.by_year || []} filename="game_length_by_year" />}>
            <TimeLine data={d.duration_trend?.by_year || []} x="year" series={[{ key: "mean_minutes", label: "Mean (min)" }, { key: "median_minutes", label: "Median (min)", color: CHART.violet, dashed: true }]} height={260} />
          </Card>
          <Card eyebrow="Year over year" title="Games, active teams and tournaments per year" info={d.season_trends?.definition}
            actions={<DownloadCsv rows={d.season_trends?.by_year || []} filename="season_trends" />}>
            <TimeLine data={d.season_trends?.by_year || []} x="year" height={240}
              series={[{ key: "active_teams", label: "Active teams", color: CHART.cyan }, { key: "tournaments", label: "Tournaments", color: CHART.violet }, { key: "teams_20plus_games", label: "Teams with 20+ games", color: CHART.emerald }]} />
          </Card>
          <Card eyebrow="Distribution of team performance" title="Spread of team win % by year" info={d.season_trends?.definition}>
            <TimeLine data={d.season_trends?.by_year || []} x="year" height={240} yFormat={(v) => fmtPct(v, 0)}
              series={[{ key: "wp_p90", label: "90th percentile", color: CHART.cyan }, { key: "wp_p75", label: "75th", color: CHART.violet, dashed: true },
                { key: "wp_p50", label: "Median", color: CHART.emerald }, { key: "wp_p25", label: "25th", color: CHART.violet, dashed: true }, { key: "wp_p10", label: "10th percentile", color: CHART.cyan }]} />
            <p className="mt-2 text-2xs text-ink-3">A narrowing band means team results became more similar. Coverage of leagues changes across years, which also moves these lines.</p>
          </Card>
          <Card eyebrow="Year over year" title="Games per year" actions={<DownloadCsv rows={d.per_year} filename="games_per_year" />}>
            <Bars data={d.per_year} x="year" series={[{ key: "matches", label: "Games" }]} height={240} />
          </Card>
          <Card eyebrow="Time series" title="Games per month" actions={<DownloadCsv rows={d.matches_per_month} filename="games_per_month" />}>
            <TimeLine data={d.matches_per_month} x="month" series={[{ key: "matches", label: "Games" }]} height={240} />
          </Card>
          <div className="xl:col-span-2"><SourceNote meta={meta} extra="Counts reflect source coverage, which differs across leagues and years." /></div>
        </div>
      )}
    </DataState>
  );
}

/* ------------------------------------------------------------------ F */
interface LeagueLevel { league: string; level: number; offset_vs_initial: number; cross_league_games: number; linked_to_international: boolean }
interface Reg {
  league_levels?: { k_league: number; definition: string; leagues: LeagueLevel[] };
  regional: { definition: string; leagues: { league: string; n_games: number; n_teams: number; first: string; last: string }[]; international_available: boolean;
    international_by_home_league?: { league: string; games: number; wins: number; win_rate: number; ci95_low: number; ci95_high: number }[] } | null;
}
export function RegionalModule() {
  const q = useApi<Reg>("/analytics/regional", { game: "lol" });
  return (
    <DataState query={q}>
      {(d, meta) => {
        const r = d.regional;
        return (
          <div className="grid gap-3 xl:grid-cols-2">
            <Card eyebrow="International results" title="Win rate at tier-1 international events by home league" info={r?.definition}
              actions={<DownloadCsv rows={r?.international_by_home_league || []} filename="international_by_home_league" />}>
              {r?.international_by_home_league?.length ? (
                <IntervalBars data={r.international_by_home_league} x="league" y="win_rate" low="ci95_low" high="ci95_high" reference={0.5} yFormat={(v) => fmtPct(v)} height={280} />
              ) : <EmptyState title="No international games in the imported data">International events use the league codes MSI and WLDs in the source.</EmptyState>}
            </Card>
            {d.league_levels && <LeagueLevels l={d.league_levels} />}
            <Card eyebrow="Coverage" title="Games and teams per league" actions={<DownloadCsv rows={r?.leagues || []} filename="league_coverage" />}>
              <div className="max-h-[320px] overflow-y-auto"><div className="overflow-x-auto"><table className="w-full"><thead className="border-b border-line"><tr><th className="th">League</th><th className="th text-right">Games</th><th className="th text-right">Teams</th></tr></thead>
                <tbody>{(r?.leagues || []).map((l) => <tr key={l.league} className="border-b border-line-soft"><td className="td">{l.league}</td><td className="td num text-right">{l.n_games}</td><td className="td num text-right">{l.n_teams}</td></tr>)}</tbody></table></div></div>
            </Card>
            <div className="xl:col-span-2"><SourceNote meta={meta} extra={meta.notes.join(" ")} /></div>
          </div>
        );
      }}
    </DataState>
  );
}

function LeagueLevels({ l }: { l: NonNullable<Reg["league_levels"]> }) {
  const [all, setAll] = useState(false);
  const rows = l.leagues.filter((x) => all || x.linked_to_international)
    .map((x) => ({ league: x.league, offset: Math.round(x.offset_vs_initial), games: x.cross_league_games }));
  return (
    <Card className="xl:col-span-2" eyebrow="League strength" title="League level in Elo points (offset from the 1500 start)"
      info={l.definition}
      actions={<><label className="flex items-center gap-2 text-xs text-ink-2"><input type="checkbox" checked={all} onChange={() => setAll(!all)} /> Show weakly linked leagues</label>
        <DownloadCsv rows={l.leagues as unknown as Record<string, unknown>[]} filename="league_levels" /></>}>
      <Bars data={rows} x="league" series={[{ key: "offset", label: "League level vs 1500" }]} layout="vertical" height={Math.max(220, rows.length * 26)} />
      <p className="mt-2 text-2xs text-ink-3">
        Estimated from games between leagues (step k_league = {l.k_league}). {all
          ? "Weakly linked leagues are compared mainly with their regional neighbours, so their level against the major leagues is poorly identified."
          : "Showing leagues regularly linked through international events, where levels are comparable."}
      </p>
    </Card>
  );
}
