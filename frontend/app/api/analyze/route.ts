/**
 * POST /api/analyze — Public AI trade analysis endpoint.
 * Scrapes article → AI analysis → price fetch → persist to GitHub.
 * Rate-limited: 5 requests/hr per IP.
 */

import { NextRequest, NextResponse } from "next/server";
import { createHash } from "crypto";
import { scrapeUrl } from "@/lib/scraper";
import { analyzeArticleEnhanced, type EnhancedTradeAnalysis } from "@/lib/ai";
import { fetchPrice, type PriceResult } from "@/lib/price";
import { getFileFromGitHub, putFileToGitHub } from "@/lib/github";

// ── Rate limiter (in-memory, resets on deploy) ──

const rateLimiter = new Map<string, number[]>();
const RATE_LIMIT = 5;
const RATE_WINDOW_MS = 60 * 60 * 1000; // 1 hour

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const timestamps = (rateLimiter.get(ip) || []).filter(
    (t) => now - t < RATE_WINDOW_MS
  );
  if (timestamps.length >= RATE_LIMIT) {
    rateLimiter.set(ip, timestamps);
    return false;
  }
  timestamps.push(now);
  rateLimiter.set(ip, timestamps);
  return true;
}

function getClientIp(req: NextRequest): string {
  return (
    req.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
    req.headers.get("x-real-ip") ||
    "unknown"
  );
}

// ── Response type ──

export interface AnalysisResponse {
  article: {
    title: string;
    snippet: string;
    ogImage: string | null;
    source: string;
    url: string;
  };
  analysis: EnhancedTradeAnalysis;
  price: PriceResult;
  id: string;
}

// ── Persistence (fire-and-forget) ──

interface AnalysisRecord {
  id: string;
  url: string;
  title: string;
  source: string;
  ticker: string;
  assetType: string;
  analyzedAt: string;
  entryPrice: number | null;
  summary: string;
  shortTerm: EnhancedTradeAnalysis["shortTerm"];
  longTerm: EnhancedTradeAnalysis["longTerm"];
  riskFactors: string[];
  catalysts: string[];
}

interface AnalysisHistoryFile {
  version: number;
  updatedAt: string;
  analyses: AnalysisRecord[];
}

// Normalize URL for dedup comparison (strip protocol, www, query, fragment)
function normalizeUrlForDedup(url: string): string {
  return (url || "")
    .replace(/^https?:\/\/(www\.)?/, "")
    .split("?")[0]
    .split("#")[0]
    .toLowerCase()
    .replace(/\/+$/, "");
}

// Simple word-overlap Jaccard for title dedup
function titleJaccard(a: string, b: string): number {
  const normalize = (t: string) =>
    t.toLowerCase().replace(/\s+[-|]\s+[^-]{2,60}$/g, "")
      .replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
  const wordsA = new Set(normalize(a).split(" ").filter((w) => w.length > 2));
  const wordsB = new Set(normalize(b).split(" ").filter((w) => w.length > 2));
  const intersection = [...wordsA].filter((w) => wordsB.has(w)).length;
  const union = new Set([...wordsA, ...wordsB]).size;
  return union > 0 ? intersection / union : 0;
}

async function saveAnalysis(
  record: AnalysisRecord
): Promise<void> {
  try {
    let file: { content: string; sha: string };
    let history: AnalysisHistoryFile;

    try {
      file = await getFileFromGitHub("out/analysis_history.json");
      history = JSON.parse(file.content) as AnalysisHistoryFile;
    } catch {
      // File doesn't exist yet — create initial structure
      // We need to create it; use a dummy sha for creation
      history = { version: 1, updatedAt: "", analyses: [] };
      file = { content: "", sha: "" };
    }

    // Dedup: skip if same URL or very similar title analyzed within 72 hours
    const cutoff72h = Date.now() - 72 * 60 * 60 * 1000;
    const recordUrlNorm = normalizeUrlForDedup(record.url);
    const isDuplicate = history.analyses.some((a) => {
      const aTime = new Date(a.analyzedAt).getTime();
      if (aTime < cutoff72h) return false;

      // URL match (normalized)
      if (normalizeUrlForDedup(a.url) === recordUrlNorm) return true;

      // Title similarity (Jaccard word overlap >= 0.50)
      if (a.title && record.title && titleJaccard(a.title, record.title) >= 0.50)
        return true;

      return false;
    });

    if (isDuplicate) {
      console.log(
        `Analysis dedup: skipping save for "${record.title?.substring(0, 60)}" (already analyzed within 72h)`
      );
      return;
    }

    // Append and prune
    history.analyses.unshift(record);
    if (history.analyses.length > 200) {
      history.analyses = history.analyses.slice(0, 200);
    }
    history.updatedAt = new Date().toISOString();

    const content = JSON.stringify(history, null, 2);

    if (file.sha) {
      await putFileToGitHub(
        "out/analysis_history.json",
        content,
        file.sha,
        `chore: analysis — ${record.ticker} ${record.shortTerm.direction}`
      );
    } else {
      // Create new file via GitHub API
      const token = process.env.GITHUB_TOKEN;
      if (!token) return;

      await fetch(
        "https://api.github.com/repos/0xhackit/fintechnewsbot/contents/out/analysis_history.json",
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: `chore: create analysis history — ${record.ticker}`,
            content: Buffer.from(content).toString("base64"),
          }),
        }
      );
    }
  } catch (err) {
    console.error("Failed to save analysis:", err);
    // Fire-and-forget — don't block the response
  }
}

// ── Handler ──

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export async function POST(req: NextRequest) {
  // ── Feature disabled ──
  return NextResponse.json(
    { error: "AI Trade Analysis is temporarily disabled." },
    { status: 503 }
  );
}
