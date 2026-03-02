/**
 * GET /api/analyze/history — Track record endpoint.
 * Returns past analyses with lazy-computed P&L from live prices.
 */

import { NextResponse } from "next/server";
import { getFileFromGitHub } from "@/lib/github";
import { fetchMultiplePrices } from "@/lib/price";

// ── Types ──

interface StoredAnalysis {
  id: string;
  url: string;
  title: string;
  source: string;
  ticker: string;
  assetType: string;
  analyzedAt: string;
  entryPrice: number | null;
  summary: string;
  shortTerm: {
    direction: "LONG" | "SHORT" | "NEUTRAL";
    confidence: number;
    timeHorizon: string;
    targetPrice: number | null;
    stopLoss?: number | null;
    rationale: string;
    exposureMethods: string[];
  };
  longTerm: {
    direction: "LONG" | "SHORT" | "NEUTRAL";
    confidence: number;
    timeHorizon: string;
    targetPrice: number | null;
    rationale: string;
    exposureMethods: string[];
  };
  riskFactors: string[];
  catalysts: string[];
}

interface AnalysisWithTracking extends StoredAnalysis {
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

/**
 * Parse a time horizon string like "1-3 days" or "1-3 months" into milliseconds.
 * Uses the upper bound for evaluation (e.g., "1-3 days" → 3 days).
 */
function parseTimeHorizonMs(horizon: string): number {
  const lower = horizon.toLowerCase();

  // Extract the last number before the unit
  const nums = lower.match(/(\d+)/g);
  const lastNum = nums ? parseInt(nums[nums.length - 1], 10) : 0;

  if (lower.includes("day")) return lastNum * 24 * 60 * 60 * 1000;
  if (lower.includes("week")) return lastNum * 7 * 24 * 60 * 60 * 1000;
  if (lower.includes("month")) return lastNum * 30 * 24 * 60 * 60 * 1000;

  // Default: 7 days for short-term-ish, 90 days for long-term-ish
  return 7 * 24 * 60 * 60 * 1000;
}

function evaluateResult(
  direction: "LONG" | "SHORT" | "NEUTRAL",
  entryPrice: number | null,
  currentPrice: number | null,
  analyzedAt: string,
  timeHorizon: string
): { result: "win" | "loss" | "pending"; pnl: number | null } {
  if (direction === "NEUTRAL" || entryPrice == null || currentPrice == null) {
    return { result: "pending", pnl: null };
  }

  const elapsed = Date.now() - new Date(analyzedAt).getTime();
  const horizonMs = parseTimeHorizonMs(timeHorizon);

  // Only evaluate if enough time has passed (at least 50% of horizon)
  if (elapsed < horizonMs * 0.5) {
    return { result: "pending", pnl: null };
  }

  let pnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100;
  // For SHORT: profit when price goes down
  if (direction === "SHORT") pnlPercent = -pnlPercent;

  // Win: > 2%, Loss: < -2%, otherwise pending
  if (pnlPercent > 2) return { result: "win", pnl: pnlPercent };
  if (pnlPercent < -2) return { result: "loss", pnl: pnlPercent };
  return { result: "pending", pnl: pnlPercent };
}

// ── Handler ──

export async function GET() {
  try {
    // 1. Load history from GitHub
    let analyses: StoredAnalysis[] = [];

    try {
      const file = await getFileFromGitHub("out/analysis_history.json");
      const history = JSON.parse(file.content) as {
        analyses?: StoredAnalysis[];
      };
      analyses = history.analyses || [];
    } catch {
      // File doesn't exist yet — return empty
      return NextResponse.json({
        analyses: [],
        stats: {
          total: 0,
          shortTermWins: 0,
          shortTermLosses: 0,
          shortTermPending: 0,
          longTermWins: 0,
          longTermLosses: 0,
          longTermPending: 0,
          shortTermAccuracy: null,
          longTermAccuracy: null,
        },
      });
    }

    // 2. Collect unique tickers for batch price fetch
    const tickerSet = new Map<string, string>();
    for (const a of analyses) {
      if (a.ticker && a.entryPrice != null) {
        tickerSet.set(a.ticker.toUpperCase(), a.assetType || "unknown");
      }
    }

    const tickers = Array.from(tickerSet.entries()).map(
      ([ticker, assetType]) => ({ ticker, assetType })
    );

    // 3. Batch fetch current prices
    const prices =
      tickers.length > 0 ? await fetchMultiplePrices(tickers) : {};

    // 4. Compute tracking for each analysis
    const tracked: AnalysisWithTracking[] = analyses
      .slice(0, 20)
      .map((a) => {
        const currentPrice =
          prices[a.ticker?.toUpperCase()]?.price ?? null;

        const shortEval = evaluateResult(
          a.shortTerm?.direction || "NEUTRAL",
          a.entryPrice,
          currentPrice,
          a.analyzedAt,
          a.shortTerm?.timeHorizon || "1-3 days"
        );

        const longEval = evaluateResult(
          a.longTerm?.direction || "NEUTRAL",
          a.entryPrice,
          currentPrice,
          a.analyzedAt,
          a.longTerm?.timeHorizon || "1-3 months"
        );

        return {
          ...a,
          currentPrice,
          pnlPercent: shortEval.pnl,
          shortTermResult: shortEval.result,
          longTermResult: longEval.result,
        };
      });

    // 5. Compute aggregate stats (over ALL analyses, not just top 20)
    let stWins = 0,
      stLosses = 0,
      stPending = 0;
    let ltWins = 0,
      ltLosses = 0,
      ltPending = 0;

    for (const a of analyses) {
      const currentPrice =
        prices[a.ticker?.toUpperCase()]?.price ?? null;

      const st = evaluateResult(
        a.shortTerm?.direction || "NEUTRAL",
        a.entryPrice,
        currentPrice,
        a.analyzedAt,
        a.shortTerm?.timeHorizon || "1-3 days"
      );
      const lt = evaluateResult(
        a.longTerm?.direction || "NEUTRAL",
        a.entryPrice,
        currentPrice,
        a.analyzedAt,
        a.longTerm?.timeHorizon || "1-3 months"
      );

      if (st.result === "win") stWins++;
      else if (st.result === "loss") stLosses++;
      else stPending++;

      if (lt.result === "win") ltWins++;
      else if (lt.result === "loss") ltLosses++;
      else ltPending++;
    }

    const stResolved = stWins + stLosses;
    const ltResolved = ltWins + ltLosses;

    const stats: TrackRecordStats = {
      total: analyses.length,
      shortTermWins: stWins,
      shortTermLosses: stLosses,
      shortTermPending: stPending,
      longTermWins: ltWins,
      longTermLosses: ltLosses,
      longTermPending: ltPending,
      shortTermAccuracy:
        stResolved > 0
          ? Math.round((stWins / stResolved) * 100)
          : null,
      longTermAccuracy:
        ltResolved > 0
          ? Math.round((ltWins / ltResolved) * 100)
          : null,
    };

    return NextResponse.json({ analyses: tracked, stats });
  } catch (err) {
    console.error("History error:", err);
    return NextResponse.json(
      { error: "Failed to load track record" },
      { status: 500 }
    );
  }
}
