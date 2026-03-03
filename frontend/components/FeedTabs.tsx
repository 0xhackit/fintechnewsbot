"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import PostItem from "./PostItem";
import { FeedEntry } from "@/lib/feed";

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

type Tab = "latest" | "highlights";

interface FeedTabsProps {
  initialEntries: FeedEntry[];
  initialHighlights: FeedEntry[];
  updatedAt: string;
}

export default function FeedTabs({
  initialEntries,
  initialHighlights,
  updatedAt,
}: FeedTabsProps) {
  const [tab, setTab] = useState<Tab>("latest");
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

  // Compute highlights client-side from current entries
  const highlights = useMemo(
    () => computeHighlights(entries, 10),
    [entries]
  );

  return (
    <>
      {/* Tab bar */}
      <div className="feed-tabs">
        <button
          className={`feed-tab ${tab === "latest" ? "feed-tab-active" : ""}`}
          onClick={() => setTab("latest")}
        >
          Latest News
        </button>
        <button
          className={`feed-tab ${tab === "highlights" ? "feed-tab-active" : ""}`}
          onClick={() => setTab("highlights")}
        >
          Weekly Highlights
        </button>
        <span className="feed-updated" title={lastUpdated}>
          Updated {relativeTimeShort(lastUpdated)}
        </span>
      </div>

      {/* Latest News tab */}
      {tab === "latest" && (
        <>
          {entries.length === 0 ? (
            <div className="empty-state">
              <p>No articles yet</p>
              <p>The feed updates every 5 minutes.</p>
            </div>
          ) : (
            <div className="news-feed">
              {entries.map((entry) => (
                <PostItem key={entry.id} entry={entry} />
              ))}
            </div>
          )}
        </>
      )}

      {/* Weekly Highlights tab */}
      {tab === "highlights" && (
        <>
          {highlights.length === 0 ? (
            <div className="empty-state">
              <p>No highlights yet</p>
              <p>Top articles from the past 7 days will appear here.</p>
            </div>
          ) : (
            <div className="news-feed">
              {highlights.map((entry, i) => (
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
                    {entry.snippet && (
                      <p className="post-snippet">{entry.snippet}</p>
                    )}
                    <div className="post-meta">
                      <span className="highlight-score">Score: {entry.score}</span>
                      <span className="post-meta-dot">&middot;</span>
                      <span className="post-time">
                        {relativeTimeShort(entry.posted_at)}
                      </span>
                      {entry.ai_category && (
                        <>
                          <span className="post-meta-dot">&middot;</span>
                          <span className="highlight-category">{entry.ai_category}</span>
                        </>
                      )}
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
          )}
        </>
      )}
    </>
  );
}
