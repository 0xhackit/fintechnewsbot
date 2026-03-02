"use client";

import { useState } from "react";
import PostingControls from "./PostingControls";
import KeywordManager from "./KeywordManager";

interface ScrapeResult {
  title: string;
  snippet: string;
  ogImage: string | null;
  source: string;
  url: string;
  tweetText: string;
  tweetStyle: string;
}

interface PostResult {
  xResult: { success: boolean; tweetUrl?: string; error?: string };
  telegramResult: { success: boolean; messageId?: number; error?: string };
  feedUpdated: boolean;
}

type Phase = "auth" | "input" | "preview" | "posting" | "done";

export default function DashboardForm() {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [phase, setPhase] = useState<Phase>("auth");

  // Input
  const [url, setUrl] = useState("");
  const [scraping, setScraping] = useState(false);

  // Preview
  const [scrapeResult, setScrapeResult] = useState<ScrapeResult | null>(null);
  const [tweetText, setTweetText] = useState("");

  // Result
  const [postResult, setPostResult] = useState<PostResult | null>(null);
  const [error, setError] = useState("");

  async function handleLogin() {
    if (!password.trim()) return;
    // Lightweight password check (no external deps like GITHUB_TOKEN)
    try {
      const resp = await fetch("/api/auth-check", {
        headers: { Authorization: `Bearer ${password}` },
      });
      if (resp.ok) {
        setAuthed(true);
        setPhase("input");
        setError("");
      } else {
        setError("Invalid password");
      }
    } catch {
      setError("Connection error");
    }
  }

  async function handleScrape() {
    if (!url.trim()) return;
    setScraping(true);
    setError("");

    try {
      const resp = await fetch("/api/scrape", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${password}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url: url.trim() }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error((data as { error?: string }).error || `HTTP ${resp.status}`);
      }

      const data = (await resp.json()) as ScrapeResult;
      setScrapeResult(data);
      setTweetText(data.tweetText);
      setPhase("preview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scrape failed");
    } finally {
      setScraping(false);
    }
  }

  async function handlePost() {
    if (!scrapeResult) return;
    setPhase("posting");
    setError("");

    try {
      const resp = await fetch("/api/manual-post", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${password}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: scrapeResult.title,
          snippet: scrapeResult.snippet,
          url: scrapeResult.url,
          source: scrapeResult.source,
          tweetText,
        }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error((data as { error?: string }).error || `HTTP ${resp.status}`);
      }

      const data = (await resp.json()) as PostResult;
      setPostResult(data);
      setPhase("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Post failed");
      setPhase("preview");
    }
  }

  function handleReset() {
    setUrl("");
    setScrapeResult(null);
    setTweetText("");
    setPostResult(null);
    setError("");
    setPhase("input");
  }

  // ── Auth gate ──
  if (!authed) {
    return (
      <div className="auth-card">
        <h2 className="auth-title">Dashboard Login</h2>
        <div className="auth-form">
          <input
            type="password"
            placeholder="Enter dashboard password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            className="input"
          />
          <button onClick={handleLogin} className="btn btn-primary">
            Login
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
      </div>
    );
  }

  return (
    <div className="dashboard-content">
      <PostingControls password={password} />
      <KeywordManager password={password} />

      {/* URL Input */}
      {(phase === "input" || phase === "preview" || phase === "done") && phase !== "done" && (
        <div className="form-card">
          <div className="form-row">
            <input
              type="url"
              placeholder="Paste article URL..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !scraping && handleScrape()}
              className="input input-url"
              disabled={scraping || phase === "preview"}
            />
            {phase === "input" && (
              <button
                onClick={handleScrape}
                className="btn btn-primary"
                disabled={scraping || !url.trim()}
              >
                {scraping ? "Scraping..." : "Scrape"}
              </button>
            )}
            {phase === "preview" && (
              <button onClick={handleReset} className="btn btn-secondary">
                Clear
              </button>
            )}
          </div>
          {error && phase === "input" && <p className="form-error">{error}</p>}
        </div>
      )}

      {/* Preview */}
      {phase === "preview" && scrapeResult && (
        <div className="preview-card">
          <div className="preview-meta">
            <span className="preview-source">{scrapeResult.source}</span>
          </div>

          {scrapeResult.ogImage && (
            <div className="preview-image-wrap">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={scrapeResult.ogImage}
                alt=""
                className="preview-image"
              />
            </div>
          )}

          <h3 className="preview-title">{scrapeResult.title}</h3>
          {scrapeResult.snippet && (
            <p className="preview-snippet">{scrapeResult.snippet}</p>
          )}

          <div className="tweet-edit">
            <label className="tweet-label">
              Tweet Preview
              <span className={`tweet-counter ${tweetText.length > 280 ? "tweet-counter-over" : ""}`}>
                {tweetText.length}/280
              </span>
            </label>
            <textarea
              value={tweetText}
              onChange={(e) => setTweetText(e.target.value)}
              className="textarea"
              rows={4}
              maxLength={290}
            />
          </div>

          {error && <p className="form-error">{error}</p>}

          <button
            onClick={handlePost}
            className="btn btn-primary btn-full"
            disabled={!tweetText.trim() || tweetText.length > 280}
          >
            Post to X & Telegram
          </button>
        </div>
      )}

      {/* Posting spinner */}
      {phase === "posting" && (
        <div className="posting-state">
          <div className="spinner" />
          <p>Posting to X & Telegram...</p>
        </div>
      )}

      {/* Done */}
      {phase === "done" && postResult && (
        <div className="result-card">
          <h3 className="result-title">Posted!</h3>

          <div className="result-item">
            <span className={`result-badge ${postResult.xResult.success ? "result-success" : "result-fail"}`}>
              X {postResult.xResult.success ? "✓" : "✗"}
            </span>
            {postResult.xResult.success && postResult.xResult.tweetUrl && (
              <a
                href={postResult.xResult.tweetUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="result-link"
              >
                View tweet →
              </a>
            )}
            {!postResult.xResult.success && (
              <span className="result-error">{postResult.xResult.error}</span>
            )}
          </div>

          <div className="result-item">
            <span className={`result-badge ${postResult.telegramResult.success ? "result-success" : "result-fail"}`}>
              Telegram {postResult.telegramResult.success ? "✓" : "✗"}
            </span>
            {!postResult.telegramResult.success && (
              <span className="result-error">{postResult.telegramResult.error}</span>
            )}
          </div>

          <div className="result-item">
            <span className={`result-badge ${postResult.feedUpdated ? "result-success" : "result-fail"}`}>
              Feed {postResult.feedUpdated ? "✓" : "✗"}
            </span>
          </div>

          <button onClick={handleReset} className="btn btn-primary btn-full" style={{ marginTop: 16 }}>
            Post Another
          </button>
        </div>
      )}
    </div>
  );
}
