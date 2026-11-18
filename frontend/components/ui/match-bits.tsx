"use client";

import { cx } from "@/components/ui/primitives";

export const TEAM_A = "#E9B23C";
export const TEAM_B = "#33C17A";

export function initials(name: string): string {
  const words = name.replace(/[^A-Za-z0-9 ]/g, " ").split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words.slice(0, 3).map((w) => w[0]).join("").toUpperCase();
}

/** Generated crest (no team logos are stored or used): shield in the team colour with initials. */
export function Crest({ name, color, size = 40 }: { name: string; color: string; size?: number }) {
  const ini = initials(name);
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role="img" aria-label={name}>
      <path d="M20 2 L35 8 V19 C35 28 28.5 34.5 20 38 C11.5 34.5 5 28 5 19 V8 Z" fill={`${color}22`} stroke={color} strokeWidth="2" />
      <text x="20" y="23.5" textAnchor="middle" fontSize={ini.length > 2 ? 9.5 : 12} fontWeight="700" fill={color}
        fontFamily="Space Grotesk Variable, Inter, sans-serif">{ini}</text>
    </svg>
  );
}

/** Two-sided comparison bar (team A gold from the left, team B green from the right). */
export function VersusBar({ label, a, b, fmt = (v: number) => String(v) }: {
  label: string; a: number | null | undefined; b: number | null | undefined; fmt?: (v: number) => string;
}) {
  const av = a ?? 0, bv = b ?? 0;
  const tot = Math.abs(av) + Math.abs(bv);
  const sa = tot ? Math.abs(av) / tot : 0.5;
  return (
    <div>
      <p className="mb-1 text-center text-2xs text-ink-3">{label}</p>
      <div className="flex items-center gap-2">
        <span className={cx("num w-14 text-right text-xs", av > bv ? "text-ink" : "text-ink-2")}>{a == null ? "n/a" : fmt(av)}</span>
        <div className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-bg">
          <div style={{ width: `${sa * 100}%`, background: TEAM_A }} />
          <div style={{ width: `${(1 - sa) * 100}%`, background: TEAM_B }} />
        </div>
        <span className={cx("num w-14 text-xs", bv > av ? "text-ink" : "text-ink-2")}>{b == null ? "n/a" : fmt(bv)}</span>
      </div>
    </div>
  );
}

export function ResultChip({ won, size = "sm" }: { won: boolean; size?: "sm" | "md" }) {
  return (
    <span className={cx("inline-flex items-center justify-center rounded-sm font-bold",
      size === "sm" ? "h-5 w-5 text-[10px]" : "h-7 w-7 text-xs",
      won ? "bg-emerald/15 text-emerald" : "bg-cyan/15 text-cyan")}>{won ? "W" : "L"}</span>
  );
}
