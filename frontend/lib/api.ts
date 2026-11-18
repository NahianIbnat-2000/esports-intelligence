/**
 * API client. The frontend never holds provider credentials: it only talks
 * to the Esports Intelligence backend, whose URL is public configuration.
 */
import { fromSnapshot, trackSlow } from "@/lib/snapshot";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type DataStatus = "available" | "empty" | "integration_pending" | "unavailable" | "insufficient_data";

export interface Meta {
  game: string | null;
  data_status: DataStatus;
  data_type: "historical" | "live" | "demo" | "none";
  source: string | null;
  attribution: string | null;
  sample_period: { start: string | null; end: string | null } | null;
  pagination: { page: number; page_size: number; total: number; pages: number } | null;
  generated_at: string;
  notes: string[];
  /** set when the response was served from the static snapshot */
  snapshot_generated_at?: string;
}

export interface Envelope<T> {
  data: T | null;
  meta: Meta;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type Params = Record<string, string | number | boolean | null | undefined>;

export function buildUrl(path: string, params?: Params): string {
  const url = new URL(`${API_URL}/api/v1${path}`);
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  });
  return url.toString();
}

async function parseError(res: Response): Promise<never> {
  let msg = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") msg = body.detail;
    else if (Array.isArray(body.detail)) msg = body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* non-JSON error body */
  }
  throw new ApiError(res.status, msg);
}

export async function apiGet<T>(path: string, params?: Params): Promise<Envelope<T>> {
  const snap = await fromSnapshot<Envelope<T>>(path, params);
  if (snap) return snap;
  let res: Response;
  try {
    res = await trackSlow(fetch(buildUrl(path, params), { headers: { Accept: "application/json" } }));
  } catch {
    throw new ApiError(0, `Cannot reach the live API at ${API_URL}. It may be asleep or offline; try again in a minute.`);
  }
  if (!res.ok) return parseError(res);
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await trackSlow(fetch(buildUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    }));
  } catch {
    throw new ApiError(0, `Cannot reach the live API at ${API_URL}. It may be asleep or offline; try again in a minute.`);
  }
  if (!res.ok) return parseError(res);
  return res.json();
}

/* ------------------------------------------------------------ shared types */
export interface GameInfo {
  slug: string;
  name: string;
  status: string;
  status_note: string | null;
  n_matches: number | null;
  coverage_start: string | null;
  coverage_end: string | null;
}

export interface TeamSummary {
  slug: string;
  name: string;
  primary_league: string | null;
  n_matches: number;
  n_wins: number;
  win_rate: number | null;
  current_elo: number | null;
  first_match_date: string | null;
  last_match_date: string | null;
  id_from_name: boolean;
}

export interface PlayerSummary {
  slug: string;
  name: string;
  primary_position: string | null;
  n_matches: number;
  first_match_date: string | null;
  last_match_date: string | null;
  latest_team: string | null;
  latest_team_slug: string | null;
}

export interface TournamentSummary {
  slug: string;
  name: string;
  league: string;
  year: number | null;
  split: string | null;
  start_date: string | null;
  end_date: string | null;
  n_matches: number;
  n_teams: number;
  has_playoffs: boolean;
  derived_champion: string | null;
  derived_champion_slug: string | null;
}

export interface MatchSummary {
  id: number;
  source_match_id: string;
  match_date: string;
  tournament: string;
  tournament_slug: string;
  league: string;
  playoffs: boolean | null;
  game_in_series: number | null;
  blue_team: string;
  blue_team_slug: string;
  red_team: string;
  red_team_slug: string;
  winner: string;
  winner_slug: string;
  duration_seconds: number | null;
  patch: string | null;
  data_completeness: string | null;
}

export interface MetricSummary {
  n: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1?: number;
  ece?: number;
  roc_auc: number | null;
  brier: number;
  log_loss: number;
  base_rate_blue_win: number;
}

export interface CalibrationBin {
  bin_lower: number;
  bin_upper: number;
  n: number;
  mean_predicted: number | null;
  observed_frequency: number | null;
}

export interface Comparison {
  metric: string;
  difference: number;
  ci95_low: number;
  ci95_high: number;
  share_bootstrap_model_better: number;
  n_boot: number;
  resampling_unit?: string;
  n_units?: number;
}

export interface ModelInfo {
  model_key: string;
  display_name: string;
  version: string;
  status: string;
  trained_at: string | null;
  periods: Record<string, { n: number; start: string | null; end: string | null; blue_win_rate: number | null } | string | null> | null;
  hyperparameters: Record<string, unknown> | null;
  feature_definitions: { name: string; definition: string; unit: string }[] | null;
  metrics: {
    test?: MetricSummary;
    validation?: MetricSummary;
    calibration?: CalibrationBin[];
    roc?: { fpr: number; tpr: number }[];
    confusion?: Record<string, number>;
    probability_histogram?: { lower: number; upper: number; n: number }[];
    comparisons?: Record<string, Comparison>;
    temporal_breakdown?: Record<string, string | number>[];
    league_breakdown?: Record<string, string | number>[];
    reason?: string;
  } | null;
}
