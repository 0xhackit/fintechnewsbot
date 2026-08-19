"use client";

import { useEffect, useState } from "react";
import { CATEGORY_ORDER, CATEGORY_LABELS, type Category } from "@/lib/categories";

// Admin-only triage of the v2 standalone pipeline: kept / review / killed,
// filterable by region and the site's 4 sections. Read-only.

type ReviewItem = {
  title: string;
  link: string;
  score?: number;
  verdict: "keep" | "kill" | "review";
  axis: string;
  reason: string;
  matched: string | null;
  regions?: string[];
  primary_region?: string | null;
  category?: string;
  source_tier?: string;
};

type Meta = { generated_at?: string } | null;
type Data = {
  kept: ReviewItem[];
  killed: ReviewItem[];
  review: ReviewItem[];
  total: number;
  generated: boolean;
  meta: Meta;
};
type Tab = "kept" | "killed" | "review";

const REGIONS = ["APAC", "US", "EU", "LatAm"] as const;

const CAT_COLORS: Record<string, { bg: string; fg: string }> = {
  product: { bg: "rgba(0,186,124,0.12)", fg: "#00875a" },
  fundraising: { bg: "rgba(29,155,240,0.12)", fg: "#1565c0" },
  regulation: { bg: "rgba(139,92,246,0.14)", fg: "#6d28d9" },
  other: { bg: "rgba(83,100,113,0.12)", fg: "#536471" },
};

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.round((Date.now() - then) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function Card({ item }: { item: ReviewItem }) {
  const c = item.category ? CAT_COLORS[item.category] || CAT_COLORS.other : CAT_COLORS.other;
  const label = (item.category && CATEGORY_LABELS[item.category as Category]) || item.category || "—";
  return (
    <div className="rq-card">
      <div className="rq-card-top">
        <span className="rq-score">{item.score ?? 0}</span>
        <span className="rq-badge" style={{ background: c.bg, color: c.fg }}>{label}</span>
        {item.source_tier ? <span className="rq-tier">tier {item.source_tier}</span> : null}
        {item.regions && item.regions.length ? (
          <span className="rq-regions">
            {item.regions.map((r) => (
              <span key={r} className="rq-region">{r}</span>
            ))}
          </span>
        ) : null}
      </div>
      <a className="rq-title" href={item.link} target="_blank" rel="noreferrer">{item.title}</a>
      <div className="rq-reason">
        {item.reason}
        {item.matched ? <code className="rq-trigger">{item.matched}</code> : null}
      </div>
    </div>
  );
}

export default function ReviewQueue() {
  const [data, setData] = useState<Data | null>(null);
  const [tab, setTab] = useState<Tab>("kept");
  const [region, setRegion] = useState<string>("all");
  const [lane, setLane] = useState<string>("all");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`/api/market?source=standalone`, { cache: "no-store" });
      setData(await res.json());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <div className="rq-empty">Failed to load the review queue.</div>;
  if (!data) return <div className="rq-empty">Loading review queue…</div>;

  if (!data.generated) {
    return (
      <div className="rq-wrap">
        <div className="rq-empty">
          <p>No review queue yet.</p>
          <p className="rq-empty-sub">
            Generate it with:
            <br />
            <code>python scripts/standalone_pipeline.py</code>
          </p>
          <button className="rq-refresh" onClick={() => load()}>Refresh</button>
        </div>
        <Style />
      </div>
    );
  }

  const pct = (n: number) => (data.total ? Math.round((100 * n) / data.total) : 0);

  let base = data[tab];
  if (region !== "all") base = base.filter((it) => (it.regions || []).includes(region));
  const laneCount = (key: string) => base.filter((it) => it.category === key).length;
  const items = lane !== "all" ? base.filter((it) => it.category === lane) : base;

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "kept", label: "Kept", count: data.kept.length },
    { key: "review", label: "Review", count: data.review.length },
    { key: "killed", label: "Killed", count: data.killed.length },
  ];

  return (
    <div className="rq-wrap">
      <div className="rq-head">
        <div className="rq-head-top">
          <h3 className="rq-h3">Review queue</h3>
          {data.meta?.generated_at ? (
            <span className="rq-gen">{loading ? "refreshing…" : `generated ${relativeTime(data.meta.generated_at)}`}</span>
          ) : null}
        </div>
        <p className="rq-sub">
          v2 pipeline triage — kept / review / killed, tagged by section &amp; region, gated by editorial
          + source tier. Deterministic, $0 LLM. Re-run <code>standalone_pipeline.py</code> then ↻.
        </p>
        <div className="rq-stats">
          <Stat label="Keep" value={data.kept.length} pct={pct(data.kept.length)} color="#00875a" />
          <Stat label="Review" value={data.review.length} pct={pct(data.review.length)} color="#536471" />
          <Stat label="Kill" value={data.killed.length} pct={pct(data.killed.length)} color="#c81e1e" />
        </div>
      </div>

      <div className="rq-tabs">
        {tabs.map((t) => (
          <button key={t.key} className={`rq-tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label} <span className="rq-count">{t.count}</span>
          </button>
        ))}
        <button className="rq-refresh-sm" onClick={() => load()} title="Reload after re-running the pipeline">↻</button>
      </div>

      <div className="rq-filters">
        <button className={`rq-chip ${region === "all" ? "active" : ""}`} onClick={() => setRegion("all")}>All regions</button>
        {REGIONS.map((r) => (
          <button key={r} className={`rq-chip ${region === r ? "active" : ""}`} onClick={() => setRegion(r)}>{r}</button>
        ))}
      </div>
      <div className="rq-lanes">
        <button className={`rq-lane ${lane === "all" ? "active" : ""}`} onClick={() => setLane("all")}>
          All <span className="rq-count">{base.length}</span>
        </button>
        {CATEGORY_ORDER.map((c) => (
          <button key={c} className={`rq-lane ${lane === c ? "active" : ""}`} onClick={() => setLane(c)}>
            {CATEGORY_LABELS[c]} <span className="rq-count">{laneCount(c)}</span>
          </button>
        ))}
      </div>

      <div className="rq-list">
        {items.length === 0 ? (
          <div className="rq-empty">Nothing matches this filter.</div>
        ) : (
          items.map((it, i) => <Card key={`${tab}-${i}`} item={it} />)
        )}
      </div>

      <Style />
    </div>
  );
}

function Stat({ label, value, pct, color }: { label: string; value: number; pct: number; color: string }) {
  return (
    <div className="rq-stat">
      <div className="rq-stat-val" style={{ color }}>{value} <span className="rq-stat-pct">{pct}%</span></div>
      <div className="rq-stat-label">{label}</div>
    </div>
  );
}

function Style() {
  return (
    <style>{`
      .rq-wrap { max-width: 640px; margin: 12px auto 0; }
      .rq-head { background:#fff; border:1px solid #eff3f4; border-radius:16px; padding:20px; margin-bottom:14px; }
      .rq-head-top { display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin-bottom:6px; }
      .rq-h3 { font-size:18px; font-weight:800; letter-spacing:-0.02em; }
      .rq-gen { font-size:12px; color:#8b98a5; font-weight:600; white-space:nowrap; }
      .rq-sub { font-size:13px; color:#536471; line-height:1.45; }
      .rq-sub code { background:#f2f4f5; border-radius:5px; padding:1px 5px; font-size:12px; }
      .rq-stats { display:flex; gap:10px; margin-top:16px; }
      .rq-stat { flex:1; background:#f7f9fa; border:1px solid #eff3f4; border-radius:12px; padding:12px; text-align:center; }
      .rq-stat-val { font-size:24px; font-weight:800; letter-spacing:-0.02em; }
      .rq-stat-pct { font-size:13px; font-weight:600; opacity:0.7; }
      .rq-stat-label { font-size:12px; color:#536471; font-weight:600; margin-top:2px; text-transform:uppercase; letter-spacing:0.04em; }
      .rq-tabs { display:flex; gap:6px; align-items:center; margin-bottom:10px; }
      .rq-tab { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:14px; font-weight:700; padding:8px 14px; border-radius:999px; cursor:pointer; }
      .rq-tab:hover { background:rgba(29,155,240,0.08); }
      .rq-tab.active { background:#0f1419; color:#fff; border-color:#0f1419; }
      .rq-count { opacity:0.6; font-weight:600; margin-left:2px; }
      .rq-refresh-sm { margin-left:auto; border:1px solid #eff3f4; background:#fff; width:34px; height:34px; border-radius:999px; cursor:pointer; font-size:16px; color:#536471; }
      .rq-refresh-sm:hover { background:rgba(29,155,240,0.08); color:#1d9bf0; }
      .rq-filters { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }
      .rq-chip { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:12.5px; font-weight:700; padding:5px 12px; border-radius:999px; cursor:pointer; }
      .rq-chip:hover { background:rgba(29,155,240,0.08); }
      .rq-chip.active { background:#1d9bf0; color:#fff; border-color:#1d9bf0; }
      .rq-lanes { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:14px; }
      .rq-lane { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:12.5px; font-weight:700; padding:5px 12px; border-radius:8px; cursor:pointer; }
      .rq-lane:hover { background:rgba(29,155,240,0.08); }
      .rq-lane.active { background:#0f1419; color:#fff; border-color:#0f1419; }
      .rq-list { display:flex; flex-direction:column; gap:10px; }
      .rq-card { background:#fff; border:1px solid #eff3f4; border-radius:14px; padding:14px 16px; }
      .rq-card:hover { border-color:#d7dbdc; }
      .rq-card-top { display:flex; align-items:center; gap:8px; margin-bottom:8px; flex-wrap:wrap; }
      .rq-score { font-size:12.5px; font-weight:800; color:#0f1419; background:#eef3f5; border-radius:8px; padding:2px 8px; min-width:30px; text-align:center; }
      .rq-badge { font-size:11.5px; font-weight:700; border-radius:999px; padding:2px 10px; letter-spacing:0.02em; }
      .rq-tier { font-size:11px; font-weight:700; color:#536471; background:#f2f4f5; border:1px solid #e6eaeb; border-radius:6px; padding:1px 6px; }
      .rq-regions { display:flex; gap:4px; margin-left:auto; }
      .rq-region { font-size:11px; font-weight:700; color:#0c447c; background:rgba(29,155,240,0.10); border-radius:6px; padding:1px 7px; }
      .rq-title { display:block; font-size:15px; font-weight:600; color:#0f1419; text-decoration:none; line-height:1.4; }
      .rq-title:hover { text-decoration:underline; }
      .rq-reason { font-size:12.5px; color:#536471; margin-top:7px; line-height:1.5; }
      .rq-trigger { background:#f2f4f5; border:1px solid #e6eaeb; border-radius:6px; padding:1px 6px; margin-left:6px; font-size:11.5px; color:#b45309; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
      .rq-empty { text-align:center; color:#536471; padding:40px 20px; font-size:14px; line-height:1.6; }
      .rq-empty-sub { font-size:13px; margin-top:8px; }
      .rq-empty code { background:#f2f4f5; border-radius:6px; padding:2px 7px; font-size:12.5px; }
      .rq-refresh { margin-top:16px; border:1px solid #1d9bf0; background:#1d9bf0; color:#fff; font-weight:700; padding:8px 18px; border-radius:999px; cursor:pointer; font-size:14px; }
    `}</style>
  );
}
