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
  const [promoting, setPromoting] = useState<string | null>(null);
  const [rated, setRated] = useState<Record<string, "positive" | "negative">>({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Learned preferences
  const [rules, setRules] = useState<string[]>([]);
  const [newRule, setNewRule] = useState("");
  const [rulesLoading, setRulesLoading] = useState(false);
  const [showPrefs, setShowPrefs] = useState(false);

  const authHeaders = {
    Authorization: `Bearer ${password}`,
    "Content-Type": "application/json",
  };

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

  const fetchRules = useCallback(async () => {
    try {
      const resp = await fetch("/api/feedback", { headers: authHeaders });
      if (!resp.ok) return;
      const data = await resp.json();
      setRules(data.learned_rules || []);
    } catch {
      // silent
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [password]);

  useEffect(() => {
    fetchFeed();
    fetchRules();
  }, [fetchFeed, fetchRules]);

  useEffect(() => {
    if (success) {
      const t = setTimeout(() => setSuccess(""), 3000);
      return () => clearTimeout(t);
    }
  }, [success]);

  async function recordFeedback(
    entry: FeedEntry,
    signal: "positive" | "negative",
    reason: string
  ) {
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          title: entry.title,
          category: entry.ai_category || "other",
          tier: "unknown",
          signal,
          reason,
        }),
      });
    } catch {
      // Best-effort
    }
  }

  async function handleThumbsUp(entry: FeedEntry) {
    setRated((prev) => ({ ...prev, [entry.id]: "positive" }));
    await recordFeedback(entry, "positive", "thumbs_up");
    setSuccess("Learned: more like this!");
  }

  async function handleThumbsDown(entry: FeedEntry) {
    setRated((prev) => ({ ...prev, [entry.id]: "negative" }));
    await recordFeedback(entry, "negative", "thumbs_down");
    setSuccess("Learned: less like this!");
  }

  async function handleDelete(entry: FeedEntry) {
    const confirmed = window.confirm(
      `Delete this post from the feed?\n\n"${entry.title}"`
    );
    if (!confirmed) return;

    setDeleting(entry.id);
    setError("");

    try {
      const resp = await fetch("/api/feed", {
        method: "DELETE",
        headers: authHeaders,
        body: JSON.stringify({ id: entry.id }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(
          (data as { error?: string }).error || `HTTP ${resp.status}`
        );
      }

      setEntries((prev) => prev.filter((e) => e.id !== entry.id));
      setSuccess(`Deleted: ${entry.title.slice(0, 60)}...`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(null);
    }
  }

  async function handlePromoteToX(entry: FeedEntry) {
    const confirmed = window.confirm(
      `Post this to X?\n\n"${entry.title}"`
    );
    if (!confirmed) return;

    setPromoting(entry.id);
    setError("");

    try {
      const resp = await fetch("/api/promote-to-x", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          id: entry.id,
          title: entry.title,
          link: entry.link,
        }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(
          (data as { error?: string }).error || `HTTP ${resp.status}`
        );
      }

      const data = await resp.json();

      // Update local state
      setEntries((prev) =>
        prev.map((e) =>
          e.id === entry.id
            ? {
                ...e,
                posted_to_x: true,
                tweet_url: data.tweetUrl,
                tweet_id: data.tweetId,
              }
            : e
        )
      );
      setRated((prev) => ({ ...prev, [entry.id]: "positive" }));
      setSuccess(`Posted to X!`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Promote failed");
    } finally {
      setPromoting(null);
    }
  }

  async function handleAddRule() {
    const rule = newRule.trim();
    if (!rule) return;
    const updated = [...rules, rule].slice(0, 10);
    setRulesLoading(true);
    try {
      const resp = await fetch("/api/feedback", {
        method: "PUT",
        headers: authHeaders,
        body: JSON.stringify({ learned_rules: updated }),
      });
      if (!resp.ok) throw new Error("Failed to save");
      setRules(updated);
      setNewRule("");
      setSuccess("Rule saved!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setRulesLoading(false);
    }
  }

  async function handleRemoveRule(index: number) {
    const updated = rules.filter((_, i) => i !== index);
    setRulesLoading(true);
    try {
      await fetch("/api/feedback", {
        method: "PUT",
        headers: authHeaders,
        body: JSON.stringify({ learned_rules: updated }),
      });
      setRules(updated);
    } catch {
      // silent
    } finally {
      setRulesLoading(false);
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
              <div className="feed-mgr-actions">
                <button
                  className={`btn-thumbs btn-thumbs-up ${rated[entry.id] === "positive" ? "btn-thumbs-active" : ""}`}
                  onClick={() => handleThumbsUp(entry)}
                  disabled={!!rated[entry.id]}
                  title="More like this"
                >
                  {"\u25B2"}
                </button>
                <button
                  className={`btn-thumbs btn-thumbs-down ${rated[entry.id] === "negative" ? "btn-thumbs-active" : ""}`}
                  onClick={() => handleThumbsDown(entry)}
                  disabled={!!rated[entry.id]}
                  title="Less like this"
                >
                  {"\u25BC"}
                </button>
                {!entry.posted_to_x && (
                  <button
                    className="btn-promote"
                    onClick={() => handlePromoteToX(entry)}
                    disabled={promoting === entry.id}
                    title="Post to X"
                  >
                    {promoting === entry.id ? "..." : "X"}
                  </button>
                )}
                <button
                  className="btn-delete"
                  onClick={() => handleDelete(entry)}
                  disabled={deleting === entry.id}
                  title="Delete post"
                >
                  {deleting === entry.id ? "..." : "\u00D7"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Learned Preferences */}
      <button
        className="prefs-toggle"
        onClick={() => setShowPrefs(!showPrefs)}
      >
        {showPrefs ? "Hide" : "Show"} Learned Preferences
        {rules.length > 0 && (
          <span className="kw-count" style={{ marginLeft: 8 }}>
            {rules.length}
          </span>
        )}
      </button>

      {showPrefs && (
        <div className="prefs-section">
          <div className="kw-add-row">
            <input
              type="text"
              placeholder='e.g. "Never post Bitcoin price speculation"'
              value={newRule}
              onChange={(e) => setNewRule(e.target.value)}
              onKeyDown={(e) =>
                e.key === "Enter" && !rulesLoading && handleAddRule()
              }
              className="input kw-input"
              maxLength={200}
              disabled={rulesLoading}
            />
            <button
              className="btn btn-primary"
              onClick={handleAddRule}
              disabled={!newRule.trim() || rulesLoading || rules.length >= 10}
            >
              Add
            </button>
          </div>

          {rules.length === 0 && (
            <p className="kw-empty">
              No rules yet. Add rules to teach the agent your preferences.
            </p>
          )}

          {rules.length > 0 && (
            <div className="kw-tags">
              {rules.map((rule, i) => (
                <span key={i} className="kw-tag">
                  {rule}
                  <button
                    className="kw-remove"
                    onClick={() => handleRemoveRule(i)}
                    disabled={rulesLoading}
                  >
                    {"\u00D7"}
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
