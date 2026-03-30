"use client";

import { useState, useEffect, useCallback } from "react";
import type { FeedEntry } from "@/lib/feed";

function relativeTime(isoString: string): string {
  if (!isoString) return "";
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function displaySource(entry: FeedEntry): string {
  const KNOWN: Record<string, string> = {
    theblock: "The Block",
    coindesk: "CoinDesk",
    cointelegraph: "CoinTelegraph",
    decrypt: "Decrypt",
    blockworks: "Blockworks",
    dlnews: "DL News",
    finextra: "Finextra",
    pymnts: "PYMNTS",
    manual: "Manual",
  };
  if (entry.feed_name && KNOWN[entry.feed_name]) return KNOWN[entry.feed_name];
  if (entry.source) return entry.source;
  try {
    return new URL(entry.link).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

interface Props {
  password: string;
}

export default function FeedManager({ password }: Props) {
  const [entries, setEntries] = useState<FeedEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const fetchFeed = useCallback(async () => {
    try {
      const resp = await fetch("/api/feed");
      if (!resp.ok) throw new Error("Failed to load feed");
      const data = await resp.json();
      setEntries(data.entries || []);
    } catch {
      setError("Failed to load feed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  useEffect(() => {
    if (success) {
      const t = setTimeout(() => setSuccess(""), 3000);
      return () => clearTimeout(t);
    }
  }, [success]);

  async function handleDelete(entry: FeedEntry) {
    const confirmed = window.confirm(
      `Delete this post from the feed?\n\n"${entry.title}"`
    );
    if (!confirmed) return;

    setDeleting(entry.id);
    setError("");
    setSuccess("");

    try {
      const resp = await fetch("/api/feed", {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${password}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ id: entry.id }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error((data as { error?: string }).error || `HTTP ${resp.status}`);
      }

      // Optimistic removal
      setEntries((prev) => prev.filter((e) => e.id !== entry.id));
      setSuccess(`Deleted: ${entry.title.slice(0, 60)}...`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="controls-card">
      <div className="controls-header">
        <span>Manage Feed</span>
        <span className="kw-count">{entries.length} posts</span>
      </div>

      {loading && <p className="controls-loading">Loading feed...</p>}
      {error && <p className="controls-error">{error}</p>}
      {success && <p className="kw-success">{success}</p>}

      {!loading && entries.length === 0 && (
        <p className="kw-empty">No posts in feed</p>
      )}

      {!loading && entries.length > 0 && (
        <div className="feed-mgr-list">
          {entries.map((entry) => (
            <div key={entry.id} className="feed-mgr-item">
              <div className="feed-mgr-content">
                <span className="feed-mgr-title">{entry.title}</span>
                <span className="feed-mgr-meta">
                  {displaySource(entry)}
                  {" · "}
                  {relativeTime(entry.posted_at)}
                  {entry.posted_to_x && " · X"}
                </span>
              </div>
              <button
                className="btn-delete"
                onClick={() => handleDelete(entry)}
                disabled={deleting === entry.id}
                title="Delete post"
              >
                {deleting === entry.id ? "..." : "\u00D7"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
