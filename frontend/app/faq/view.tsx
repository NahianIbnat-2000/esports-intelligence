"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { Card, PageHeader, cx } from "@/components/ui/primitives";

/* ------------------------------------------------------------------ */
/* Content. Numbers quoted here are the published test results         */
/* (README / research report). Everything else is a definition.        */
/* ------------------------------------------------------------------ */

type QA = { id: string; q: string; a: ReactNode; text: string };

const FAQ: QA[] = [
  {
    id: "what-is-this",
    q: "What is this site?",
    text: "research platform professional league of legends games 2020 data elo machine learning",
    a: <>A research platform built on professional League of Legends games from 2020 onward. It asks one main question: can machine learning predict who wins a game better than a simple rating system called Elo? Around that question it shows every match, team and player, plus statistics on how balanced each league is.</>,
  },
  {
    id: "elo-plain",
    q: "What is Elo, in plain words?",
    text: "elo rating points chess favourite underdog win chance",
    a: <>Elo is a rating system first made for chess. Every team has a number. A higher number means a stronger team. Before a game, the gap between two numbers gives each team a win chance. After the game, the winner takes points from the loser. Beating a stronger team earns many points; beating a weaker team earns few. Try the calculator on this page to see it work.</>,
  },
  {
    id: "elo-leagues",
    q: "Why does each league get its own Elo level?",
    text: "league offset level korea china regional international worlds msi",
    a: <>Teams mostly play inside their own league, so points only move between leagues when their teams meet at events like MSI or Worlds. With one shared scale, a team that beats everyone in a small league could rank above the best teams in Korea or China. So each league has its own level, learned from games between leagues, and each team is rated relative to its league. This change improved predictions more than the machine learning did.</>,
  },
  {
    id: "ml-beat-elo",
    q: "So, does machine learning beat Elo?",
    text: "machine learning logistic regression beat elo result brier small significant",
    a: <>Yes, but only by a little. On test games the models never saw (23 Sep 2025 to 14 Nov 2026), logistic regression had a Brier score of 0.2164 against 0.2170 for calibrated Elo. The difference is statistically clear, but small in practice. Most of the gain came from giving leagues their own Elo level. Details are in the <Link className="link" href="/research">research reports</Link>.</>,
  },
  {
    id: "accuracy",
    q: "What does \"64.7% accuracy\" mean?",
    text: "accuracy percent favourite won baseline blue side 53.5",
    a: <>In the test games, the team that Elo rated higher won 64.7% of the time. For comparison, always picking the blue side was right 53.5% of the time. Esports games are close to a coin flip more often than people expect, so even good models stay well below 100%.</>,
  },
  {
    id: "win-chance",
    q: "A team had a 70% chance and lost. Was the model wrong?",
    text: "probability chance lost wrong calibration 70 percent",
    a: <>Not by itself. A 70% chance means the team should lose about 3 games out of 10 like it. A model is judged over many games: if teams given 70% win about 70% of the time, the model is well calibrated. The calibration chart in the <Link className="link" href="/predictions">model lab</Link> checks exactly this.</>,
  },
  {
    id: "data-source",
    q: "Where does the data come from?",
    text: "data source oracle's elixir riot games affiliated",
    a: <>From Oracle&apos;s Elixir, a public collection of professional League of Legends game data by Tim Sevenhuysen. Game statistics are the property of Riot Games. This site is not affiliated with or endorsed by Riot Games. See <Link className="link" href="/data-sources">data provenance</Link> and the <Link className="link" href="/data-quality">data quality report</Link> for what was kept and removed.</>,
  },
  {
    id: "other-games",
    q: "Why only League of Legends? What about VALORANT and CS2?",
    text: "valorant cs2 counter-strike other games",
    a: <>They are planned. The code has adapters for them, but they stay hidden until a verified data source is connected. The site does not show made-up or placeholder numbers.</>,
  },
  {
    id: "series",
    q: "How are series (best-of-3, best-of-5) built?",
    text: "series bo3 bo5 best of grouped game number",
    a: <>The source data has no series identifier, so series are rebuilt from game times. Games between the same two teams in the same tournament are grouped when they are close in time, and the game number in the source is used to keep long series together. A rebuilt series can be wrong in rare cases.</>,
  },
  {
    id: "betting",
    q: "Can I use this for betting?",
    text: "betting odds gambling advice",
    a: <>No. This is a research project, not betting advice. It shows no odds and the models are fixed at one point in time, so they do not react to roster changes or news.</>,
  },
  {
    id: "slow",
    q: "Why does a page sometimes say the server is waking up?",
    text: "slow loading waking server snapshot",
    a: <>Most views are served from a saved snapshot and load at once. Less common views ask the live server, which sleeps when nobody uses it. The first request wakes it up, which can take up to a minute.</>,
  },
  {
    id: "who",
    q: "Who made this?",
    text: "author nahian ibnat github code",
    a: <>Nahian Ibnat, with an economics and data science background. The code, methods and tests are public on <a className="link" href="https://github.com/NahianIbnat-2000/esports-intelligence" target="_blank" rel="noreferrer">GitHub</a>.</>,
  },
];

type Term = { id: string; term: string; group: string; def: string; aka?: string };

const GROUPS = ["Esports basics", "Ratings and models", "Statistics", "Economics", "Game stats"];

const TERMS: Term[] = [
  // Esports basics
  { id: "league-of-legends", group: "Esports basics", term: "League of Legends (LoL)", def: "A team game made by Riot Games. Two teams of five players try to destroy the other team's base. A professional game usually lasts around 30 minutes." },
  { id: "game", group: "Esports basics", term: "Game (map)", def: "One full match from start to finish. On this site, one game is the basic unit: ratings and predictions are made for single games." },
  { id: "series-term", group: "Esports basics", term: "Series (Bo1, Bo3, Bo5)", aka: "best of", def: "A set of games between two teams. In a best-of-3 (Bo3), the first team to win 2 games wins the series. Best-of-5 (Bo5) needs 3 wins." },
  { id: "side", group: "Esports basics", term: "Blue side / red side", def: "The two starting sides of the map. Blue side picks first in the draft. Historically, blue side wins slightly more often, which is why it is used as a simple baseline." },
  { id: "league", group: "Esports basics", term: "League", aka: "LCK LPL LEC region", def: "A regional competition that runs every year, for example LCK (Korea), LPL (China) and LEC (Europe). Teams mostly play inside their own league." },
  { id: "split", group: "Esports basics", term: "Split", def: "A part of a league's season, such as a spring or summer split. Each split ends with its own playoffs and champion." },
  { id: "international", group: "Esports basics", term: "International events (MSI, Worlds)", aka: "worlds msi mid-season invitational world championship", def: "Tournaments where top teams from different leagues meet. Worlds is the yearly world championship; MSI is held mid-season. These games are the main link between leagues for ratings." },
  { id: "roles", group: "Esports basics", term: "Roles", aka: "top jungle mid bot adc support position", def: "Each player has a position: top, jungle, mid, bot (also called ADC) and support. Player statistics are compared within the same role, because each role has a different job." },
  { id: "champion", group: "Esports basics", term: "Champion", def: "The character a player controls in a game. Each player picks a different champion before the game starts (the draft)." },
  { id: "patch", group: "Esports basics", term: "Patch", aka: "meta", def: "A game update that changes champions and items. Patches can shift which strategies are strong (the meta)." },
  { id: "upset", group: "Esports basics", term: "Upset", def: "A game won by the team with the lower pre-game Elo rating. The upset rate is the share of games won by the underdog." },

  // Ratings and models
  { id: "elo", group: "Ratings and models", term: "Elo rating", aka: "rating points", def: "A number for each team's strength. The gap between two ratings gives a win chance, and after each game the winner takes points from the loser. Bigger surprises move more points. All teams on this site start at 1500." },
  { id: "k-factor", group: "Ratings and models", term: "K-factor", def: "How fast Elo ratings move. A large K reacts quickly to recent results but is noisy; a small K is steady but slow. The value used here was picked on validation games." },
  { id: "league-offset", group: "Ratings and models", term: "League level (league offset)", def: "An extra Elo number for each league. A team's rating is its league level plus its own part. The league level moves only when teams from different leagues play each other." },
  { id: "carry-over", group: "Ratings and models", term: "Carry-over", def: "At the start of a new year, team ratings can be pulled part of the way back toward their league level, because rosters change between seasons." },
  { id: "pre-game", group: "Ratings and models", term: "Pre-game prediction", def: "A prediction made only from information available before the game starts. No statistic from the game itself is used, so the model cannot cheat by looking at the result." },
  { id: "baseline", group: "Ratings and models", term: "Baseline", def: "A very simple prediction used as a reference, such as always picking blue side. A model is only useful if it clearly beats the baseline." },
  { id: "logistic-regression", group: "Ratings and models", term: "Logistic regression", def: "A standard statistical model that turns several inputs (here, rating gap, recent form and similar pre-game numbers) into a win probability between 0 and 1." },
  { id: "calibrated-elo", group: "Ratings and models", term: "Calibrated Elo", def: "Elo's win chances adjusted with a small model so that they match how often teams actually won. It also accounts for the blue-side advantage." },
  { id: "tree-models", group: "Ratings and models", term: "Gradient boosting / random forest", aka: "tree models", def: "More flexible machine learning models built from many decision trees. They were tested here but did not beat logistic regression, so they were not used." },
  { id: "train-test", group: "Ratings and models", term: "Training, validation and test periods", aka: "split by date", def: "Games are split by date. Models learn on older games (training), settings are chosen on the next period (validation), and the final score uses only the newest games (test), which were never used for learning or tuning." },

  // Statistics
  { id: "accuracy-term", group: "Statistics", term: "Accuracy", def: "The share of games where the team given the higher win chance actually won. Easy to read, but it ignores how confident the prediction was." },
  { id: "brier", group: "Statistics", term: "Brier score", def: "The average squared gap between the predicted chance and what happened (1 for a win, 0 for a loss). Lower is better. Always saying 50% gives 0.25. It rewards being confident and right, and punishes being confident and wrong." },
  { id: "log-loss", group: "Statistics", term: "Log loss", def: "Another score for probability predictions. Lower is better. It punishes very confident wrong predictions much more than the Brier score does." },
  { id: "calibration", group: "Statistics", term: "Calibration", aka: "reliability diagram", def: "Whether predicted chances match reality. If games given a 60% chance are won about 60% of the time, the model is well calibrated." },
  { id: "roc-auc", group: "Statistics", term: "ROC-AUC", def: "How well a model ranks winners above losers, from 0.5 (no better than chance) to 1 (perfect ranking). It does not check whether the probabilities themselves are right." },
  { id: "bootstrap", group: "Statistics", term: "Bootstrap", aka: "resampling", def: "A way to measure uncertainty: redraw the test games many times with replacement and recompute the result each time. Here, games from the same series are drawn together because they are not independent." },
  { id: "ci", group: "Statistics", term: "Confidence interval (95% CI)", def: "A range that shows how uncertain a result is. If the whole interval for a difference is below zero, the improvement is unlikely to be luck." },
  { id: "significance", group: "Statistics", term: "Statistically significant vs. practically important", def: "Significant means the difference is unlikely to be chance. Important means it is big enough to matter. A difference can be significant and still too small to matter, as with machine learning against Elo here." },
  { id: "median", group: "Statistics", term: "Median", def: "The middle value when numbers are sorted. Used for role comparisons because a few extreme games do not pull it much." },

  // Economics
  { id: "competitive-balance", group: "Economics", term: "Competitive balance", def: "How evenly wins and titles are spread across teams in a league. Sports economists study it because leagues with very uneven results can lose fan interest." },
  { id: "hhi", group: "Economics", term: "HHI (Herfindahl-Hirschman Index)", def: "Adds up the squared shares (for example, each team's share of wins or titles). Higher means more concentrated in a few teams. The normalised version runs from 0 (perfectly even) to 1 (one team has everything)." },
  { id: "gini", group: "Economics", term: "Gini coefficient", def: "A measure of inequality from 0 (everyone equal) to 1 (one team has everything). Here it is applied to wins or titles, not money." },
  { id: "lorenz", group: "Economics", term: "Lorenz curve", def: "A chart of cumulative shares. The further the curve bends away from the straight diagonal line, the less equal the spread." },
  { id: "noll-scully", group: "Economics", term: "Noll-Scully ratio", def: "The spread of team win rates divided by the spread expected if every game were a coin flip. A value of 1 means as balanced as pure chance; higher means less balanced." },

  // Game stats
  { id: "kda", group: "Game stats", term: "KDA", def: "(Kills + assists) / deaths, with deaths counted as at least 1. A rough measure of how much a player contributed while staying alive." },
  { id: "dpm", group: "Game stats", term: "DPM", def: "Damage to enemy champions per minute." },
  { id: "damage-share", group: "Game stats", term: "Damage share", def: "A player's share of their team's total damage to enemy champions." },
  { id: "cspm", group: "Game stats", term: "CSPM", aka: "creep score", def: "Creep score per minute: minions and monsters killed per minute. Main source of gold for most roles." },
  { id: "gpm", group: "Game stats", term: "Earned GPM", def: "Gold earned per minute, leaving out the gold every player gets automatically over time." },
  { id: "vspm", group: "Game stats", term: "VSPM", aka: "vision score", def: "Vision score per minute: how much a player helped their team see the map, by placing and clearing wards." },
  { id: "gd15", group: "Game stats", term: "GD@15", aka: "gold difference at 15", def: "Gold difference against the opponent at 15 minutes. Shows who was ahead in the early game." },
  { id: "objectives", group: "Game stats", term: "Objectives (dragon, Herald, Baron, towers)", def: "Neutral monsters and buildings that give a team gold or lasting bonuses. Taking them is usually a sign of control of the map." },
  { id: "top-performer", group: "Game stats", term: "Top performer", def: "On match pages: the player on the winning team with the highest KDA in that game. A simple, stated rule, not an expert opinion." },
];

/* ------------------------------------------------------------------ */

const ILLUSTRATIVE_K = 20;
const expected = (a: number, b: number) => 1 / (1 + 10 ** ((b - a) / 400));
const pct = (x: number) => `${(x * 100).toFixed(0)}%`;
const pts = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)}`;
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-");
const norm = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[^\w\s@%.-]/g, "");

function RatingInput({ label, value, onChange, color }: { label: string; value: number; onChange: (v: number) => void; color: string }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="eyebrow" style={{ color }}>{label}</span>
      <div className="flex items-center gap-3">
        <input type="range" min={1200} max={1900} step={10} value={value} onChange={(e) => onChange(+e.target.value)}
          className="w-full accent-[#FF9F1C]" aria-label={`${label} rating`} />
        <span className="num w-14 text-right text-ink">{value}</span>
      </div>
    </label>
  );
}

function EloCalculator() {
  const [a, setA] = useState(1600);
  const [b, setB] = useState(1500);
  const ea = expected(a, b);
  return (
    <Card title="Elo in one minute" eyebrow="Interactive example" className="mb-3">
      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-3 text-sm leading-relaxed text-ink-2">
          <p>Think of Elo as a strength score. Every team starts at 1500. Move the sliders to see how the gap between two teams turns into a win chance, and how many points change hands after the game.</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>Equal ratings mean a 50/50 game.</li>
            <li>A 100-point gap gives the stronger team about a 64% chance.</li>
            <li>A 400-point gap gives about 91%.</li>
            <li>The favourite gains little for winning and loses a lot for losing. The underdog is the opposite.</li>
          </ul>
          <p className="text-xs text-ink-3">Formula: win chance = 1 / (1 + 10<sup>(B − A) / 400</sup>). Points after the game = K × (result − win chance), where result is 1 for a win and 0 for a loss.</p>
        </div>
        <div className="space-y-4 rounded-sm border border-line bg-bg-2 p-3">
          <RatingInput label="Team A" value={a} onChange={setA} color="#4DA3FF" />
          <RatingInput label="Team B" value={b} onChange={setB} color="#FF5C5C" />
          <div>
            <div className="mb-1 flex justify-between text-xs"><span className="text-ink-2">Team A win chance</span><span className="num text-ink">{pct(ea)}</span></div>
            <div className="flex h-2 overflow-hidden rounded-sm" aria-hidden>
              <div style={{ width: `${ea * 100}%`, background: "#4DA3FF" }} />
              <div style={{ width: `${(1 - ea) * 100}%`, background: "#FF5C5C" }} />
            </div>
            <div className="mt-1 flex justify-between text-xs"><span className="text-ink-3">A</span><span className="num text-ink-2">B {pct(1 - ea)}</span></div>
          </div>
          <table className="w-full text-xs">
            <thead><tr className="text-ink-3"><th className="text-left font-normal">If…</th><th className="text-right font-normal">Team A</th><th className="text-right font-normal">Team B</th></tr></thead>
            <tbody className="num">
              <tr><td className="text-ink-2">A wins</td><td className="text-right text-emerald">{pts(ILLUSTRATIVE_K * (1 - ea))}</td><td className="text-right text-danger">{pts(-ILLUSTRATIVE_K * (1 - ea))}</td></tr>
              <tr><td className="text-ink-2">B wins</td><td className="text-right text-danger">{pts(-ILLUSTRATIVE_K * ea)}</td><td className="text-right text-emerald">{pts(ILLUSTRATIVE_K * ea)}</td></tr>
            </tbody>
          </table>
          <p className="text-2xs text-ink-3">Illustrative example with K = {ILLUSTRATIVE_K}. These are not real teams. The site&apos;s own K and league levels are set from validation games (see <Link className="link" href="/methodology">methodology</Link>).</p>
        </div>
      </div>
    </Card>
  );
}

export default function FaqView() {
  const [q, setQ] = useState("");
  const query = norm(q.trim());

  const faq = useMemo(() => !query ? FAQ : FAQ.filter((f) => norm(`${f.q} ${f.text}`).includes(query)), [query]);
  const terms = useMemo(() => {
    const list = !query ? TERMS : TERMS.filter((t) => norm(`${t.term} ${t.aka || ""} ${t.def}`).includes(query));
    return GROUPS.map((g) => ({ g, items: list.filter((t) => t.group === g) })).filter((x) => x.items.length);
  }, [query]);
  const none = query && !faq.length && !terms.length;

  return (
    <>
      <PageHeader eyebrow="Help" title="FAQ and glossary"
        description="Plain-language answers and definitions. No esports or statistics background needed." />

      <label className="mb-3 flex items-center gap-2 rounded-sm border border-line bg-bg-2 px-3 py-2 focus-within:border-cyan">
        <Search size={16} className="shrink-0 text-ink-3" aria-hidden />
        <span className="sr-only">Search definitions</span>
        <input className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-3"
          placeholder="Look up a word, e.g. Elo, Brier, Bo5, KDA, Gini" value={q} onChange={(e) => setQ(e.target.value)} />
        {q && <button type="button" className="text-xs text-ink-3 hover:text-cyan" onClick={() => setQ("")}>Clear</button>}
      </label>

      {!query && <EloCalculator />}

      {none && (
        <Card className="mb-3">
          <p className="text-sm text-ink-2">No match for &ldquo;{q}&rdquo;. Try a shorter word, or open an <a className="link" href="https://github.com/NahianIbnat-2000/esports-intelligence/issues" target="_blank" rel="noreferrer">issue on GitHub</a> to suggest a definition.</p>
        </Card>
      )}

      <div className="grid gap-3 lg:grid-cols-[1fr_1.2fr]">
        {faq.length > 0 && (
          <Card title="Frequently asked questions" className="self-start">
            <div className="divide-y divide-line">
              {faq.map((f, i) => (
                <details key={f.id} id={f.id} className="group py-2" open={!!query || i < 2}>
                  <summary className="flex cursor-pointer list-none items-start justify-between gap-3 text-sm font-semibold text-ink hover:text-cyan">
                    <span>{f.q}</span>
                    <span className="num mt-0.5 text-ink-3 transition-transform group-open:rotate-45" aria-hidden>+</span>
                  </summary>
                  <p className="mt-2 text-sm leading-relaxed text-ink-2">{f.a}</p>
                </details>
              ))}
            </div>
          </Card>
        )}

        {terms.length > 0 && (
          <Card title="Glossary" className="self-start" actions={!query ? (
            <nav className="flex flex-wrap gap-1" aria-label="Glossary sections">
              {GROUPS.map((g) => (
                <a key={g} href={`#g-${slug(g)}`} className="rounded-sm border border-line px-2 py-0.5 text-2xs uppercase tracking-wide text-ink-3 hover:border-cyan hover:text-cyan">{g}</a>
              ))}
            </nav>
          ) : undefined}>
            <div className="space-y-4">
              {terms.map(({ g, items }) => (
                <section key={g} id={`g-${slug(g)}`} className="scroll-mt-24">
                  <h3 className="eyebrow mb-2 text-cyan">{g}</h3>
                  <dl className="divide-y divide-line">
                    {items.map((t) => (
                      <div key={t.id} id={t.id} className={cx("scroll-mt-24 py-2 sm:grid sm:grid-cols-[11rem_1fr] sm:gap-4")}>
                        <dt className="text-sm font-semibold text-ink">{t.term}</dt>
                        <dd className="mt-1 text-sm leading-relaxed text-ink-2 sm:mt-0">{t.def}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ))}
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
