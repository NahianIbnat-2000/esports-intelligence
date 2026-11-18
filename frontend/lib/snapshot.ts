/**
 * Static snapshot layer (hybrid hosting).
 *
 * `make snapshot` writes API responses for the default views of every page to
 * public/snapshot/<fnv1a(key)>.json and lists the keys in manifest.json. A GET whose exact
 * key is listed is served from that file (instant, works while the live API sleeps);
 * every other request goes to the live API. Same key rule as backend/app/snapshot.py.
 */
type Params = Record<string, string | number | boolean | null | undefined>;

export const SNAPSHOT_ENABLED = process.env.NEXT_PUBLIC_SNAPSHOT !== "off";

export function canonicalKey(path: string, params?: Params): string {
  const items = Object.entries(params || {})
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([k, v]) => `${k}=${String(v)}`);
  return items.length ? `${path}?${items.join("&")}` : path;
}

export function fnv1a(s: string): string {
  let h = 0x811c9dc5;
  for (const b of new TextEncoder().encode(s)) {
    h ^= b;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

let manifest: Promise<Set<string> | null> | null = null;

function loadManifest(): Promise<Set<string> | null> {
  if (!manifest) {
    manifest = fetch("/snapshot/manifest.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : null))
      .then((m: { keys?: string[] } | null) => (m?.keys ? new Set(m.keys) : null))
      .catch(() => null);
  }
  return manifest;
}

/** Returns the snapshot response for this request, or null if there is none. */
export async function fromSnapshot<T>(path: string, params?: Params): Promise<T | null> {
  if (!SNAPSHOT_ENABLED || typeof window === "undefined") return null;
  const keys = await loadManifest();
  const key = canonicalKey(path, params);
  if (!keys?.has(key)) return null;
  try {
    const r = await fetch(`/snapshot/${fnv1a(key)}.json`);
    return r.ok ? ((await r.json()) as T) : null;
  } catch {
    return null;
  }
}

/* ---------- "server is waking up" signal for live requests that take long ---------- */
type Listener = (slow: number) => void;
let slow = 0;
const listeners = new Set<Listener>();
export function onSlowRequests(l: Listener) {
  listeners.add(l);
  return () => { listeners.delete(l); };
}
const emit = () => listeners.forEach((l) => l(slow));

/** Wraps a live request: after 3 s without an answer, the wake-up notice is shown. */
export async function trackSlow<T>(p: Promise<T>): Promise<T> {
  let flagged = false;
  const t = setTimeout(() => { flagged = true; slow += 1; emit(); }, 3000);
  try {
    return await p;
  } finally {
    clearTimeout(t);
    if (flagged) { slow -= 1; emit(); }
  }
}
