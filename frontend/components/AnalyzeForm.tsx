"use client";

import { useState, useEffect, useCallback, useRef } from "react";

// ── Types matching API responses ──

interface TimeframeData {
  direction: "LONG" | "SHORT" | "NEUTRAL";
  confidence: number;
  timeHorizon: string;
  targetPrice: number | null;
  stopLoss?: number | null;
  rationale: string;
  exposureMethods: string[];
}

interface AnalysisResult {
  article: {
    title: string;
    snippet: string;
    ogImage: string | null;
    source: string;
    url: string;
  };
  analysis: {
    ticker: string;
    assetType: string;
    summary: string;
    shortTerm: TimeframeData;
    longTerm: TimeframeData;
    riskFactors: string[];
    catalysts: string[];
  };
  price: {
    price: number | null;
    currency: string;
    change24h: number | null;
    source: string;
  };
  id: string;
}

interface TrackRecordEntry {
  id: string;
  ticker: string;
  assetType: string;
  analyzedAt: string;
  entryPrice: number | null;
  summary: string;
  shortTerm: { direction: string; confidence: number };
  longTerm: { direction: string; confidence: number };
  currentPrice: number | null;
  pnlPercent: number | null;
  shortTermResult: "win" | "loss" | "pending";
  longTermResult: "win" | "loss" | "pending";
}

interface TrackRecordStats {
  total: number;
  shortTermWins: number;
  shortTermLosses: number;
  shortTermPending: number;
  longTermWins: number;
  longTermLosses: number;
  longTermPending: number;
  shortTermAccuracy: number | null;
  longTermAccuracy: number | null;
}

// ── Helpers ──

function formatPrice(price: number | null, currency = "USD"): string {
  if (price == null) return "—";
  if (price >= 1) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(price);
  }
  // Small tokens: show more decimals
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(price);
}

function formatChange(change: number | null): string {
  if (change == null) return "";
  const sign = change >= 0 ? "+" : "";
  return `${sign}${change.toFixed(2)}%`;
}

function directionArrow(d: string): string {
  if (d === "LONG") return "\u25B2";
  if (d === "SHORT") return "\u25BC";
  return "\u2014";
}

function directionClass(d: string): string {
  if (d === "LONG") return "direction-long";
  if (d === "SHORT") return "direction-short";
  return "direction-neutral";
}

function confidenceLevel(c: number): string {
  if (c >= 7) return "high";
  if (c >= 4) return "mid";
  return "low";
}

// ── Loading steps ──

const LOADING_STEPS = [
  "Scraping article content...",
  "Running AI analysis...",
  "Fetching live price data...",
  "Generating recommendation...",
];

// ── Component ──

type Phase = "input" | "loading" | "result" | "error";

export default function AnalyzeForm() {
  const [phase, setPhase] = useState<Phase>("input");
  const [url, setUrl] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");
  const [loadingStep, setLoadingStep] = useState(0);
  const [copied, setCopied] = useState(false);

  // Track record
  const [trackEntries, setTrackEntries] = useState<TrackRecordEntry[]>([]);
  const [trackStats, setTrackStats] = useState<TrackRecordStats | null>(null);
  const [trackLoading, setTrackLoading] = useState(true);

  const loadingTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Load track record on mount ──

  const loadTrackRecord = useCallback(async () => {
    try {
      const resp = await fetch("/api/analyze/history");
      if (!resp.ok) throw new Error("Failed");
      const data = (await resp.json()) as {
        analyses: TrackRecordEntry[];
        stats: TrackRecordStats;
      };
      setTrackEntries(data.analyses || []);
      setTrackStats(data.stats || null);
    } catch {
      // Silently fail — track record is supplementary
    } finally {
      setTrackLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTrackRecord();
  }, [loadTrackRecord]);

  // ── Pre-fill from URL query param ──

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const prefill = params.get("url");
    if (prefill) {
      setUrl(prefill);
    }
  }, []);

  // ── Loading step animation ──

  useEffect(() => {
    if (phase === "loading") {
      setLoadingStep(0);
      loadingTimer.current = setInterval(() => {
        setLoadingStep((prev) =>
          prev < LOADING_STEPS.length - 1 ? prev + 1 : prev
        );
      }, 2000);
    } else {
      if (loadingTimer.current) {
        clearInterval(loadingTimer.current);
        loadingTimer.current = null;
      }
    }
    return () => {
      if (loadingTimer.current) clearInterval(loadingTimer.current);
    };
  }, [phase]);

  // ── Analyze handler ──

  async function handleAnalyze() {
    const trimmed = url.trim();
    if (!trimmed) return;

    if (
      !trimmed.startsWith("http://") &&
      !trimmed.startsWith("https://")
    ) {
      setError("Please enter a valid URL starting with http:// or https://");
      setPhase("error");
      return;
    }

    setPhase("loading");
    setError("");

    try {
      const resp = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmed }),
      });

      const data = await resp.json();

      if (!resp.ok) {
        throw new Error(
          data.error || `Analysis failed (${resp.status})`
        );
      }

      setResult(data as AnalysisResult);
      setPhase("result");

      // Refresh track record
      loadTrackRecord();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong"
      );
      setPhase("error");
    }
  }

  function handleReset() {
    setPhase("input");
    setUrl("");
    setResult(null);
    setError("");
    setCopied(false);
  }

  function handleCopyLink() {
    if (!result) return;
    const shareUrl = `${window.location.origin}/analyze?url=${encodeURIComponent(result.article.url)}`;
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  // ── Render: Input Phase ──

  function renderInput() {
    return (
      <>
        <div className="form-card">
          <div className="form-row">
            <input
              type="url"
              className="input input-url"
              placeholder="Paste article URL..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleAnalyze();
              }}
            />
            <button
              className="btn btn-primary"
              onClick={handleAnalyze}
              disabled={!url.trim()}
            >
              Analyze
            </button>
          </div>
        </div>
        <div className="disclaimer">
          This tool provides AI-generated analysis for educational purposes only.
          Not financial advice. Always do your own research before making
          investment decisions.
        </div>
      </>
    );
  }

  // ── Render: Loading Phase ──

  function renderLoading() {
    return (
      <div className="loading-steps">
        <div className="spinner" />
        {LOADING_STEPS.map((step, i) => (
          <div
            key={step}
            className={`loading-step ${
              i < loadingStep
                ? "loading-step-done"
                : i === loadingStep
                  ? "loading-step-active"
                  : ""
            }`}
          >
            {i < loadingStep ? "\u2713 " : ""}
            {step}
          </div>
        ))}
      </div>
    );
  }

  // ── Render: Error Phase ──

  function renderError() {
    return (
      <div className="form-card" style={{ textAlign: "center", padding: 32 }}>
        <p style={{ color: "#f4212e", fontWeight: 600, marginBottom: 12 }}>
          {error}
        </p>
        <button className="btn btn-primary" onClick={handleReset}>
          Try Again
        </button>
      </div>
    );
  }

  // ── Render: Timeframe Card ──

  function renderTimeframe(
    label: string,
    icon: string,
    data: TimeframeData
  ) {
    return (
      <div className="analysis-timeframe">
        <div className="timeframe-header">
          <div className="timeframe-title">
            <span>{icon}</span> {label}
            <span className="timeframe-horizon">{data.timeHorizon}</span>
          </div>
          <span
            className={`timeframe-direction ${directionClass(data.direction)}`}
          >
            {directionArrow(data.direction)} {data.direction}
          </span>
        </div>

        <div className="confidence-bar">
          <span className="confidence-label">
            Confidence: {data.confidence}/10
          </span>
          <div className="confidence-track">
            <div
              className={`confidence-fill confidence-fill-${confidenceLevel(data.confidence)}`}
              style={{ width: `${data.confidence * 10}%` }}
            />
          </div>
        </div>

        <p className="timeframe-rationale">{data.rationale}</p>

        {(data.targetPrice != null || data.stopLoss != null) && (
          <div className="timeframe-targets">
            {data.targetPrice != null && (
              <div className="target-item">
                <div className="target-label">Target</div>
                <div className="target-value target-value-green">
                  {formatPrice(data.targetPrice)}
                </div>
              </div>
            )}
            {data.stopLoss != null && (
              <div className="target-item">
                <div className="target-label">Stop Loss</div>
                <div className="target-value target-value-red">
                  {formatPrice(data.stopLoss)}
                </div>
              </div>
            )}
          </div>
        )}

        {data.exposureMethods.length > 0 && (
          <div>
            <div className="exposure-label">How to trade:</div>
            <div className="exposure-methods">
              {data.exposureMethods.map((m) => (
                <span key={m} className="exposure-pill">
                  {m}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Render: Result Phase ──

  function renderResult() {
    if (!result) return null;
    const { article, analysis, price } = result;

    // Use short-term direction as the "primary" direction
    const primaryDirection = analysis.shortTerm.direction;
    const primaryConfidence = analysis.shortTerm.confidence;

    return (
      <>
        {/* Article preview */}
        <div className="analysis-article">
          {article.ogImage && (
            <img
              src={article.ogImage}
              alt=""
              className="analysis-article-image"
            />
          )}
          <div className="analysis-article-body">
            <div className="analysis-article-title">{article.title}</div>
            <div className="analysis-article-source">
              {article.source}
            </div>
          </div>
        </div>

        {/* Direction hero */}
        <div className="analysis-direction">
          <span
            className={`direction-badge ${directionClass(primaryDirection)}`}
          >
            {directionArrow(primaryDirection)} {primaryDirection}
          </span>
          <div className="analysis-ticker">${analysis.ticker}</div>
          {price.price != null && (
            <div className="analysis-price">
              {formatPrice(price.price, price.currency)}
              {price.change24h != null && (
                <span
                  className={`analysis-price-change ${
                    price.change24h >= 0
                      ? "price-change-up"
                      : "price-change-down"
                  }`}
                >
                  {formatChange(price.change24h)}
                </span>
              )}
            </div>
          )}
          <div className="confidence-bar">
            <span className="confidence-label">
              Confidence: {primaryConfidence}/10
            </span>
            <div className="confidence-track">
              <div
                className={`confidence-fill confidence-fill-${confidenceLevel(primaryConfidence)}`}
                style={{ width: `${primaryConfidence * 10}%` }}
              />
            </div>
          </div>
        </div>

        {/* Summary callout */}
        {analysis.summary && (
          <div className="analysis-summary">{analysis.summary}</div>
        )}

        {/* Short-term */}
        {renderTimeframe(
          "Short-Term Trade",
          "\u26A1",
          analysis.shortTerm
        )}

        {/* Long-term */}
        {renderTimeframe(
          "Long-Term Investment",
          "\uD83D\uDCC8",
          analysis.longTerm
        )}

        {/* Risk factors */}
        {analysis.riskFactors.length > 0 && (
          <div className="analysis-list-card">
            <div className="analysis-list-title">
              <span className="list-icon">\u26A0\uFE0F</span> Risk Factors
            </div>
            <ul className="analysis-list">
              {analysis.riskFactors.map((r) => (
                <li key={r}>
                  <span className="list-icon">\u2022</span>
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Catalysts */}
        {analysis.catalysts.length > 0 && (
          <div className="analysis-list-card">
            <div className="analysis-list-title">
              <span className="list-icon">\uD83D\uDD25</span> Catalysts
            </div>
            <ul className="analysis-list">
              {analysis.catalysts.map((c) => (
                <li key={c}>
                  <span className="list-icon">\u2022</span>
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="analysis-actions">
          <button className="btn btn-primary" onClick={handleReset}>
            Analyze Another
          </button>
          <button
            className={`btn ${copied ? "btn-copy-done" : "btn-copy"}`}
            onClick={handleCopyLink}
          >
            {copied ? "Copied!" : "Copy Link"}
          </button>
        </div>

        {/* Disclaimer */}
        <div className="disclaimer">
          This analysis is AI-generated and not financial advice. Always do your
          own research before making investment decisions. Past performance does
          not guarantee future results.
        </div>
      </>
    );
  }

  // ── Render: Track Record ──

  function renderTrackRecord() {
    if (trackLoading) return null;

    // Show even if empty (shows "No analyses yet" state)
    return (
      <div className="track-record">
        <div className="track-record-header">
          <span className="track-record-title">Track Record</span>
          {trackStats && trackStats.total > 0 && (
            <span className="track-record-count">
              {trackStats.total} analyses
            </span>
          )}
        </div>

        {trackStats &&
          (trackStats.shortTermAccuracy !== null ||
            trackStats.longTermAccuracy !== null) && (
            <div className="track-record-stats">
              {trackStats.shortTermAccuracy !== null && (
                <div className="track-stat">
                  <div className="track-stat-value track-stat-value-green">
                    {trackStats.shortTermAccuracy}%
                  </div>
                  <div className="track-stat-label">Short-term</div>
                </div>
              )}
              {trackStats.longTermAccuracy !== null && (
                <div className="track-stat">
                  <div className="track-stat-value track-stat-value-green">
                    {trackStats.longTermAccuracy}%
                  </div>
                  <div className="track-stat-label">Long-term</div>
                </div>
              )}
              <div className="track-stat">
                <div className="track-stat-value">{trackStats.total}</div>
                <div className="track-stat-label">Total</div>
              </div>
            </div>
          )}

        {trackEntries.length === 0 ? (
          <div className="track-empty">
            No analyses yet. Paste an article URL above to get started.
          </div>
        ) : (
          trackEntries.slice(0, 5).map((entry) => (
            <div key={entry.id} className="track-record-row">
              <span className="track-ticker">{entry.ticker}</span>
              <span
                className={`track-direction ${directionClass(entry.shortTerm.direction)}`}
              >
                {entry.shortTerm.direction}
              </span>
              <span
                className={`result-badge ${
                  entry.shortTermResult === "win"
                    ? "result-success"
                    : entry.shortTermResult === "loss"
                      ? "result-fail"
                      : ""
                }`}
              >
                {entry.shortTermResult === "win"
                  ? "Win"
                  : entry.shortTermResult === "loss"
                    ? "Loss"
                    : "Pending"}
              </span>
              <span
                className={`track-pnl ${
                  entry.pnlPercent != null && entry.pnlPercent >= 0
                    ? "track-pnl-positive"
                    : "track-pnl-negative"
                }`}
              >
                {entry.pnlPercent != null
                  ? `${entry.pnlPercent >= 0 ? "+" : ""}${entry.pnlPercent.toFixed(1)}%`
                  : "—"}
              </span>
            </div>
          ))
        )}
      </div>
    );
  }

  // ── Main render ──

  return (
    <div className="dashboard-content">
      {phase === "input" && renderInput()}
      {phase === "loading" && renderLoading()}
      {phase === "error" && renderError()}
      {phase === "result" && renderResult()}
      {renderTrackRecord()}
    </div>
  );
}
