"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import PostItem from "./PostItem";
import { FeedEntry } from "@/lib/feed";
import {
  Category,
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  REGIONS,
  isHighSignal,
  resolveCategory,
} from "@/lib/categories";

// ── Dedup helpers (same logic as lib/feed.ts) ──

const STOPWORDS = new Set([
  "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
  "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
  "has", "have", "had", "do", "does", "did", "will", "would", "could",
  "should", "may", "might", "its", "it", "this", "that", "as", "not",
]);

function tokenize(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((w) => w.length > 1 && !STOPWORDS.has(w))
  );
}

function jaccardSimilarity(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 1;
  let intersection = 0;
  for (const token of a) {
    if (b.has(token)) intersection++;
  }
  const union = a.size + b.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

function computeHighlights(entries: FeedEntry[], limit: number = 10): FeedEntry[] {
  const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const selected: { entry: FeedEntry; tokens: Set<string> }[] = [];

  const candidates = entries
    .filter((e) => new Date(e.posted_at).getTime() >= sevenDaysAgo)
    .sort((a, b) => b.score - a.score);

  for (const entry of candidates) {
    if (selected.length >= limit) break;
    const tokens = tokenize(entry.title);
    const isDuplicate = selected.some(
      (s) => jaccardSimilarity(tokens, s.tokens) > 0.35
    );
    if (!isDuplicate) {
      selected.push({ entry, tokens });
    }
  }

  return selected.map((s) => s.entry);
}

// ── Relative time for "Updated X ago" ──

function relativeTimeShort(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Component ──

type View = "top" | "latest" | "highlights";
type SectionFilter = "all" | Category;
type RegionFilter = "all" | (typeof REGIONS)[number];

const byPostedDesc = (a: FeedEntry, b: FeedEntry) =>
  new Date(b.posted_at).getTime() - new Date(a.posted_at).getTime();

const EMPTY_COPY: Record<View, { title: string; sub: string }> = {
  top: {
    title: "No high-signal news yet",
    sub: "Top shows product updates and fundraising. The feed updates every 5 minutes.",
  },
  latest: {
    title: "No news yet",
    sub: "Everything, newest first. The feed updates every 5 minutes.",
  },
  highlights: {
    title: "No highlights yet",
    sub: "Top articles from the past 7 days will appear here.",
  },
};

interface FeedTabsProps {
  initialEntries: FeedEntry[];
  updatedAt: string;
}

export default function FeedTabs({ initialEntries, updatedAt }: FeedTabsProps) {
  const [view, setView] = useState<View>("top");
  const [section, setSection] = useState<SectionFilter>("all");
  const [region, setRegion] = useState<RegionFilter>("all");
  const [entries, setEntries] = useState(initialEntries);
  const [lastUpdated, setLastUpdated] = useState(updatedAt);

  // Auto-refresh feed every 5 minutes
  const refreshFeed = useCallback(async () => {
    try {
      const resp = await fetch("/api/feed");
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.entries) {
        setEntries(data.entries);
        setLastUpdated(data.updated_at || "");
      }
    } catch {
      // silent fail
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(refreshFeed, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [refreshFeed]);

  // Base pools computed once per feed change.
  const allNewest = useMemo(() => [...entries].sort(byPostedDesc), [entries]);
  const highSignal = useMemo(
    () => allNewest.filter((e) => isHighSignal(resolveCategory(e))),
    [allNewest]
  );
  const highlights = useMemo(() => computeHighlights(entries, 10), [entries]);

  const inRegion = useCallback(
    (list: FeedEntry[]) =>
      region === "all" ? list : list.filter((e) => (e.regions || []).includes(region)),
    [region]
  );
  const inSection = useCallback(
    (list: FeedEntry[]) =>
      section === "all" ? list : list.filter((e) => resolveCategory(e) === section),
    [section]
  );

  // View picks the base pool; a chosen section on Top/Latest browses ALL entries of
  // that section (so it never empties); region narrows last.
  let base: FeedEntry[];
  if (view === "highlights") base = highlights;
  else if (section !== "all") base = allNewest;
  else if (view === "top") base = highSignal;
  else base = allNewest;
  const visible = inRegion(inSection(base));

  // Counts: tab counts reflect the region filter; section counts reflect region + the
  // current view's universe (highlights vs all).
  const universe = inRegion(view === "highlights" ? highlights : allNewest);
  const tabs: { key: View; label: string; count: number }[] = [
    { key: "top", label: "Top", count: inRegion(highSignal).length },
    { key: "latest", label: "Latest", count: inRegion(allNewest).length },
    { key: "highlights", label: "Highlights", count: inRegion(highlights).length },
  ];
  const sectionCount = (c: Category) => universe.filter((e) => resolveCategory(e) === c).length;

  const empty = EMPTY_COPY[view];

  return (
    <>
      {/* Primary views */}
      <div className="feed-tabs">
        <div className="feed-tabs-scroll">
          {tabs.map(({ key, label, count }) => (
            <button
              key={key}
              className={`feed-tab ${view === key ? "feed-tab-active" : ""}`}
              onClick={() => setView(key)}
            >
              {label}
              <span className="feed-tab-count">{count}</span>
            </button>
          ))}
        </div>
        <span className="feed-updated" title={lastUpdated}>
          Updated {relativeTimeShort(lastUpdated)}
        </span>
      </div>

      {/* Secondary filters */}
      <div className="feed-filters">
        <div className="feed-filter-row">
          <span className="feed-filter-label">Section</span>
          <button
            className={`feed-chip ${section === "all" ? "feed-chip-active" : ""}`}
            onClick={() => setSection("all")}
          >
            All <span className="feed-chip-count">{universe.length}</span>
          </button>
          {CATEGORY_ORDER.map((c) => (
            <button
              key={c}
              className={`feed-chip ${section === c ? "feed-chip-active" : ""}`}
              onClick={() => setSection(c)}
            >
              {CATEGORY_LABELS[c]} <span className="feed-chip-count">{sectionCount(c)}</span>
            </button>
          ))}
        </div>
        <div className="feed-filter-row">
          <span className="feed-filter-label">Region</span>
          <button
            className={`feed-chip ${region === "all" ? "feed-chip-active" : ""}`}
            onClick={() => setRegion("all")}
          >
            All
          </button>
          {REGIONS.map((r) => (
            <button
              key={r}
              className={`feed-chip ${region === r ? "feed-chip-active" : ""}`}
              onClick={() => setRegion(r)}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="empty-state">
          <p>{empty.title}</p>
          <p>{empty.sub}</p>
        </div>
      ) : view === "highlights" ? (
        <div className="news-feed">
          {visible.map((entry, i) => (
            <article key={entry.id} className="post-item highlight-item">
              <div className="highlight-rank-badge">{i + 1}</div>
              <div className="post-content">
                <a
                  href={entry.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="post-title-link"
                >
                  <h3 className="post-title">{entry.title}</h3>
                </a>
                {entry.snippet && <p className="post-snippet">{entry.snippet}</p>}
                <div className="post-meta">
                  <span className="highlight-score">Score: {entry.score}</span>
                  <span className="post-meta-dot">&middot;</span>
                  <span className="post-time">{relativeTimeShort(entry.posted_at)}</span>
                  <span className="post-meta-dot">&middot;</span>
                  <span className="highlight-category">
                    {CATEGORY_LABELS[resolveCategory(entry)]}
                  </span>
                  {entry.tweet_url && entry.tweet_url.startsWith("https://x.com/") && (
                    <a
                      href={entry.tweet_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="post-tweet-link"
                    >
                      View on X
                    </a>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="news-feed">
          {visible.map((entry) => (
            <PostItem key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </>
  );
}
