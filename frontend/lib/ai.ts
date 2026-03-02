/**
 * Claude AI wrappers for tweet generation and trade analysis.
 * Ports the tweet generation logic from publish_x.py to TypeScript.
 */

import Anthropic from "@anthropic-ai/sdk";

// ── Company @handle mapping ──

const COMPANY_HANDLES: Record<string, string> = {
  coinbase: "@coinbase",
  stripe: "@stripe",
  circle: "@circle",
  ripple: "@Ripple",
  paypal: "@PayPal",
  visa: "@Visa",
  mastercard: "@Mastercard",
  jpmorgan: "@jpmorgan",
  "jp morgan": "@jpmorgan",
  blackrock: "@BlackRock",
  fidelity: "@Fidelity",
  revolut: "@RevolutApp",
  plaid: "@PlaidDev",
  robinhood: "@RobinhoodApp",
  kraken: "@kaboracle",
  binance: "@binance",
  gemini: "@Gemini",
  square: "@Square",
  block: "@blocks",
  wise: "@wise",
  klarna: "@Klarna",
  affirm: "@Affirm",
  sofi: "@SoFi",
  brex: "@brex",
  ubs: "@UBS",
  hsbc: "@HSBC",
  "goldman sachs": "@GoldmanSachs",
  goldman: "@GoldmanSachs",
  "morgan stanley": "@MorganStanley",
  "deutsche bank": "@DeutscheBank",
  barclays: "@Barclays",
  "standard chartered": "@StanChart",
  citi: "@Citi",
  citigroup: "@Citi",
  "bnp paribas": "@BNPParibas",
  "societe generale": "@SocieteGenerale",
  "bank of america": "@BankofAmerica",
  "wells fargo": "@WellsFargo",
  "state street": "@StateStreet",
  "bny mellon": "@BNYMellon",
  "franklin templeton": "@FTI_US",
  anchorage: "@Anchorage",
  paxos: "@PaxosGlobal",
  bitstamp: "@Bitstamp",
  bybit: "@Bybit_Official",
  okx: "@okx",
  tether: "@Tether_to",
};

const ALL_STYLES = [
  "TRADFI_BRIDGE",
  "EXPLAINER",
  "IMPACT",
  "QUESTION",
  "STAT_LED",
  "CONTRARIAN",
] as const;

type TweetStyle = (typeof ALL_STYLES)[number] | "UNKNOWN";

export interface TweetResult {
  text: string;
  styleUsed: TweetStyle;
}

export interface TradeAnalysis {
  ticker: string;
  assetType: string;
  direction: "LONG" | "SHORT" | "NEUTRAL";
  confidence: number;
  fundamentalAnalysis: string;
  technicalContext: string;
  exposureMethods: string[];
  riskFactors: string[];
  timeHorizon: string;
}

// ── Enhanced Trade Analysis (short-term + long-term split) ──

export interface TimeframeAnalysis {
  direction: "LONG" | "SHORT" | "NEUTRAL";
  confidence: number;
  timeHorizon: string;
  targetPrice: number | null;
  stopLoss?: number | null;
  rationale: string;
  exposureMethods: string[];
}

export interface EnhancedTradeAnalysis {
  ticker: string;
  assetType: "crypto" | "stock" | "etf" | "token" | "unknown";
  summary: string;
  shortTerm: TimeframeAnalysis;
  longTerm: TimeframeAnalysis;
  riskFactors: string[];
  catalysts: string[];
}

// ── Tweet Generation ──

/**
 * Build @handles hint from title text.
 */
function getRelevantHandles(title: string): string[] {
  const lower = title.toLowerCase();
  const handles: string[] = [];
  for (const [company, handle] of Object.entries(COMPANY_HANDLES)) {
    if (lower.includes(company) && !handles.includes(handle)) {
      handles.push(handle);
    }
  }
  return handles.slice(0, 3);
}

/**
 * Generate an AI-enhanced tweet using Claude Haiku.
 * Ports _generate_ai_tweet() from publish_x.py.
 */
export async function generateTweet(
  title: string,
  snippet: string
): Promise<TweetResult> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    // Fail-open: return title-only tweet
    return { text: title.slice(0, 270), styleUsed: "UNKNOWN" };
  }

  const handles = getRelevantHandles(title);
  const handlesHint = handles.length
    ? `\nRelevant company @handles you SHOULD use: ${handles.join(", ")}`
    : "";

  const prompt = `You are a fintech news editor writing a tweet for a professional audience.

Given this article:
TITLE: ${title}
SNIPPET: ${snippet ? snippet.slice(0, 300) : "(none)"}

This is a MEDIUM-PRIORITY story. Use an insightful, analytical hook. Do NOT use BREAKING: prefix.

Write a single tweet using EXACTLY ONE of these styles:
- TRADFI_BRIDGE: Connect this news to a traditional finance concept
- EXPLAINER: Briefly explain the tech/product for someone outside crypto
- IMPACT: State the concrete implication for the industry
- QUESTION: Open with a compelling rhetorical question
- STAT_LED: Lead with a number or statistic from the article
- CONTRARIAN: Offer a "most people miss this" angle

Rules:
1. Use company @handles where natural${handlesHint}
2. Do NOT include any article link or URL
3. NO hashtags. NO emojis. Professional, factual tone.
4. TOTAL tweet MUST be under 270 characters (count carefully)
5. On the LAST line of your response, write: STYLE_USED: <style_name>

Return the tweet text followed by the STYLE_USED line. Nothing else.`;

  try {
    const client = new Anthropic({ apiKey });
    const message = await client.messages.create({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 200,
      messages: [{ role: "user", content: prompt }],
    });

    const raw =
      message.content[0].type === "text" ? message.content[0].text.trim() : "";

    // Parse STYLE_USED from last line
    let styleUsed: TweetStyle = "UNKNOWN";
    const tweetLines: string[] = [];

    for (const line of raw.split("\n")) {
      if (line.trim().toUpperCase().startsWith("STYLE_USED:")) {
        const parsed = line
          .split(":")[1]
          .trim()
          .toUpperCase()
          .replace(/\s+/g, "_");
        if ((ALL_STYLES as readonly string[]).includes(parsed)) {
          styleUsed = parsed as TweetStyle;
        }
      } else {
        tweetLines.push(line);
      }
    }

    let tweet = tweetLines.join("\n").trim();

    // Strip quotes the model may wrap it in
    if (tweet.startsWith('"') && tweet.endsWith('"')) {
      tweet = tweet.slice(1, -1);
    }
    if (tweet.startsWith("'") && tweet.endsWith("'")) {
      tweet = tweet.slice(1, -1);
    }

    // Remove any URLs the model may have added
    tweet = tweet.replace(/https?:\/\/\S+/g, "").trim();

    // Validate length
    if (tweet.length > 280) {
      return { text: title.slice(0, 270), styleUsed: "UNKNOWN" };
    }
    if (tweet.length < 20) {
      return { text: title.slice(0, 270), styleUsed: "UNKNOWN" };
    }

    return { text: tweet, styleUsed };
  } catch {
    // Fail-open: return title-only tweet
    return { text: title.slice(0, 270), styleUsed: "UNKNOWN" };
  }
}

// ── Trade Analysis ──

/**
 * Analyze an article and generate a trade recommendation.
 */
export async function analyzeArticle(
  title: string,
  content: string,
  url: string
): Promise<TradeAnalysis> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error("Missing ANTHROPIC_API_KEY");
  }

  const prompt = `You are a senior financial analyst specializing in fintech, crypto, and digital assets.

Analyze this article and provide a structured trade recommendation.

TITLE: ${title}
URL: ${url}
CONTENT: ${content.slice(0, 4000)}

Respond with ONLY valid JSON (no markdown, no backticks) in this exact format:
{
  "ticker": "TICKER_SYMBOL",
  "asset_type": "stock|crypto|etf|token",
  "direction": "LONG|SHORT|NEUTRAL",
  "confidence": 1-10,
  "fundamental_analysis": "2-3 sentences on fundamentals",
  "technical_context": "1-2 sentences on market context",
  "exposure_methods": ["method 1", "method 2", "method 3"],
  "risk_factors": ["risk 1", "risk 2", "risk 3"],
  "time_horizon": "short-term (days)|medium-term (weeks)|long-term (months)"
}

Guidelines:
- Use the most relevant publicly traded ticker or crypto token
- Be specific about exposure methods (spot, options, ETFs, etc.)
- Confidence 1-3 = low conviction, 4-6 = moderate, 7-10 = high conviction
- If the article doesn't clearly suggest a trade, use "NEUTRAL" direction
- Focus on actionable insights, not generic advice`;

  const client = new Anthropic({ apiKey });
  const message = await client.messages.create({
    model: "claude-haiku-4-5-20251001",
    max_tokens: 500,
    messages: [{ role: "user", content: prompt }],
  });

  const raw =
    message.content[0].type === "text" ? message.content[0].text.trim() : "";

  // Parse JSON — strip any markdown code fences if present
  const cleaned = raw.replace(/```json?\n?/g, "").replace(/```/g, "").trim();

  const data = JSON.parse(cleaned) as {
    ticker?: string;
    asset_type?: string;
    direction?: string;
    confidence?: number;
    fundamental_analysis?: string;
    technical_context?: string;
    exposure_methods?: string[];
    risk_factors?: string[];
    time_horizon?: string;
  };

  return {
    ticker: data.ticker || "N/A",
    assetType: data.asset_type || "unknown",
    direction: (["LONG", "SHORT", "NEUTRAL"].includes(
      (data.direction || "").toUpperCase()
    )
      ? (data.direction!.toUpperCase() as "LONG" | "SHORT" | "NEUTRAL")
      : "NEUTRAL"),
    confidence: Math.min(10, Math.max(1, data.confidence || 5)),
    fundamentalAnalysis: data.fundamental_analysis || "",
    technicalContext: data.technical_context || "",
    exposureMethods: data.exposure_methods || [],
    riskFactors: data.risk_factors || [],
    timeHorizon: data.time_horizon || "medium-term (weeks)",
  };
}

// ── Enhanced Trade Analysis (with short-term / long-term split) ──

function parseDirection(d: string | undefined): "LONG" | "SHORT" | "NEUTRAL" {
  const upper = (d || "").toUpperCase();
  if (upper === "LONG" || upper === "SHORT" || upper === "NEUTRAL") return upper;
  return "NEUTRAL";
}

function clampConfidence(n: number | undefined): number {
  return Math.min(10, Math.max(1, n || 5));
}

/**
 * Enhanced article analysis with separate short-term and long-term recommendations.
 * Returns structured data for the /analyze page.
 */
export async function analyzeArticleEnhanced(
  title: string,
  content: string,
  url: string
): Promise<EnhancedTradeAnalysis> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error("Missing ANTHROPIC_API_KEY");
  }

  const prompt = `You are a senior financial analyst at a top hedge fund, specializing in fintech, crypto, and digital assets. You provide actionable trade recommendations based on news analysis.

Analyze this article and provide SEPARATE short-term and long-term trade recommendations.

TITLE: ${title}
URL: ${url}
CONTENT: ${content.slice(0, 4000)}

Respond with ONLY valid JSON (no markdown, no backticks) in this exact format:
{
  "ticker": "TICKER_SYMBOL",
  "asset_type": "crypto|stock|etf|token",
  "summary": "One compelling sentence summarizing the trade thesis (under 120 chars)",
  "short_term": {
    "direction": "LONG|SHORT|NEUTRAL",
    "confidence": 1-10,
    "time_horizon": "1-3 days|3-7 days|1-2 weeks",
    "target_price": 00000,
    "stop_loss": 00000,
    "rationale": "2-3 sentences on the short-term trade thesis",
    "exposure_methods": ["specific method 1", "specific method 2"]
  },
  "long_term": {
    "direction": "LONG|SHORT|NEUTRAL",
    "confidence": 1-10,
    "time_horizon": "1-3 months|3-6 months|6-12 months",
    "target_price": 00000,
    "rationale": "2-3 sentences on the long-term investment thesis",
    "exposure_methods": ["specific method 1", "specific method 2"]
  },
  "risk_factors": ["specific risk 1", "specific risk 2", "specific risk 3"],
  "catalysts": ["upcoming catalyst 1", "upcoming catalyst 2"]
}

Guidelines:
- Use the most relevant publicly traded ticker or crypto token symbol (e.g. BTC, ETH, COIN, MSTR)
- Short-term and long-term CAN have DIFFERENT directions (e.g. short-term SHORT but long-term LONG)
- Confidence 1-3 = low conviction, 4-6 = moderate, 7-10 = high conviction
- For target_price and stop_loss: use realistic numeric values based on current market levels. Use null if not applicable.
- Exposure methods must be SPECIFIC:
  - Crypto short-term: "spot BTC on Coinbase", "BTC perpetual futures (2-3x)", "BTC weekly options"
  - Crypto long-term: "dollar-cost average spot BTC", "IBIT ETF", "MSTR stock as BTC proxy"
  - Stock short-term: "buy COIN shares", "COIN call options (30 DTE)", "short via put spreads"
  - Stock long-term: "accumulate on dips", "covered call strategy", "sector ETF (ARKF)"
- Risk factors must be SPECIFIC to this news, not generic
- Catalysts must be CONCRETE upcoming events (earnings dates, protocol upgrades, regulatory deadlines, etc.)
- If the article doesn't clearly suggest a trade, use "NEUTRAL" for both timeframes
- Summary should be punchy and shareable — think Twitter-style insight`;

  const client = new Anthropic({ apiKey });
  const message = await client.messages.create({
    model: "claude-haiku-4-5-20251001",
    max_tokens: 800,
    messages: [{ role: "user", content: prompt }],
  });

  const raw =
    message.content[0].type === "text" ? message.content[0].text.trim() : "";

  // Parse JSON — strip any markdown code fences if present
  const cleaned = raw.replace(/```json?\n?/g, "").replace(/```/g, "").trim();

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const data = JSON.parse(cleaned) as Record<string, any>;
  const st = data.short_term || {};
  const lt = data.long_term || {};

  const validAssetTypes = ["crypto", "stock", "etf", "token"];
  const assetType = validAssetTypes.includes((data.asset_type || "").toLowerCase())
    ? (data.asset_type.toLowerCase() as "crypto" | "stock" | "etf" | "token")
    : "unknown" as const;

  return {
    ticker: (data.ticker || "N/A").toUpperCase(),
    assetType,
    summary: data.summary || "",
    shortTerm: {
      direction: parseDirection(st.direction),
      confidence: clampConfidence(st.confidence),
      timeHorizon: st.time_horizon || "1-3 days",
      targetPrice: typeof st.target_price === "number" ? st.target_price : null,
      stopLoss: typeof st.stop_loss === "number" ? st.stop_loss : null,
      rationale: st.rationale || "",
      exposureMethods: Array.isArray(st.exposure_methods) ? st.exposure_methods : [],
    },
    longTerm: {
      direction: parseDirection(lt.direction),
      confidence: clampConfidence(lt.confidence),
      timeHorizon: lt.time_horizon || "1-3 months",
      targetPrice: typeof lt.target_price === "number" ? lt.target_price : null,
      rationale: lt.rationale || "",
      exposureMethods: Array.isArray(lt.exposure_methods) ? lt.exposure_methods : [],
    },
    riskFactors: Array.isArray(data.risk_factors) ? data.risk_factors : [],
    catalysts: Array.isArray(data.catalysts) ? data.catalysts : [],
  };
}
