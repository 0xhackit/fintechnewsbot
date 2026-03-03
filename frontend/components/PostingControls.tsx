"use client";

import { useState, useEffect, useCallback } from "react";

interface PostingStatus {
  post_to_x: boolean;
  post_to_telegram: boolean;
  auto_approve: boolean;
  trade_analysis_x: boolean;
  trade_analysis_telegram: boolean;
}

export default function PostingControls({ password }: { password: string }) {
  const [status, setStatus] = useState<PostingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);
  const [error, setError] = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch("/api/posting-status", {
        headers: { Authorization: `Bearer ${password}` },
      });
      if (!resp.ok) throw new Error("Failed to fetch");
      const data = (await resp.json()) as PostingStatus;
      setStatus(data);
      setError("");
    } catch {
      setError("Failed to load posting status");
    } finally {
      setLoading(false);
    }
  }, [password]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  async function toggleX() {
    if (!status || toggling) return;
    const newVal = !status.post_to_x;

    if (status.post_to_x && !confirm("Stop X posting? This takes effect within 5 minutes.")) {
      return;
    }

    setToggling("x");
    try {
      const resp = await fetch("/api/posting-status", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${password}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ post_to_x: newVal }),
      });
      if (!resp.ok) throw new Error("Failed to update");
      const data = (await resp.json()) as PostingStatus;
      setStatus(data);
    } catch {
      setError("Failed to toggle X posting");
    } finally {
      setToggling(null);
    }
  }

  async function toggleAll() {
    if (!status || toggling) return;
    const currentlyActive = status.post_to_x || status.post_to_telegram;
    const newVal = !currentlyActive;

    if (currentlyActive && !confirm("Stop ALL posting (X + Telegram)? This takes effect within 5 minutes.")) {
      return;
    }

    setToggling("all");
    try {
      const resp = await fetch("/api/posting-status", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${password}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          post_to_x: newVal,
          post_to_telegram: newVal,
        }),
      });
      if (!resp.ok) throw new Error("Failed to update");
      const data = (await resp.json()) as PostingStatus;
      setStatus(data);
    } catch {
      setError("Failed to toggle posting");
    } finally {
      setToggling(null);
    }
  }

  async function toggleAnalysis(platform: "x" | "telegram") {
    if (!status || toggling) return;
    const key = platform === "x" ? "trade_analysis_x" : "trade_analysis_telegram";
    const newVal = !status[key];

    setToggling(`analysis_${platform}`);
    try {
      const resp = await fetch("/api/posting-status", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${password}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ [key]: newVal }),
      });
      if (!resp.ok) throw new Error("Failed to update");
      const data = (await resp.json()) as PostingStatus;
      setStatus(data);
    } catch {
      setError("Failed to toggle trade analysis");
    } finally {
      setToggling(null);
    }
  }

  if (loading) {
    return (
      <div className="controls-card">
        <div className="controls-header">Posting Controls</div>
        <p className="controls-loading">Loading status...</p>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="controls-card">
        <div className="controls-header">
          <span>Posting Controls</span>
          <span className="status-dot" style={{ background: "#cfd9de" }} />
        </div>
        <p className="controls-error">{error || "Unable to load status"}</p>
        <div className="controls-row">
          <div className="control-item">
            <div className="control-label">
              <span className="status-dot-sm" style={{ background: "#cfd9de" }} />
              X Posting
            </div>
            <button className="toggle-btn toggle-paused" disabled>--</button>
          </div>
          <div className="control-item">
            <div className="control-label">
              <span className="status-dot-sm" style={{ background: "#cfd9de" }} />
              All Posting
            </div>
            <button className="toggle-btn toggle-paused" disabled>--</button>
          </div>
        </div>
      </div>
    );
  }

  const allPaused = !status.post_to_x && !status.post_to_telegram;

  return (
    <div className="controls-card">
      <div className="controls-header">
        <span>Posting Controls</span>
        <span className={`status-dot ${allPaused ? "status-dot-red" : "status-dot-green"}`} />
      </div>

      {error && <p className="controls-error">{error}</p>}

      <div className="controls-row">
        <div className="control-item">
          <div className="control-label">
            <span className={`status-dot-sm ${status.post_to_x ? "status-dot-green" : "status-dot-red"}`} />
            X Posting
          </div>
          <button
            className={`toggle-btn ${status.post_to_x ? "toggle-active" : "toggle-paused"}`}
            onClick={toggleX}
            disabled={!!toggling || allPaused}
            title={allPaused ? "Enable All Posting first" : ""}
          >
            {toggling === "x" ? "..." : status.post_to_x ? "Active" : "Paused"}
          </button>
        </div>

        <div className="control-item">
          <div className="control-label">
            <span className={`status-dot-sm ${allPaused ? "status-dot-red" : "status-dot-green"}`} />
            All Posting
          </div>
          <button
            className={`toggle-btn ${allPaused ? "toggle-paused" : "toggle-active"}`}
            onClick={toggleAll}
            disabled={!!toggling}
          >
            {toggling === "all" ? "..." : allPaused ? "Paused" : "Active"}
          </button>
        </div>
      </div>

      <div className="controls-section-label">Trade Analysis Replies</div>
      <div className="controls-row">
        <div className="control-item">
          <div className="control-label">
            <span className={`status-dot-sm ${status.trade_analysis_x ? "status-dot-green" : "status-dot-red"}`} />
            Analysis on X
          </div>
          <button
            className={`toggle-btn ${status.trade_analysis_x ? "toggle-active" : "toggle-paused"}`}
            onClick={() => toggleAnalysis("x")}
            disabled={!!toggling}
          >
            {toggling === "analysis_x" ? "..." : status.trade_analysis_x ? "Active" : "Paused"}
          </button>
        </div>

        <div className="control-item">
          <div className="control-label">
            <span className={`status-dot-sm ${status.trade_analysis_telegram ? "status-dot-green" : "status-dot-red"}`} />
            Analysis on TG
          </div>
          <button
            className={`toggle-btn ${status.trade_analysis_telegram ? "toggle-active" : "toggle-paused"}`}
            onClick={() => toggleAnalysis("telegram")}
            disabled={!!toggling}
          >
            {toggling === "analysis_telegram" ? "..." : status.trade_analysis_telegram ? "Active" : "Paused"}
          </button>
        </div>
      </div>
    </div>
  );
}
