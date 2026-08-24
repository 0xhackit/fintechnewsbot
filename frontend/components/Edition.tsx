"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import type { FeedEntry } from "@/lib/feed";
import {
  shapeEdition,
  type Story,
  type Desk,
  type DeskKey,
} from "@/lib/broadsheet";

const READING_LIST_KEY = "fintech-onchain-reading-list";

type Filter = "all" | DeskKey;

function ago(ms: number, ref: number): string {
  if (!ms) return "";
  const diff = ref - ms;
  if (diff < 0) return "now";
  const min = Math.floor(diff / 60000);
  if (min < 1) return "now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

function sourcesLabel(n: number): string {
  return n > 1 ? `${n} sources` : "1 source";
}

export default function Edition({
  initialEntries,
  updatedAt,
}: {
  initialEntries: FeedEntry[];
  updatedAt: string;
}) {
  const [entries, setEntries] = useState(initialEntries);
  const [lastUpdated, setLastUpdated] = useState(updatedAt);
  const [saved, setSaved] = useState<string[]>([]);
  const [filter, setFilter] = useState<Filter>("all");
  const [panelOpen, setPanelOpen] = useState(false);
  const [toast, setToast] = useState("");
  // `now` is null until mount so SSR and first client render agree; then it
  // ticks each minute. Times use the feed's own updated_at as the reference
  // until the client takes over.
  const [now, setNow] = useState<number | null>(null);

  const ref = now ?? Date.parse(lastUpdated) ?? 0;

  useEffect(() => {
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(t);
  }, []);

  // Load reading list.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(READING_LIST_KEY);
      if (raw) setSaved(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  // Auto-refresh every 5 minutes.
  const refresh = useCallback(async () => {
    try {
      const r = await fetch("/api/feed");
      if (!r.ok) return;
      const d = await r.json();
      if (d.entries) {
        setEntries(d.entries);
        setLastUpdated(d.updated_at || "");
      }
    } catch {
      /* silent */
    }
  }, []);
  useEffect(() => {
    const t = setInterval(refresh, 5 * 60 * 1000);
    return () => clearInterval(t);
  }, [refresh]);

  const edition = useMemo(
    () => shapeEdition(entries, lastUpdated),
    [entries, lastUpdated]
  );

  const persist = useCallback((next: string[]) => {
    setSaved(next);
    try {
      localStorage.setItem(READING_LIST_KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }, []);

  const flash = useCallback((msg: string) => {
    setToast(msg);
    window.clearTimeout((flash as unknown as { _t?: number })._t);
    (flash as unknown as { _t?: number })._t = window.setTimeout(
      () => setToast(""),
      2000
    );
  }, []);

  const toggleSave = useCallback(
    (id: string) => {
      const has = saved.includes(id);
      persist(has ? saved.filter((x) => x !== id) : saved.concat(id));
      flash(has ? "Removed from reading list" : "Saved for later");
    },
    [saved, persist, flash]
  );

  const copy = useCallback(
    (text: string, msg: string) => {
      try {
        navigator.clipboard.writeText(text);
      } catch {
        /* ignore */
      }
      flash(msg);
    },
    [flash]
  );

  const isSaved = (id: string) => saved.includes(id);
  const savedStories = edition.wire.filter((s) => isSaved(s.id));

  // Segmented desk filter.
  const filters: { key: Filter; label: string; count: number }[] = [
    { key: "all", label: "The whole desk", count: edition.wire.length },
    ...edition.desks.map((d) => ({
      key: d.key as Filter,
      label: d.name,
      count: d.stories.length + (edition.lead?.section === d.key ? 1 : 0),
    })),
  ];

  const visibleDesks =
    filter === "all" ? edition.desks : edition.desks.filter((d) => d.key === filter);
  const wire =
    filter === "all"
      ? edition.wire
      : edition.wire.filter((s) => s.section === filter);
  const deskCount = visibleDesks.reduce((n, d) => n + d.stories.length, 0);

  const SaveButton = ({ story, variant }: { story: Story; variant: "link" | "btn" }) => {
    const on = isSaved(story.id);
    if (variant === "btn") {
      return (
        <button
          type="button"
          className="btn btn-secondary bs-btn"
          style={{ color: on ? "var(--color-accent-2-700)" : undefined }}
          onClick={() => toggleSave(story.id)}
        >
          {on ? "Saved" : "Save"}
        </button>
      );
    }
    return (
      <button
        type="button"
        className="bs-save-link"
        style={{ color: on ? "var(--color-accent-2-700)" : "var(--color-accent-700)" }}
        onClick={() => toggleSave(story.id)}
      >
        {on ? "Saved" : "Save"}
      </button>
    );
  };

  const lead = edition.lead;

  return (
    <div className="broadsheet">
      <div className="bs-page">
        {/* ── Masthead ─────────────────────────────────────────────── */}
        <header>
          <div className="bs-rule-thick" />
          <div className="bs-masthead">
            <h1 className="bs-title">Fintech Onchain</h1>
            <nav className="bs-nav">
              <span className="bs-nav-here">Today</span>
              <a href="#wire">The Wire</a>
              <a href="/analyze">Analyze</a>
              <button
                type="button"
                className="btn btn-secondary bs-btn"
                onClick={() => setPanelOpen((o) => !o)}
              >
                Reading list · {saved.length}
              </button>
            </nav>
          </div>
          <div className="bs-rule-thin" />
          <div className="bs-dateline">
            <span>
              {edition.dateline} · Edition No. {edition.editionNo} ·{" "}
              {edition.partOfDay}
            </span>
            <span>
              {edition.storyCount} stories on file · {edition.sourceCount} sources
            </span>
            <span className="bs-live">
              <span className="bs-live-dot" />
              Live · updated <span suppressHydrationWarning>{ago(Date.parse(lastUpdated), ref)}</span>
            </span>
          </div>
          <div className="bs-rule-hair" />
        </header>

        {/* ── The sixty-second brief ───────────────────────────────── */}
        {edition.brief.length > 0 && (
          <section className="bs-brief">
            <div className="bs-brief-head">
              <span className="bs-kicker bs-kicker-accent">The sixty-second brief</span>
              <span className="bs-kicker bs-kicker-muted">
                {edition.briefLabel}
              </span>
            </div>
            <div className="bs-brief-grid">
              {edition.brief.map((b) => (
                <div key={b.id} className="bs-brief-item">
                  <span className="cmyk-num bs-num">
                    <span className="paper">{b.n}</span>
                    <span className="plate plate-c" aria-hidden="true">{b.n}</span>
                    <span className="plate plate-m" aria-hidden="true">{b.n}</span>
                    <span className="plate plate-y" aria-hidden="true">{b.n}</span>
                  </span>
                  <p className="bs-brief-text">{b.text}</p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ── Lead ─────────────────────────────────────────────────── */}
        {lead && (
          <section className="bs-lead">
            <div className="bs-lead-main">
              <div className="bs-kicker bs-kicker-accent2">
                Lead · {lead.sectionLabel}
              </div>
              <h2 className="bs-lead-title">
                <a href={lead.url} target="_blank" rel="noopener noreferrer">
                  {lead.title}
                </a>
              </h2>
              {lead.deck && <p className="bs-lead-deck">{lead.deck}</p>}
              <div className="bs-lead-meta">
                <span className="tag tag-accent">{lead.sectionLabel}</span>
                <span>{lead.source}</span>
                <span>·</span>
                <span suppressHydrationWarning>{ago(lead.publishedAt, ref)}</span>
                {lead.isConsensus && (
                  <>
                    <span>·</span>
                    <span className="bs-consensus">✓ {sourcesLabel(lead.sources)}</span>
                  </>
                )}
                {lead.coins.slice(0, 3).map((c) => (
                  <span key={c} className="bs-ticker">${c}</span>
                ))}
              </div>
              <div className="bs-lead-actions">
                <SaveButton story={lead} variant="btn" />
                <button
                  type="button"
                  className="btn btn-secondary bs-btn"
                  onClick={() => copy(lead.url, "Link copied")}
                >
                  Copy link
                </button>
                <a
                  href={lead.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-ghost bs-btn"
                >
                  Read at {lead.source} →
                </a>
                {lead.tweetUrl && (
                  <a
                    href={lead.tweetUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-ghost bs-btn"
                  >
                    View on X
                  </a>
                )}
              </div>
            </div>
            <aside className="bs-lead-aside">
              <div className="bs-kicker bs-kicker-muted">Filed by</div>
              <div className="bs-filedby">
                {lead.filedBy.map((f) => (
                  <span key={f} className="tag tag-outline">{f}</span>
                ))}
              </div>
              <LeadContext lead={lead} wire={edition.wire} ref_={ref} />
            </aside>
          </section>
        )}

        {/* ── The desk ─────────────────────────────────────────────── */}
        <section className="bs-desk">
          <div className="bs-desk-controls">
            <div className="seg bs-seg" role="group" aria-label="Filter the desk">
              {filters.map((f) => (
                <label key={f.key} className="seg-opt bs-seg-opt">
                  <input
                    type="radio"
                    name="desk-filter"
                    checked={filter === f.key}
                    onChange={() => setFilter(f.key)}
                  />
                  <span>{f.label}</span>
                  <span className="bs-seg-count">{f.count}</span>
                </label>
              ))}
            </div>
            <span className="bs-kicker bs-kicker-muted">
              {deskCount} {deskCount === 1 ? "story" : "stories"} on the desk
            </span>
          </div>

          <div className="bs-columns">
            {visibleDesks.map((col) => (
              <DeskColumn
                key={col.key}
                col={col}
                ref_={ref}
                isSaved={isSaved}
                onSave={toggleSave}
              />
            ))}
          </div>
        </section>

        {/* ── The Wire ─────────────────────────────────────────────── */}
        <section id="wire" className="bs-wire">
          <div className="bs-wire-head">
            <h3>The Wire</h3>
            <span className="bs-kicker bs-kicker-muted">
              Every story filed, newest first · times UTC
            </span>
          </div>
          <div>
            {(() => {
              const rows: JSX.Element[] = [];
              let prevDay = "";
              for (const w of wire) {
                if (w.dayKey !== prevDay) {
                  prevDay = w.dayKey;
                  rows.push(
                    <div key={`day-${w.dayKey}`} className="bs-wire-day">
                      {w.dayLabel}
                    </div>
                  );
                }
                rows.push(
                  <div key={w.id} className="bs-wire-row">
                    <span className="bs-wire-time" suppressHydrationWarning>
                      {w.time || ago(w.publishedAt, ref)}
                    </span>
                    <div className="bs-wire-body">
                      <a href={w.url} target="_blank" rel="noopener noreferrer" className="bs-wire-title">
                        {w.title}
                      </a>
                      <div className="bs-wire-meta">
                        <span>{w.sectionLabel}</span>
                        <span>·</span>
                        <span>{w.source}</span>
                        {w.isConsensus && (
                          <>
                            <span>·</span>
                            <span className="bs-consensus">✓ {sourcesLabel(w.sources)}</span>
                          </>
                        )}
                        {w.coins.slice(0, 2).map((c) => (
                          <span key={c} className="bs-ticker">${c}</span>
                        ))}
                      </div>
                    </div>
                    <SaveButton story={w} variant="link" />
                  </div>
                );
              }
              return rows;
            })()}
          </div>
          <div className="bs-wire-foot">
            <p>That is the whole file. The next edition prints at 6:00.</p>
            <button
              type="button"
              className="btn btn-primary bs-btn"
              onClick={() => setPanelOpen(true)}
            >
              Open reading list · {saved.length}
            </button>
          </div>
        </section>
      </div>

      {/* ── Reading-list drawer ────────────────────────────────────── */}
      {panelOpen && (
        <>
          <div className="bs-scrim" onClick={() => setPanelOpen(false)} />
          <aside className="bs-drawer">
            <div className="bs-rule-thick bs-drawer-rule" />
            <div className="bs-drawer-head">
              <h3>Reading list</h3>
              <button type="button" className="bs-save-link" onClick={() => setPanelOpen(false)}>
                Close
              </button>
            </div>
            <div className="bs-kicker bs-kicker-muted bs-drawer-sub">
              {saved.length} saved · syncs to your digest
            </div>
            {savedStories.length === 0 ? (
              <p className="bs-drawer-empty">
                Nothing saved yet. Save a story from the desk or the wire and it waits
                here — and in tomorrow&rsquo;s digest.
              </p>
            ) : (
              <div className="bs-drawer-list">
                {savedStories.map((s) => (
                  <div key={s.id} className="bs-drawer-item">
                    <a href={s.url} target="_blank" rel="noopener noreferrer" className="bs-drawer-title">
                      {s.title}
                    </a>
                    <div className="bs-drawer-meta">
                      <span>{s.source}</span>
                      <span>·</span>
                      <span suppressHydrationWarning>{ago(s.publishedAt, ref)}</span>
                      <button
                        type="button"
                        className="bs-save-link"
                        style={{ color: "var(--color-accent-2-700)" }}
                        onClick={() => toggleSave(s.id)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="bs-drawer-actions">
              <button
                type="button"
                className="btn btn-secondary bs-btn"
                disabled={savedStories.length === 0}
                onClick={() => {
                  const rows = [["title", "source", "section", "filed", "url"]].concat(
                    savedStories.map((s) => [s.title, s.source, s.sectionLabel, s.time, s.url])
                  );
                  const csv = rows
                    .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))
                    .join("\n");
                  const a = document.createElement("a");
                  a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
                  a.download = "fintech-onchain-reading-list.csv";
                  a.click();
                  flash(`Exported ${savedStories.length} stories`);
                }}
              >
                Export .csv
              </button>
              <button
                type="button"
                className="btn btn-secondary bs-btn"
                disabled={savedStories.length === 0}
                onClick={() =>
                  copy(
                    savedStories.map((s) => `${s.title} — ${s.url}`).join("\n"),
                    "All links copied"
                  )
                }
              >
                Copy all links
              </button>
              <button
                type="button"
                className="btn btn-ghost bs-btn"
                disabled={savedStories.length === 0}
                onClick={() => {
                  persist([]);
                  flash("Reading list cleared");
                }}
              >
                Clear
              </button>
            </div>
          </aside>
        </>
      )}

      {toast && <div className="bs-toast">{toast}</div>}
    </div>
  );
}

// ── Desk column ────────────────────────────────────────────────────────────────

function DeskColumn({
  col,
  ref_,
  isSaved,
  onSave,
}: {
  col: Desk;
  ref_: number;
  isSaved: (id: string) => boolean;
  onSave: (id: string) => void;
}) {
  return (
    <div className="bs-col">
      <h3 className="bs-col-name">{col.name}</h3>
      <div className="bs-kicker bs-kicker-muted bs-col-note">{col.note}</div>
      <div className="bs-col-stories">
        {col.stories.length === 0 ? (
          <p className="bs-col-empty">Nothing filed to this desk yet.</p>
        ) : (
          col.stories.map((s) => (
            <article key={s.id} className="bs-story">
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="bs-story-title">
                {s.title}
              </a>
              {s.deck && <p className="bs-story-deck">{s.deck}</p>}
              <div className="bs-story-meta">
                <span>{s.source}</span>
                <span>·</span>
                <span suppressHydrationWarning>{ago(s.publishedAt, ref_)}</span>
                {s.isConsensus && (
                  <>
                    <span>·</span>
                    <span className="bs-consensus">✓ 2</span>
                  </>
                )}
                {s.coins.slice(0, 2).map((c) => (
                  <span key={c} className="bs-ticker">${c}</span>
                ))}
                <button
                  type="button"
                  className="bs-save-link"
                  style={{
                    color: isSaved(s.id)
                      ? "var(--color-accent-2-700)"
                      : "var(--color-accent-700)",
                  }}
                  onClick={() => onSave(s.id)}
                >
                  {isSaved(s.id) ? "Saved" : "Save"}
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
}

// ── Lead aside: "more on this desk" (deterministic stand-in for the LLM thread) ──

function LeadContext({
  lead,
  wire,
  ref_,
}: {
  lead: Story;
  wire: Story[];
  ref_: number;
}) {
  const related = wire
    .filter((s) => s.id !== lead.id && s.category === lead.category)
    .slice(0, 3);
  if (related.length === 0) return null;
  return (
    <>
      <div className="bs-kicker bs-kicker-muted bs-aside-head">
        More on the {lead.sectionLabel} desk
      </div>
      <ol className="bs-thread">
        {related.map((s) => (
          <li key={s.id}>
            <a href={s.url} target="_blank" rel="noopener noreferrer">
              {s.title}
            </a>{" "}
            <span className="bs-thread-time" suppressHydrationWarning>
              {ago(s.publishedAt, ref_)}
            </span>
          </li>
        ))}
      </ol>
    </>
  );
}
