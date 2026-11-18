"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowDown, ArrowUp, Trophy } from "lucide-react";
import { TimeLine } from "@/components/charts/charts";
import { Crest, ResultChip, TEAM_A, TEAM_B, VersusBar } from "@/components/ui/match-bits";
import { Breadcrumbs, Card, DataState, InfoTip, SourceNote, cx } from "@/components/ui/primitives";
import { useApi } from "@/hooks/use-api";
import { POSITIONS, fmtDate, fmtDuration, fmtInt, fmtNum, fmtPct } from "@/lib/format";

interface PlayerLine {
  player: string; slug: string; position: string | null; champion: string | null; kills: number | null; deaths: number | null;
  assists: number | null; kda: number | null; kill_participation: number | null; dpm: number | null; damage_share: number | null;
  cspm: number | null; golddiff_at_15: number | null; csdiff_at_15: number | null; vspm: number | null; earned_gpm: number | null;
  gold_share: number | null;
}
interface TeamStats {
  kills: number | null; deaths: number | null; assists: number | null; dragons: number | null; barons: number | null;
  towers: number | null; heralds: number | null; inhibitors: number | null; first_blood: number | null; first_dragon: number | null;
  first_baron: number | null; first_tower: number | null; damage_to_champions: number | null; dpm: number | null;
  vision_score: number | null; total_gold: number | null; earned_gpm: number | null; total_cs: number | null;
  golddiff_at_15: number | null; xpdiff_at_15: number | null; csdiff_at_15: number | null;
}
interface Side {
  name: string; slug: string; side: string; won: boolean; series_wins: number; stats: TeamStats | null; players: PlayerLine[];
  elo: { before: number; after: number; change: number; expected_score: number; league_rating: number | null } | null;
  elo_trend: { date: string; elo: number; match_id: number }[]; form: { result: number; match_id: number; date: string }[];
}
interface Detail {
  id: number; source_match_id: string; match_date: string; patch: string | null; playoffs: boolean | null; game_in_series: number | null;
  duration_seconds: number | null; data_completeness: string | null;
  tournament: { name: string; slug: string; league: string; year: number | null; split: string | null };
  blue: Side; red: Side; series: { id: number; number: number; winner_slug: string; winner: string; duration_seconds: number | null; current: boolean }[];
  series_note: string;
  top_performer: (PlayerLine & { team_slug: string; tournament_role_median: Record<string, number | null> & { n_player_games: number } | null }) | null;
  top_performer_rule: string;
  predictions: { model_key: string; display_name: string; version: string; prob_blue_win: number; split: string }[];
  elo_model_version: string | null;
}

const MODEL_SHORT: Record<string, string> = { elo: "Elo", elo_logit: "Calibrated Elo", logreg: "Logistic" };

function Hero({ d }: { d: Detail }) {
  const a = d.blue, b = d.red;
  const multi = d.series.length > 1;
  return (
    <section className="card relative h-full min-h-[300px] overflow-hidden">
      {/* abstract arena drawing (original artwork) */}
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden>
        <defs>
          <radialGradient id="hero-glow" cx="50%" cy="55%" r="60%">
            <stop offset="0" stopColor="#E5394F" stopOpacity="0.18" />
            <stop offset="1" stopColor="#0B0C10" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="400" height="300" fill="url(#hero-glow)" />
        {[60, 95, 130, 165].map((r) => <ellipse key={r} cx="200" cy="175" rx={r * 1.5} ry={r * 0.55} fill="none" stroke="#ffffff" strokeOpacity="0.05" />)}
        {Array.from({ length: 18 }, (_, i) => i * 20).map((ang) => (
          <line key={ang} x1="200" y1="175" x2={200 + Math.cos((ang * Math.PI) / 180) * 260} y2={175 + Math.sin((ang * Math.PI) / 180) * 95} stroke="#fff" strokeOpacity="0.025" />
        ))}
      </svg>
      <div className="relative flex h-full min-h-[300px] flex-col p-4">
        <p className="text-2xs text-ink-3"><span className="text-ink-2">{d.tournament.league}</span> · {d.tournament.name}{d.playoffs ? " · Playoffs" : ""}</p>
        <div className="mt-6 text-center">
          <p className="font-display text-sm font-semibold text-ink">{d.tournament.name}</p>
          <p className="text-2xs uppercase tracking-widest text-ink-3">{multi ? `Game ${d.series.find((s) => s.current)?.number ?? d.game_in_series ?? ""} of the series` : "Single game"}</p>
        </div>
        <div className="mt-5 flex items-center justify-center gap-4">
          <div className="flex w-24 flex-col items-center gap-1 text-center">
            <Crest name={a.name} color={TEAM_A} size={58} />
            <Link href={`/teams/${a.slug}`} className="text-sm font-semibold hover:text-cyan">{a.name}</Link>
            <span className="text-2xs text-ink-3">{a.side} side</span>
          </div>
          <div className="text-center">
            <p className="num text-4xl font-bold">
              <span className={a.won ? "text-ink" : "text-ink-3"}>{multi ? a.series_wins : a.won ? 1 : 0}</span>
              <span className="mx-3 text-base text-ink-3">vs</span>
              <span className={b.won ? "text-ink" : "text-ink-3"}>{multi ? b.series_wins : b.won ? 1 : 0}</span>
            </p>
            <p className="mt-1 text-2xs text-ink-3">{multi ? "series score (approx.)" : "game result"}</p>
          </div>
          <div className="flex w-24 flex-col items-center gap-1 text-center">
            <Crest name={b.name} color={TEAM_B} size={58} />
            <Link href={`/teams/${b.slug}`} className="text-sm font-semibold hover:text-cyan">{b.name}</Link>
            <span className="text-2xs text-ink-3">{b.side} side</span>
          </div>
        </div>
        <p className="mt-3 text-center text-xs font-semibold" style={{ color: d.blue.won ? TEAM_A : TEAM_B }}>
          <Trophy size={12} className="mr-1 inline" />{(d.blue.won ? a : b).name} won this game
        </p>
        <div className="mt-auto flex flex-wrap justify-between gap-2 pt-4 text-2xs text-ink-3">
          <span>Length: <span className="text-ink-2">{fmtDuration(d.duration_seconds)}</span>{d.patch && <> · Patch <span className="text-ink-2">{d.patch}</span></>}</span>
          <span>Date: <span className="text-ink-2">{fmtDate(d.match_date)}</span></span>
        </div>
      </div>
    </section>
  );
}

function EloChange({ d }: { d: Detail }) {
  const row = (s: Side, color: string) => (
    <div className="flex items-center gap-3 py-2">
      <Crest name={s.name} color={color} size={30} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-semibold">{s.name}</p>
        {s.won && <p className="text-2xs italic text-cyan">Winner</p>}
      </div>
      {s.elo ? (
        <>
          <div className="text-center"><p className="num text-xs">{fmtInt(s.elo.before)}</p><p className="text-[10px] uppercase text-ink-3">before</p></div>
          <div className="text-center"><p className="num text-xs">{fmtInt(s.elo.after)}</p><p className="text-[10px] uppercase text-ink-3">after</p></div>
          <span className={cx("num flex w-16 items-center justify-center gap-0.5 rounded-sm py-1 text-xs font-semibold",
            s.elo.change >= 0 ? "bg-emerald/15 text-emerald" : "bg-cyan/15 text-cyan")}>
            {s.elo.change >= 0 ? <ArrowUp size={11} /> : <ArrowDown size={11} />}{fmtNum(Math.abs(s.elo.change), 1)}
          </span>
        </>
      ) : <span className="text-2xs text-ink-3">no rating</span>}
    </div>
  );
  return (
    <Card title="Elo change" info={`Elo with league offsets (model ${d.elo_model_version ?? "n/a"}). Rating = league level + team component; points move by K × (result − expected score).`}>
      <div className="divide-y divide-line-soft">
        {row(d.blue, TEAM_A)}
        {row(d.red, TEAM_B)}
      </div>
    </Card>
  );
}

function TopPerformer({ d }: { d: Detail }) {
  const p = d.top_performer;
  if (!p) return <Card title="Top performer"><p className="text-xs text-ink-3">No player lines for the winning team.</p></Card>;
  const med = p.tournament_role_median;
  const metrics: { key: keyof PlayerLine; label: string; fmt: (v: number) => string }[] = [
    { key: "kda", label: "KDA", fmt: (v) => fmtNum(v, 1) },
    { key: "kill_participation", label: "KP", fmt: (v) => fmtPct(v, 0) },
    { key: "dpm", label: "DPM", fmt: (v) => fmtInt(v) },
    { key: "damage_share", label: "DMG%", fmt: (v) => fmtPct(v, 0) },
    { key: "cspm", label: "CSPM", fmt: (v) => fmtNum(v, 1) },
  ];
  const color = p.team_slug === d.blue.slug ? TEAM_A : TEAM_B;
  return (
    <Card title="Top performer" info={d.top_performer_rule}>
      <div className="flex gap-4">
        <div className="w-28 shrink-0">
          <div className="flex h-24 items-center justify-center rounded-sm border border-line bg-bg" style={{ boxShadow: `inset 0 -30px 40px -30px ${color}66` }}>
            <span className="font-display text-2xl font-bold" style={{ color }}>{p.player.slice(0, 2).toUpperCase()}</span>
          </div>
          <Link href={`/players/${p.slug}`} className="mt-1.5 block truncate text-sm font-semibold hover:text-cyan">{p.player}</Link>
          <p className="text-2xs text-ink-3">{POSITIONS[(p.position || "").toLowerCase()] ?? p.position}{p.champion ? ` · ${p.champion}` : ""}</p>
          <p className="num mt-1 text-xs text-ink-2">{p.kills}/{p.deaths}/{p.assists}</p>
        </div>
        <div className="flex flex-1 items-end gap-1.5">
          {metrics.map((m) => {
            const v = p[m.key] as number | null;
            const base = med?.[m.key as string] ?? null;
            const ratio = v != null && base ? v / base : null;
            const h = ratio == null ? 0 : Math.min(1, ratio / 2);
            return (
              <div key={m.key} className="flex flex-1 flex-col items-center gap-1">
                <span className="num text-[11px] text-ink">{v == null ? "n/a" : m.fmt(v)}</span>
                <div className="relative flex h-24 w-full items-end rounded-sm bg-bg">
                  <div className="w-full rounded-sm" style={{ height: `${h * 100}%`, background: ratio != null && ratio >= 1 ? TEAM_B : "#4B505C" }} />
                  <div className="absolute inset-x-0 border-t border-dashed border-ink-3" style={{ bottom: "50%" }} />
                </div>
                <span className="text-[10px] font-semibold text-ink-2">{m.label}</span>
              </div>
            );
          })}
        </div>
      </div>
      <p className="mt-3 text-2xs text-ink-3">
        Dashed line = median for the same role in this tournament ({fmtInt(med?.n_player_games)} player games). Bar height = value / median, capped at 2×.
      </p>
    </Card>
  );
}

function WinProbability({ d }: { d: Detail }) {
  const rows = d.predictions.length
    ? d.predictions.map((p) => ({ label: MODEL_SHORT[p.model_key] ?? p.display_name, pa: p.prob_blue_win, note: `${p.split} prediction, ${p.version}` }))
    : d.blue.elo ? [{ label: "Elo expectation", pa: d.blue.elo.expected_score, note: "rating-based expectation before the game" }] : [];
  return (
    <Card title="Pre-game win probability" className="h-full"
      info="Stored predictions exist only for games in the validation and test periods (made without knowing the result). For other games the Elo expected score before the game is shown.">
      {rows.length === 0 ? <p className="text-xs text-ink-3">No rating available.</p> : (
        <div className="space-y-4">
          {rows.map((r) => (
            <div key={r.label}>
              <div className="mb-1 flex justify-between text-2xs"><span className="text-ink-2">{r.label}</span><span className="text-ink-3">{r.note}</span></div>
              <div className="flex items-center gap-2">
                <span className="num w-11 text-right text-sm font-semibold" style={{ color: TEAM_A }}>{fmtPct(r.pa, 0)}</span>
                <div className="flex h-2.5 flex-1 overflow-hidden rounded-sm">
                  <div style={{ width: `${r.pa * 100}%`, background: TEAM_A }} />
                  <div className="w-0.5 bg-bg" />
                  <div style={{ width: `${(1 - r.pa) * 100}%`, background: TEAM_B }} />
                </div>
                <span className="num w-11 text-sm font-semibold" style={{ color: TEAM_B }}>{fmtPct(1 - r.pa, 0)}</span>
              </div>
            </div>
          ))}
          <p className="text-2xs text-ink-3">
            Result: <span className="text-ink-2">{(d.blue.won ? d.blue : d.red).name}</span> won.{" "}
            {rows[0] && ((rows[0].pa >= 0.5) === d.blue.won ? "The favourite won." : "An upset by these models.")}
          </p>
          {d.blue.elo && d.red.elo && (
            <dl className="grid grid-cols-2 gap-2 border-t border-line-soft pt-4 text-xs">
              {[
                ["Elo gap before the game", `${fmtInt(Math.abs(d.blue.elo.before - d.red.elo.before))} for ${d.blue.elo.before >= d.red.elo.before ? d.blue.name : d.red.name}`],
                ["League level (home league)", `${fmtInt(d.blue.elo.league_rating)} / ${fmtInt(d.red.elo.league_rating)}`],
                ["Last 10 before (W-L)", `${d.blue.form.filter((f) => f.result === 1).length}-${d.blue.form.filter((f) => f.result === 0).length} / ${d.red.form.filter((f) => f.result === 1).length}-${d.red.form.filter((f) => f.result === 0).length}`],
                ["Elo points exchanged", fmtNum(Math.abs(d.blue.elo.change), 1)],
              ].map(([k, v]) => (
                <div key={k} className="rounded-sm border border-line-soft bg-bg px-2.5 py-2">
                  <dt className="text-2xs text-ink-3">{k}</dt><dd className="num mt-0.5 text-ink">{v}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      )}
    </Card>
  );
}

function EloForm({ d }: { d: Detail }) {
  const a = d.blue.elo_trend, b = d.red.elo_trend;
  const n = Math.max(a.length, b.length);
  const data = Array.from({ length: n }, (_, i) => ({
    g: i - n + 1,
    a: a[a.length - n + i]?.elo != null ? Math.round(a[a.length - n + i].elo) : null,
    b: b[b.length - n + i]?.elo != null ? Math.round(b[b.length - n + i].elo) : null,
  }));
  return (
    <Card title="Elo over the last 20 games" className="h-full" info="Rating after each of the team's games, up to and including this one (0 = this game).">
      <TimeLine data={data} x="g" dots legend={false} height={300}
        series={[{ key: "a", label: d.blue.name, color: TEAM_A }, { key: "b", label: d.red.name, color: TEAM_B }]} />
      <div className="mt-2 flex justify-end gap-4 text-2xs text-ink-2">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: TEAM_A }} />{d.blue.name}</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: TEAM_B }} />{d.red.name}</span>
      </div>
    </Card>
  );
}

function SeriesStrip({ d }: { d: Detail }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
      {d.series.map((g) => {
        const color = g.winner_slug === d.blue.slug ? TEAM_A : TEAM_B;
        return (
          <Link key={g.id} href={`/matches/${g.id}`}
            className={cx("card relative flex h-24 flex-col justify-between overflow-hidden p-2.5 transition-colors hover:border-ink-3",
              g.current && "border-cyan")}>
            <div className="absolute inset-0 opacity-30" style={{ background: `linear-gradient(135deg, ${color}33, transparent 60%)` }} />
            <div className="relative flex items-center justify-between">
              <Crest name={g.winner} color={color} size={26} />
              <span className="text-2xs text-ink-3">{fmtDuration(g.duration_seconds)}</span>
            </div>
            <div className="relative min-w-0">
              <span className="block whitespace-nowrap font-display text-xs font-semibold uppercase">Game {g.number}</span>
              <span className="block truncate text-2xs" style={{ color }}>{g.winner}</span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}

function FormPanel({ d }: { d: Detail }) {
  const row = (s: Side, color: string) => (
    <div className="flex items-center gap-3">
      <Crest name={s.name} color={color} size={26} />
      <div className="flex flex-1 flex-wrap gap-1">
        {s.form.map((f) => (
          <Link key={f.match_id} href={`/matches/${f.match_id}`} title={fmtDate(f.date)}><ResultChip won={f.result === 1} /></Link>
        ))}
        {s.form.length === 0 && <span className="text-2xs text-ink-3">no earlier games</span>}
      </div>
      <span className="num w-12 text-right text-xs text-ink-2">{s.form.length ? `${s.form.filter((f) => f.result === 1).length}-${s.form.filter((f) => f.result === 0).length}` : ""}</span>
    </div>
  );
  return (
    <Card title="Form before this game" info="Each team's last 10 results before this game, oldest first. Click a square to open that game.">
      <div className="space-y-3">{row(d.blue, TEAM_A)}{row(d.red, TEAM_B)}</div>
    </Card>
  );
}

function Scoreboard({ s, color }: { s: Side; color: string }) {
  return (
    <Card title={<span className="flex items-center gap-2"><Crest name={s.name} color={color} size={20} /><span style={{ color }}>{s.name}</span>{s.won && <span className="text-2xs font-normal text-ink-3">winner</span>}</span>}>
      <div className="-mx-4 overflow-x-auto sm:-mx-5">
        <table className="w-full min-w-[640px] text-xs [&_td]:px-2 [&_td]:text-xs [&_th]:px-2">
          <thead><tr className="border-b border-line-soft">
            {["Player", "Role", "Champion", "K", "D", "A", "KDA", "KP", "DPM", "DMG%", "CSPM", "GD@15"].map((h, i) => (
              <th key={h} className={cx("th py-1.5 normal-case tracking-normal", i > 2 && "text-right")}>{h}</th>))}
          </tr></thead>
          <tbody>
            {s.players.map((p) => (
              <tr key={p.slug} className="border-b border-line-soft/60 hover:bg-bg-elev/40">
                <td className="td py-1.5"><Link href={`/players/${p.slug}`} className="font-medium hover:text-cyan">{p.player}</Link></td>
                <td className="td py-1.5 text-ink-2">{POSITIONS[(p.position || "").toLowerCase()] ?? p.position ?? ""}</td>
                <td className="td py-1.5 text-ink-2">{p.champion ?? ""}</td>
                <td className="td num py-1.5 text-right">{p.kills ?? ""}</td>
                <td className="td num py-1.5 text-right">{p.deaths ?? ""}</td>
                <td className="td num py-1.5 text-right">{p.assists ?? ""}</td>
                <td className="td num py-1.5 text-right">{fmtNum(p.kda, 1)}</td>
                <td className="td num py-1.5 text-right">{fmtPct(p.kill_participation, 0)}</td>
                <td className="td num py-1.5 text-right">{fmtInt(p.dpm)}</td>
                <td className="td num py-1.5 text-right">{fmtPct(p.damage_share, 0)}</td>
                <td className="td num py-1.5 text-right">{fmtNum(p.cspm, 1)}</td>
                <td className={cx("td num py-1.5 text-right", p.golddiff_at_15 != null && (p.golddiff_at_15 > 0 ? "text-emerald" : p.golddiff_at_15 < 0 ? "text-cyan" : ""))}>
                  {p.golddiff_at_15 == null ? "n/a" : `${p.golddiff_at_15 > 0 ? "+" : ""}${fmtInt(p.golddiff_at_15)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const sumCs = (s: Side) => {
  const v = s.players.map((p) => (p as PlayerLine & { total_cs?: number | null }).total_cs);
  return v.length && v.every((x) => x != null) ? (v as number[]).reduce((a, b) => a + b, 0) : s.stats?.total_cs ?? null;
};

function TeamStatsPanel({ d }: { d: Detail }) {
  const a = d.blue.stats, b = d.red.stats;
  if (!a || !b) return <Card title="Match stats" className="h-full"><p className="text-xs text-ink-3">No team lines.</p></Card>;
  const k = (v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : fmtInt(v));
  return (
    <Card title="Match stats" className="h-full">
      <div className="mb-4 flex items-center justify-between">
        <span className="flex items-center gap-2 text-xs font-semibold"><Crest name={d.blue.name} color={TEAM_A} size={22} />{d.blue.name}</span>
        <span className="flex items-center gap-2 text-xs font-semibold">{d.red.name}<Crest name={d.red.name} color={TEAM_B} size={22} /></span>
      </div>
      <div className="space-y-3">
        <VersusBar label="Kills" a={a.kills} b={b.kills} />
        <VersusBar label="Deaths" a={a.deaths} b={b.deaths} />
        <VersusBar label="Assists" a={a.assists} b={b.assists} />
        <VersusBar label="Total gold" a={a.total_gold} b={b.total_gold} fmt={k} />
        <VersusBar label="Damage to champions" a={a.damage_to_champions} b={b.damage_to_champions} fmt={k} />
        <VersusBar label="Creep score (sum of player lines)" a={sumCs(d.blue)} b={sumCs(d.red)} fmt={k} />
        <VersusBar label="Vision score" a={a.vision_score} b={b.vision_score} fmt={(v) => fmtInt(v)} />
      </div>
      {a.golddiff_at_15 != null && (
        <p className="mt-4 text-2xs text-ink-3">Gold difference at 15 min: <span className="num" style={{ color: a.golddiff_at_15 >= 0 ? TEAM_A : TEAM_B }}>
          {a.golddiff_at_15 >= 0 ? d.blue.name : d.red.name} +{fmtInt(Math.abs(a.golddiff_at_15))}</span></p>
      )}
    </Card>
  );
}

function Objectives({ d }: { d: Detail }) {
  const a = d.blue.stats, b = d.red.stats;
  if (!a || !b) return null;
  const rows: { label: string; key: keyof TeamStats }[] = [
    { label: "Towers", key: "towers" }, { label: "Dragons", key: "dragons" }, { label: "Heralds", key: "heralds" },
    { label: "Barons", key: "barons" }, { label: "Inhibitors", key: "inhibitors" },
  ];
  const firsts: { label: string; key: keyof TeamStats }[] = [
    { label: "First blood", key: "first_blood" }, { label: "First tower", key: "first_tower" },
    { label: "First dragon", key: "first_dragon" }, { label: "First baron", key: "first_baron" },
  ];
  return (
    <Card title="Objectives" className="h-full" info="Objective counts and 'firsts' from the team rows. The source has no positional (map) data, so a kill map cannot be drawn.">
      <div className="space-y-2.5">
        {rows.map((r) => {
          const av = a[r.key] as number | null, bv = b[r.key] as number | null;
          return (
            <div key={r.key} className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
              <div className="flex justify-end gap-0.5">{Array.from({ length: av ?? 0 }, (_, i) => <span key={i} className="h-3 w-2 rounded-[1px]" style={{ background: TEAM_A }} />)}
                <span className="num ml-1 w-4 text-right text-xs">{av ?? "n/a"}</span></div>
              <span className="w-20 text-center text-2xs text-ink-3">{r.label}</span>
              <div className="flex gap-0.5"><span className="num mr-1 w-4 text-xs">{bv ?? "n/a"}</span>
                {Array.from({ length: bv ?? 0 }, (_, i) => <span key={i} className="h-3 w-2 rounded-[1px]" style={{ background: TEAM_B }} />)}</div>
            </div>
          );
        })}
      </div>
      <div className="mt-5 grid grid-cols-2 gap-2">
        {firsts.map((f) => {
          const who = a[f.key] === 1 ? d.blue : b[f.key] === 1 ? d.red : null;
          const color = who === d.blue ? TEAM_A : TEAM_B;
          return (
            <div key={f.key} className="flex items-center justify-between rounded-sm border border-line-soft bg-bg px-2 py-1.5">
              <span className="text-2xs text-ink-3">{f.label}</span>
              {who ? <Crest name={who.name} color={color} size={18} /> : <span className="text-2xs text-ink-3">none</span>}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default function MatchCentre() {
  const { id } = useParams<{ id: string }>();
  const q = useApi<Detail>(`/matches/${id}`, { game: "lol" });
  return (
    <>
      <Breadcrumbs items={[{ label: "Match centre", href: "/matches" }, {
        label: q.data?.data ? `${q.data.data.blue.name} vs ${q.data.data.red.name}` : `Game ${id}` }]} />
      <DataState query={q}>
        {(d, meta) => (
          <div className="space-y-3">
            <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-12">
              <div className="xl:col-span-3"><Hero d={d} /></div>
              <div className="space-y-3 xl:col-span-3"><EloChange d={d} /><TopPerformer d={d} /></div>
              <div className="xl:col-span-3"><WinProbability d={d} /></div>
              <div className="xl:col-span-3"><EloForm d={d} /></div>
            </div>
            <div className="grid gap-3 xl:grid-cols-12">
              <div className="xl:col-span-6">
                <div className="mb-2 flex items-center gap-2">
                  <p className="panel-title">Series</p><InfoTip text={d.series_note} />
                </div>
                <SeriesStrip d={d} />
              </div>
              <div className="xl:col-span-6 xl:pt-7"><FormPanel d={d} /></div>
            </div>
            <div className="grid gap-3 xl:grid-cols-12">
              <div className="space-y-3 xl:col-span-6">
                <Scoreboard s={d.blue} color={TEAM_A} />
                <Scoreboard s={d.red} color={TEAM_B} />
              </div>
              <div className="xl:col-span-3"><TeamStatsPanel d={d} /></div>
              <div className="xl:col-span-3"><Objectives d={d} /></div>
            </div>
            {d.data_completeness && d.data_completeness !== "complete" && (
              <p className="text-2xs text-amber">This game is flagged &quot;{d.data_completeness}&quot; in the source; some time-based stats are missing.</p>
            )}
            <SourceNote meta={meta} extra={`Game id ${d.source_match_id}.`} />
          </div>
        )}
      </DataState>
    </>
  );
}
