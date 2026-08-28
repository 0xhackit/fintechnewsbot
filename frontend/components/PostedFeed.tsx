"use client";

import { useCallback, useEffect, useState } from "react";
import { CATEGORY_LABELS, type Category } from "@/lib/categories";
import type { FeedEntry } from "@/lib/feed";

// Everything that ALREADY posted, with a retract button per item — the escape
// hatch for whatever the deterministic gate let through. Reads the live feed
// (out/feed.json via /api/feed) and calls /api/retract, which pulls the item
// off the website, Telegram and X in one action.

type SurfaceResult = { attempted: boolean; success: boolean; error?: string };
type RetractResult = {
  website?: SurfaceResult;
  telegram?: SurfaceResult;
  x?: SurfaceResult;
  error?: string;
};

const CAT_COLORS: Record<string, { bg: string; fg: string }> = {
  product: { bg: "rgba(0,186,124,0.12)", fg: "#00875a" },
  fundraising: { bg: "rgba(29,155,240,0.12)", fg: "#1565c0" },
  regulation: { bg: "rgba(139,92,246,0.14)", fg: "#6d28d9" },
  other: { bg: "rgba(83,100,113,0.12)", fg: "#536471" },
};

/** Filters aimed at the failure mode: firehose items that cleared the gate. */
const FILTERS = [
  { key: "all", label: "All" },
  { key: "tree", label: "Firehose" },
  { key: "tierC", label: "Tier C" },
  { key: "onX", label: "On X" },
] as const;
type FilterKey = (typeof FILTERS)[number]["key"];

function matches(e: FeedEntry, f: FilterKey): boolean {
  if (f === "tree") return (e.origin || "").includes("tree");
  if (f === "tierC") return e.source_tier === "C";
  if (f === "onX") return Boolean(e.posted_to_x);
  return true;
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.round((Date.now() - then) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  return `${Math.floor(secs / 86400)} d ago`;
}

/** One line per surface, so a partial retraction is legible rather than "failed". */
function surfaceLine(name: string, r?: SurfaceResult): string | null {
  if (!r?.attempted) return null;
  return r.success ? `${name} removed` : `${name} NOT removed — ${r.error || "unknown"}`;
}

export default function PostedFeed({ password }: { password: string }) {
  const [entries, setEntries] = useState<FeedEntry[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, RetractResult>>({});
  const [boosting, setBoosting] = useState<string | null>(null);
  const [boostErr, setBoostErr] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/feed", { cache: "no-store" });
      const data = (await res.json()) as { entries?: FeedEntry[] };
      setEntries(data.entries || []);
      setError("");
    } catch {
      setError("Failed to load the posted feed.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /** Set the manual boost on an entry. `delta` of 0 clears it. */
  async function boost(entry: FeedEntry, delta: number) {
    const next = delta === 0 ? 0 : (entry.boost || 0) + delta;
    setBoosting(entry.id);
    setBoostErr((e) => ({ ...e, [entry.id]: "" }));
    try {
      const res = await fetch("/api/boost", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${password}` },
        body: JSON.stringify({ id: entry.id, boost: next }),
      });
      const json = (await res.json()) as { boost?: number; error?: string };
      if (!res.ok) {
        setBoostErr((e) => ({ ...e, [entry.id]: json.error || `Failed (${res.status})` }));
        return;
      }
      setEntries((es) =>
        es ? es.map((e) => (e.id === entry.id ? { ...e, boost: json.boost || 0 } : e)) : es
      );
    } catch {
      setBoostErr((e) => ({ ...e, [entry.id]: "Network error" }));
    } finally {
      setBoosting(null);
    }
  }

  async function retract(entry: FeedEntry) {
    const surfaces = [
      "the website",
      entry.posted_to_telegram ? "Telegram" : null,
      entry.posted_to_x ? "X" : null,
    ].filter(Boolean);
    if (
      !window.confirm(
        `Retract "${entry.title.slice(0, 60)}"?\n\nThis removes it from ${surfaces.join(
          ", "
        )}. It cannot be undone.`
      )
    ) {
      return;
    }

    setBusyId(entry.id);
    setResults((r) => ({ ...r, [entry.id]: {} }));
    try {
      const res = await fetch("/api/retract", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${password}` },
        body: JSON.stringify({ id: entry.id }),
      });
      const json = (await res.json()) as RetractResult & { success?: boolean };
      setResults((r) => ({ ...r, [entry.id]: json }));
      if (json.success) {
        // Gone from the website — drop the card, keep the result line visible
        // only if a remote surface refused.
        const stuck =
          (json.telegram?.attempted && !json.telegram.success) ||
          (json.x?.attempted && !json.x.success);
        if (!stuck) {
          setEntries((es) => (es ? es.filter((e) => e.id !== entry.id) : es));
        }
      }
    } catch {
      setResults((r) => ({ ...r, [entry.id]: { error: "Network error" } }));
    } finally {
      setBusyId(null);
    }
  }

  if (error) return <div className="pf-empty">{error}</div>;
  if (!entries) return <div className="pf-empty">Loading posted items…</div>;

  const shown = entries.filter((e) => matches(e, filter));
  const count = (f: FilterKey) => entries.filter((e) => matches(e, f)).length;

  return (
    <div className="pf-wrap">
      <div className="pf-head">
        <div className="pf-head-top">
          <h3 className="pf-h3">Posted</h3>
          <span className="pf-gen">
            {loading ? "refreshing…" : `${entries.length} live on the site`}
          </span>
        </div>
        <p className="pf-sub">
          Everything the pipeline already published. <b>Retract</b> pulls an item off the
          website, deletes its Telegram message and deletes its tweet — use it on anything
          the gate let through. Telegram refuses posts older than 48 h; when that happens the
          card stays put and says so.
        </p>
      </div>

      <div className="pf-filters">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`pf-chip ${filter === f.key ? "active" : ""}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label} <span className="pf-count">{count(f.key)}</span>
          </button>
        ))}
        <button className="pf-refresh" onClick={() => load()} title="Reload the feed">
          ↻
        </button>
      </div>

      <div className="pf-list">
        {shown.length === 0 ? (
          <div className="pf-empty">Nothing matches this filter.</div>
        ) : (
          shown.map((e) => {
            const c = CAT_COLORS[e.category || "other"] || CAT_COLORS.other;
            const label =
              (e.category && CATEGORY_LABELS[e.category as Category]) || e.category || "—";
            const r = results[e.id];
            const lines = [
              surfaceLine("Website", r?.website),
              surfaceLine("Telegram", r?.telegram),
              surfaceLine("X", r?.x),
            ].filter(Boolean) as string[];
            return (
              <div key={e.id} className="pf-card">
                <div className="pf-card-top">
                  <span className={`pf-score ${e.boost ? "boosted" : ""}`}>
                    {(e.score ?? 0) + (e.boost || 0)}
                  </span>
                  {e.boost ? (
                    <span className="pf-boosttag">
                      {e.boost > 0 ? "+" : ""}{e.boost} boost
                    </span>
                  ) : null}
                  <span className="pf-badge" style={{ background: c.bg, color: c.fg }}>
                    {label}
                  </span>
                  {(e.origin || "").includes("tree") ? (
                    <span className="pf-tag pf-tree">
                      {e.origin === "rss+tree" ? "✓ consensus" : "Tree"}
                    </span>
                  ) : null}
                  {e.source_tier ? <span className="pf-tier">tier {e.source_tier}</span> : null}
                  <span className="pf-surfaces">
                    {e.posted_to_telegram ? <span className="pf-surface">TG</span> : null}
                    {e.posted_to_x ? (
                      <a
                        className="pf-surface pf-surface-x"
                        href={e.tweet_url || "#"}
                        target="_blank"
                        rel="noreferrer"
                      >
                        X
                      </a>
                    ) : null}
                  </span>
                </div>
                <a className="pf-title" href={e.link} target="_blank" rel="noreferrer">
                  {e.title}
                </a>
                <div className="pf-meta">
                  {e.feed_name || e.source || "—"} · posted {relativeTime(e.posted_at)}
                </div>
                <div className="pf-actions">
                  <span className="pf-boost">
                    <button
                      className="pf-bbtn"
                      disabled={boosting === e.id}
                      title="Rank this higher — added to the pipeline score"
                      onClick={() => boost(e, 25)}
                    >
                      ▲ Boost
                    </button>
                    <button
                      className="pf-bbtn"
                      disabled={boosting === e.id}
                      title="Rank this lower"
                      onClick={() => boost(e, -25)}
                    >
                      ▼
                    </button>
                    {e.boost ? (
                      <button
                        className="pf-bbtn pf-bclear"
                        disabled={boosting === e.id}
                        onClick={() => boost(e, 0)}
                      >
                        clear
                      </button>
                    ) : null}
                    {boostErr[e.id] ? <span className="pf-err">{boostErr[e.id]}</span> : null}
                  </span>
                  <button
                    className="pf-act"
                    disabled={busyId === e.id}
                    onClick={() => retract(e)}
                  >
                    {busyId === e.id ? "Retracting…" : "Retract"}
                  </button>
                  {r?.error ? <span className="pf-err">{r.error}</span> : null}
                  {lines.length ? (
                    <span className="pf-lines">
                      {lines.map((l) => (
                        <span
                          key={l}
                          className={l.includes("NOT removed") ? "pf-line-bad" : "pf-line-ok"}
                        >
                          {l}
                        </span>
                      ))}
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>

      <style>{`
        .pf-wrap { max-width: 640px; margin: 12px auto 0; }
        .pf-head { background:#fff; border:1px solid #eff3f4; border-radius:16px; padding:20px; margin-bottom:14px; }
        .pf-head-top { display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin-bottom:6px; }
        .pf-h3 { font-size:18px; font-weight:800; letter-spacing:-0.02em; }
        .pf-gen { font-size:12px; color:#8b98a5; font-weight:600; white-space:nowrap; }
        .pf-sub { font-size:13px; color:#536471; line-height:1.45; }
        .pf-filters { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-bottom:14px; }
        .pf-chip { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:12.5px; font-weight:700; padding:5px 12px; border-radius:999px; cursor:pointer; }
        .pf-chip:hover { background:rgba(29,155,240,0.08); }
        .pf-chip.active { background:#0f1419; color:#fff; border-color:#0f1419; }
        .pf-count { opacity:0.6; font-weight:600; margin-left:2px; }
        .pf-refresh { margin-left:auto; border:1px solid #eff3f4; background:#fff; width:34px; height:34px; border-radius:999px; cursor:pointer; font-size:16px; color:#536471; }
        .pf-refresh:hover { background:rgba(29,155,240,0.08); color:#1d9bf0; }
        .pf-list { display:flex; flex-direction:column; gap:10px; }
        .pf-card { background:#fff; border:1px solid #eff3f4; border-radius:14px; padding:14px 16px; }
        .pf-card:hover { border-color:#d7dbdc; }
        .pf-card-top { display:flex; align-items:center; gap:8px; margin-bottom:8px; flex-wrap:wrap; }
        .pf-score { font-size:12.5px; font-weight:800; color:#0f1419; background:#eef3f5; border-radius:8px; padding:2px 8px; min-width:30px; text-align:center; }
        .pf-badge { font-size:11.5px; font-weight:700; border-radius:999px; padding:2px 10px; letter-spacing:0.02em; }
        .pf-tier { font-size:11px; font-weight:700; color:#536471; background:#f2f4f5; border:1px solid #e6eaeb; border-radius:6px; padding:1px 6px; }
        .pf-tag { font-size:11px; font-weight:700; border-radius:6px; padding:1px 7px; }
        .pf-tree { color:#6d28d9; background:rgba(139,92,246,0.12); border:1px solid rgba(139,92,246,0.22); }
        .pf-surfaces { display:flex; gap:4px; margin-left:auto; }
        .pf-surface { font-size:11px; font-weight:800; color:#0c447c; background:rgba(29,155,240,0.10); border-radius:6px; padding:1px 7px; text-decoration:none; }
        .pf-surface-x { color:#0f1419; background:#eef3f5; }
        .pf-title { display:block; font-size:15px; font-weight:600; color:#0f1419; text-decoration:none; line-height:1.4; }
        .pf-title:hover { text-decoration:underline; }
        .pf-meta { font-size:12.5px; color:#8b98a5; margin-top:7px; }
        .pf-actions { display:flex; align-items:center; gap:8px; margin-top:12px; flex-wrap:wrap; }
        .pf-act { border:1px solid #f3c9c9; background:#fff; color:#c81e1e; font-size:13px; font-weight:700; padding:6px 16px; border-radius:999px; cursor:pointer; }
        .pf-act:hover:not(:disabled) { background:#fdecec; }
        .pf-act:disabled { opacity:0.5; cursor:default; }
        .pf-err { font-size:12px; color:#c81e1e; font-weight:600; }
        .pf-lines { display:flex; flex-direction:column; gap:2px; font-size:12px; font-weight:600; }
        .pf-line-ok { color:#00875a; }
        .pf-line-bad { color:#c81e1e; }
        .pf-score.boosted { background:#fff3d6; color:#96690a; }
        .pf-boosttag { font-size:11px; font-weight:700; color:#96690a; background:#fff3d6; border:1px solid #f0dcae; border-radius:6px; padding:1px 7px; }
        .pf-boost { display:flex; align-items:center; gap:4px; }
        .pf-bbtn { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:12.5px; font-weight:700; padding:6px 12px; border-radius:999px; cursor:pointer; }
        .pf-bbtn:hover:not(:disabled) { background:rgba(29,155,240,0.08); color:#1d9bf0; border-color:#cfe4f7; }
        .pf-bbtn:disabled { opacity:0.5; cursor:default; }
        .pf-bclear { color:#8b98a5; }
        .pf-empty { text-align:center; color:#536471; padding:40px 20px; font-size:14px; }
      `}</style>
    </div>
  );
}
