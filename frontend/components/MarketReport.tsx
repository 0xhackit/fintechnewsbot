"use client";

import { useEffect, useState } from "react";

type MarketItem = {
  title: string;
  link: string;
  snippet?: string;
  score?: number;
  category?: string;
  verdict: "keep" | "kill" | "review";
  axis: string;
  reason: string;
  matched: string | null;
  // v2 (standalone) fields — absent on feed/items sources
  regions?: string[];
  primary_region?: string | null;
  content_type?: string;
  source_tier?: string;
};

type Meta = {
  source: string;
  label: string;
  generated_at: string;
  total: number;
} | null;

type MarketData = {
  source: Source;
  kept: MarketItem[];
  killed: MarketItem[];
  review: MarketItem[];
  total: number;
  generated: boolean;
  meta: Meta;
};

type Tab = "kept" | "killed" | "review";
type Source = "feed" | "items" | "standalone";

const SOURCE_LABELS: Record<Source, string> = {
  feed: "Published feed",
  items: "Current candidates",
  standalone: "Standalone (v2)",
};

const REGIONS = ["APAC", "US", "EU", "LatAm"] as const;

const LANES: { key: string; label: string }[] = [
  { key: "product_launch", label: "Product" },
  { key: "breaking", label: "Breaking" },
  { key: "price_move", label: "Price" },
  { key: "funding", label: "Funding" },
  { key: "deal", label: "Deals" },
  { key: "regulatory_action", label: "Regulatory" },
];

const CONTENT_COLORS: Record<string, { bg: string; fg: string; label: string }> = {
  product_launch: { bg: "rgba(0,186,124,0.12)", fg: "#00875a", label: "product" },
  funding: { bg: "rgba(29,155,240,0.12)", fg: "#1565c0", label: "funding" },
  deal: { bg: "rgba(139,92,246,0.14)", fg: "#6d28d9", label: "deal" },
  regulatory_action: { bg: "rgba(0,186,124,0.12)", fg: "#00875a", label: "regulatory" },
  price_move: { bg: "rgba(245,158,11,0.14)", fg: "#b45309", label: "price move" },
  breaking: { bg: "rgba(15,20,25,0.08)", fg: "#0f1419", label: "breaking" },
  slop: { bg: "rgba(244,33,46,0.12)", fg: "#c81e1e", label: "slop" },
  other: { bg: "rgba(83,100,113,0.12)", fg: "#536471", label: "other" },
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

const AXIS_COLORS: Record<string, { bg: string; fg: string; label: string }> = {
  market_event: { bg: "rgba(0,186,124,0.12)", fg: "#00875a", label: "market event" },
  regulatory_action: { bg: "rgba(0,186,124,0.12)", fg: "#00875a", label: "reg action" },
  commentary: { bg: "rgba(245,158,11,0.14)", fg: "#b45309", label: "commentary" },
  policy: { bg: "rgba(139,92,246,0.14)", fg: "#6d28d9", label: "policy" },
  political: { bg: "rgba(244,33,46,0.12)", fg: "#c81e1e", label: "political" },
  low_signal: { bg: "rgba(83,100,113,0.12)", fg: "#536471", label: "low signal" },
};

function Card({ item, showLanes }: { item: MarketItem; showLanes: boolean }) {
  const ct = item.content_type ? CONTENT_COLORS[item.content_type] || CONTENT_COLORS.other : null;
  const axis = AXIS_COLORS[item.axis] || AXIS_COLORS.low_signal;
  return (
    <div className="mk-card">
      <div className="mk-card-top">
        <span className="mk-score">{item.score ?? 0}</span>
        {showLanes && ct ? (
          <span className="mk-badge" style={{ background: ct.bg, color: ct.fg }}>{ct.label}</span>
        ) : (
          <span className="mk-badge" style={{ background: axis.bg, color: axis.fg }}>{axis.label}</span>
        )}
        {showLanes && item.source_tier ? <span className="mk-tier">tier {item.source_tier}</span> : null}
        {showLanes && item.regions && item.regions.length ? (
          <span className="mk-regions">
            {item.regions.map((r) => (
              <span key={r} className="mk-region">{r}</span>
            ))}
          </span>
        ) : null}
        {!showLanes && item.category ? <span className="mk-cat">{item.category}</span> : null}
      </div>
      <a className="mk-title" href={item.link} target="_blank" rel="noreferrer">
        {item.title}
      </a>
      <div className="mk-reason">
        {item.reason}
        {item.matched ? <code className="mk-trigger">{item.matched}</code> : null}
      </div>
    </div>
  );
}

export default function MarketReport() {
  const [data, setData] = useState<MarketData | null>(null);
  const [tab, setTab] = useState<Tab>("kept");
  const [source, setSource] = useState<Source>("standalone");
  const [region, setRegion] = useState<string>("all");
  const [lane, setLane] = useState<string>("all");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  async function load(src: Source = source) {
    setLoading(true);
    try {
      const res = await fetch(`/api/market?source=${src}`, { cache: "no-store" });
      setData(await res.json());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(source);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);

  const isV2 = source === "standalone";

  const sourceToggle = (
    <div className="mk-source">
      {(Object.keys(SOURCE_LABELS) as Source[]).map((s) => (
        <button
          key={s}
          className={`mk-source-btn ${source === s ? "active" : ""}`}
          onClick={() => setSource(s)}
        >
          {SOURCE_LABELS[s]}
        </button>
      ))}
    </div>
  );

  if (error) return <div className="mk-empty">Failed to load the report.</div>;
  if (!data) return <div className="mk-empty">Loading report…</div>;

  if (!data.generated) {
    return (
      <div className="mk-wrap">
        {sourceToggle}
        <div className="mk-empty">
          <p>No report for “{SOURCE_LABELS[source]}” yet.</p>
          <p className="mk-empty-sub">
            Generate it with:
            <br />
            <code>{isV2 ? "python scripts/standalone_pipeline.py" : "python scripts/shadow_market.py"}</code>
          </p>
          <button className="mk-refresh" onClick={() => load()}>Refresh</button>
        </div>
        <Style />
      </div>
    );
  }

  const pct = (n: number) => (data.total ? Math.round((100 * n) / data.total) : 0);

  // Apply region + lane filters (v2 only).
  let base = data[tab];
  if (isV2 && region !== "all") base = base.filter((it) => (it.regions || []).includes(region));
  const laneCount = (key: string) => base.filter((it) => it.content_type === key).length;
  const items = isV2 && lane !== "all" ? base.filter((it) => it.content_type === lane) : base;

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "kept", label: "Kept", count: data.kept.length },
    { key: "killed", label: "Killed", count: data.killed.length },
    { key: "review", label: "Review", count: data.review.length },
  ];

  return (
    <div className="mk-wrap">
      {sourceToggle}
      <div className="mk-head">
        <div className="mk-head-top">
          <h2 className="mk-h2">{isV2 ? "Market feed — v2 preview" : "Market profile — shadow preview"}</h2>
          {data.meta?.generated_at ? (
            <span className="mk-gen" title={new Date(data.meta.generated_at).toLocaleString()}>
              {loading ? "refreshing…" : `generated ${relativeTime(data.meta.generated_at)}`}
            </span>
          ) : null}
        </div>
        <p className="mk-sub">
          {isV2 ? (
            <>
              {data.total} items, tagged by <strong>content lane</strong> and <strong>region</strong>, gated
              by editorial + source tier. Deterministic, $0 LLM.
            </>
          ) : (
            <>
              Strict editorial policy applied to {data.total} items from your{" "}
              <strong>{SOURCE_LABELS[source].toLowerCase()}</strong>.
            </>
          )}
        </p>
        <div className="mk-stats">
          <Stat label="Keep" value={data.kept.length} pct={pct(data.kept.length)} color="#00875a" />
          <Stat label="Kill" value={data.killed.length} pct={pct(data.killed.length)} color="#c81e1e" />
          <Stat label="Review" value={data.review.length} pct={pct(data.review.length)} color="#536471" />
        </div>
      </div>

      <div className="mk-tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`mk-tab ${tab === t.key ? "active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label} <span className="mk-tab-count">{t.count}</span>
          </button>
        ))}
        <button className="mk-refresh-sm" onClick={() => load()} title="Reload after re-running the script">
          ↻
        </button>
      </div>

      {isV2 ? (
        <>
          <div className="mk-filters">
            <button className={`mk-chip ${region === "all" ? "active" : ""}`} onClick={() => setRegion("all")}>
              All regions
            </button>
            {REGIONS.map((r) => (
              <button key={r} className={`mk-chip ${region === r ? "active" : ""}`} onClick={() => setRegion(r)}>
                {r}
              </button>
            ))}
          </div>
          <div className="mk-lanes">
            <button className={`mk-lane ${lane === "all" ? "active" : ""}`} onClick={() => setLane("all")}>
              All <span className="mk-tab-count">{base.length}</span>
            </button>
            {LANES.map((l) => (
              <button
                key={l.key}
                className={`mk-lane ${lane === l.key ? "active" : ""}`}
                onClick={() => setLane(l.key)}
              >
                {l.label} <span className="mk-tab-count">{laneCount(l.key)}</span>
              </button>
            ))}
          </div>
        </>
      ) : null}

      <div className="mk-list">
        {items.length === 0 ? (
          <div className="mk-empty">Nothing matches this filter.</div>
        ) : (
          items.map((it, i) => <Card key={`${tab}-${i}`} item={it} showLanes={isV2} />)
        )}
      </div>

      <Style />
    </div>
  );
}

function Stat({ label, value, pct, color }: { label: string; value: number; pct: number; color: string }) {
  return (
    <div className="mk-stat">
      <div className="mk-stat-val" style={{ color }}>
        {value} <span className="mk-stat-pct">{pct}%</span>
      </div>
      <div className="mk-stat-label">{label}</div>
    </div>
  );
}

function Style() {
  return (
    <style>{`
      .mk-wrap { max-width: 600px; margin: 0 auto; padding: 16px; }
      .mk-source { display:flex; gap:4px; background:#eef3f5; border:1px solid #eff3f4; border-radius:999px; padding:4px; margin-bottom:14px; }
      .mk-source-btn { flex:1; border:none; background:transparent; color:#536471; font-size:13px; font-weight:700;
        padding:8px 10px; border-radius:999px; cursor:pointer; transition:all .15s; }
      .mk-source-btn:hover { color:#0f1419; }
      .mk-source-btn.active { background:#fff; color:#0f1419; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
      .mk-head { background:#fff; border:1px solid #eff3f4; border-radius:16px; padding:20px; margin-bottom:14px; }
      .mk-head-top { display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin-bottom:6px; }
      .mk-gen { font-size:12px; color:#8b98a5; font-weight:600; white-space:nowrap; }
      .mk-h2 { font-size:19px; font-weight:800; letter-spacing:-0.02em; }
      .mk-sub { font-size:13.5px; color:#536471; line-height:1.45; }
      .mk-stats { display:flex; gap:10px; margin-top:16px; }
      .mk-stat { flex:1; background:#f7f9fa; border:1px solid #eff3f4; border-radius:12px; padding:12px; text-align:center; }
      .mk-stat-val { font-size:24px; font-weight:800; letter-spacing:-0.02em; }
      .mk-stat-pct { font-size:13px; font-weight:600; opacity:0.7; }
      .mk-stat-label { font-size:12px; color:#536471; font-weight:600; margin-top:2px; text-transform:uppercase; letter-spacing:0.04em; }
      .mk-tabs { display:flex; gap:6px; align-items:center; margin-bottom:12px; }
      .mk-tab { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:14px; font-weight:700;
        padding:8px 14px; border-radius:999px; cursor:pointer; transition:all .15s; }
      .mk-tab:hover { background:rgba(29,155,240,0.08); }
      .mk-tab.active { background:#0f1419; color:#fff; border-color:#0f1419; }
      .mk-tab-count { opacity:0.6; font-weight:600; margin-left:2px; }
      .mk-refresh-sm { margin-left:auto; border:1px solid #eff3f4; background:#fff; width:34px; height:34px;
        border-radius:999px; cursor:pointer; font-size:16px; color:#536471; }
      .mk-refresh-sm:hover { background:rgba(29,155,240,0.08); color:#1d9bf0; }
      .mk-filters { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:8px; }
      .mk-chip { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:12.5px; font-weight:700;
        padding:5px 12px; border-radius:999px; cursor:pointer; transition:all .15s; }
      .mk-chip:hover { background:rgba(29,155,240,0.08); }
      .mk-chip.active { background:#1d9bf0; color:#fff; border-color:#1d9bf0; }
      .mk-lanes { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:14px; }
      .mk-lane { border:1px solid #eff3f4; background:#fff; color:#536471; font-size:12.5px; font-weight:700;
        padding:5px 12px; border-radius:8px; cursor:pointer; transition:all .15s; }
      .mk-lane:hover { background:rgba(29,155,240,0.08); }
      .mk-lane.active { background:#0f1419; color:#fff; border-color:#0f1419; }
      .mk-list { display:flex; flex-direction:column; gap:10px; }
      .mk-card { background:#fff; border:1px solid #eff3f4; border-radius:14px; padding:14px 16px; transition:border-color .15s; }
      .mk-card:hover { border-color:#d7dbdc; }
      .mk-card-top { display:flex; align-items:center; gap:8px; margin-bottom:8px; flex-wrap:wrap; }
      .mk-score { font-size:12.5px; font-weight:800; color:#0f1419; background:#eef3f5; border-radius:8px; padding:2px 8px; min-width:30px; text-align:center; }
      .mk-badge { font-size:11.5px; font-weight:700; border-radius:999px; padding:2px 10px; text-transform:uppercase; letter-spacing:0.03em; }
      .mk-tier { font-size:11px; font-weight:700; color:#536471; background:#f2f4f5; border:1px solid #e6eaeb; border-radius:6px; padding:1px 6px; }
      .mk-regions { display:flex; gap:4px; margin-left:auto; }
      .mk-region { font-size:11px; font-weight:700; color:#0c447c; background:rgba(29,155,240,0.10); border-radius:6px; padding:1px 7px; }
      .mk-cat { font-size:12px; color:#536471; font-weight:600; margin-left:auto; }
      .mk-title { display:block; font-size:15px; font-weight:600; color:#0f1419; text-decoration:none; line-height:1.4; }
      .mk-title:hover { text-decoration:underline; }
      .mk-reason { font-size:12.5px; color:#536471; margin-top:7px; line-height:1.5; }
      .mk-trigger { background:#f2f4f5; border:1px solid #e6eaeb; border-radius:6px; padding:1px 6px; margin-left:6px; font-size:11.5px; color:#b45309; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
      .mk-empty { text-align:center; color:#536471; padding:40px 20px; font-size:14px; line-height:1.6; }
      .mk-empty-sub { font-size:13px; margin-top:8px; }
      .mk-empty code { background:#f2f4f5; border-radius:6px; padding:2px 7px; font-size:12.5px; }
      .mk-refresh { margin-top:16px; border:1px solid #1d9bf0; background:#1d9bf0; color:#fff; font-weight:700;
        padding:8px 18px; border-radius:999px; cursor:pointer; font-size:14px; }
    `}</style>
  );
}
