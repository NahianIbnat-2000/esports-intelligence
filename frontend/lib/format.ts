/** Formatting helpers. Every helper returns the placeholder "n/a"
 * for null/undefined so missing values never display as zero. */
export const NA = "n/a";

export function fmtInt(v: number | null | undefined): string {
  return v === null || v === undefined || Number.isNaN(v) ? NA : Math.round(v).toLocaleString("en-US");
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined || Number.isNaN(v)
    ? NA
    : v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined || Number.isNaN(v) ? NA : `${(v * 100).toFixed(digits)}%`;
}

export function fmtSigned(v: number | null | undefined, digits = 4): string {
  if (v === null || v === undefined || Number.isNaN(v)) return NA;
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}`;
}

export function fmtDate(v: string | null | undefined): string {
  if (!v) return NA;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return NA;
  return d.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "2-digit", timeZone: "UTC" });
}

export function fmtDateTime(v: string | null | undefined): string {
  if (!v) return NA;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return NA;
  return `${d.toLocaleString("en-GB", { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "UTC" })} UTC`;
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return NA;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function fmtPeriod(p: { start: string | null; end: string | null } | null | undefined): string {
  if (!p || !p.start) return NA;
  return `${fmtDate(p.start)} to ${fmtDate(p.end)}`;
}

export const POSITIONS: Record<string, string> = { top: "Top", jng: "Jungle", mid: "Mid", bot: "Bot", sup: "Support" };
