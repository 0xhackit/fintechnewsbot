/**
 * broadsheet.ts — shapes the flat feed into the "edition" model the
 * Broadsheet layout renders (lead · brief · desks · wire).
 *
 * Pure and isomorphic: runs on the server (page.tsx) for the first paint and
 * again in the client (Edition.tsx) after each 5-minute refresh. It reads only
 * `FeedEntry` fields the pipeline already writes; the editorial slots that the
 * $0-LLM pipeline can't produce (a rewritten "consequence" line, the lead's
 * "read it for", real multi-publisher clusters) degrade to honest, derived
 * values rather than being faked. See DATA-PIPELINE.md §3/§5 for the backend
 * work that would light those up fully.
 */

import type { FeedEntry } from "./feed";
import { resolveCategory, type Category } from "./categories";

export type DeskKey = "regulation" | "fundraising" | "product";

export interface Story {
  id: string;
  title: string;
  deck: string; // one-sentence standfirst; "" when we have nothing better than the title
  url: string;
  source: string;
  sources: number; // cluster size (>= 1). 2 when RSS + TreeOfAlpha corroborate.
  filedBy: string[]; // channels that carried it
  category: Category;
  section: DeskKey | null; // null = "other" → wire-only, no desk column
  sectionLabel: string; // kicker text, e.g. "Regulation & Policy"
  publishedAt: number; // ms epoch, for sorting
  time: string; // HH:MM, wire gutter (reader locale)
  score: number;
  origin: string; // rss | tree | rss+tree
  isConsensus: boolean; // origin === "rss+tree"
  coins: string[];
  regions: string[];
  postedToX: boolean;
  tweetUrl: string | null;
  dayKey: string; // UTC calendar day (YYYY-MM-DD), drives the wire date separators
  dayLabel: string; // "Monday, August 24" (UTC), shown as a wire day heading
}

export interface Desk {
  key: DeskKey;
  name: string;
  note: string; // per-column aggregate computed at edition time
  stories: Story[];
}

export interface BriefLine {
  n: string;
  text: string;
  id: string;
}

export interface Edition {
  lead: Story | null;
  brief: BriefLine[];
  briefLabel: string; // "The top three from yesterday" — reflects what the brief holds
  desks: Desk[];
  wire: Story[];
  updatedAt: string;
  dateline: string; // "Thursday, August 20, 2026"
  partOfDay: string; // Morning | Afternoon | Evening
  editionNo: number;
  storyCount: number;
  sourceCount: number;
}

// ── Section mapping: my four categories → the design's three desks ─────────────
// The mockup also has an "Institutions" section, but the pipeline has no such
// classifier — it has "other". So "other" is wire-only (curated columns stay
// clean, the Wire still shows everything), and the lead kicker just reads the
// story's own desk label.

const DESK_DEFS: { key: DeskKey; category: Category; name: string }[] = [
  { key: "regulation", category: "regulation", name: "Regulation & Policy" },
  { key: "fundraising", category: "fundraising", name: "Funding & Deals" },
  { key: "product", category: "product", name: "Rails & Product" },
];

const SECTION_LABEL: Record<Category, string> = {
  regulation: "Regulation & Policy",
  fundraising: "Funding & Deals",
  product: "Rails & Product",
  other: "Markets",
};

const DESK_OF: Partial<Record<Category, DeskKey>> = {
  regulation: "regulation",
  fundraising: "fundraising",
  product: "product",
};

// ── Source naming (ported + extended from PostItem) ────────────────────────────

const KNOWN_SOURCES: Record<string, string> = {
  theblock: "The Block",
  coindesk: "CoinDesk",
  cointelegraph: "CoinTelegraph",
  decrypt: "Decrypt",
  blockworks: "Blockworks",
  dlnews: "DL News",
  finextra: "Finextra",
  pymnts: "PYMNTS",
  fintechfutures: "Fintech Futures",
  ledger_insights: "Ledger Insights",
  techcrunch_fintech: "TechCrunch",
  ft_markets: "Financial Times",
  ft_fintech: "Financial Times",
  wsj_markets: "WSJ",
  stripe_blog: "Stripe",
};

const DOMAIN_NAMES: Record<string, string> = {
  "news.google.com": "Google News",
  "coindesk.com": "CoinDesk",
  "cointelegraph.com": "CoinTelegraph",
  "theblock.co": "The Block",
  "decrypt.co": "Decrypt",
  "blockworks.co": "Blockworks",
  "dlnews.com": "DL News",
  "finextra.com": "Finextra",
  "pymnts.com": "PYMNTS",
  "fintechfutures.com": "Fintech Futures",
  "ledgerinsights.com": "Ledger Insights",
  "techcrunch.com": "TechCrunch",
  "ft.com": "Financial Times",
  "wsj.com": "WSJ",
  "stripe.com": "Stripe",
  "sifted.eu": "Sifted",
  "reuters.com": "Reuters",
  "bloomberg.com": "Bloomberg",
};

const TREE_NAMES: Record<string, string> = {
  "the block": "The Block",
  coindesk: "CoinDesk",
  cointelegraph: "CoinTelegraph",
  bloomberg: "Bloomberg",
  reuters: "Reuters",
  wsj: "WSJ",
  ft: "Financial Times",
  "the information": "The Information",
};

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Loose normalisation for comparing a title against a snippet. */
function norm(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

// Social/relay hosts are never a useful "source" name — a TreeOfAlpha item that
// links to x.com is still The Block/Bloomberg/etc. under the hood, not "x.com".
const SOCIAL_HOSTS = new Set(["x.com", "twitter.com", "t.co", "mobile.twitter.com"]);

function sourceFromUrl(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (SOCIAL_HOSTS.has(host)) return "";
    if (DOMAIN_NAMES[host]) return DOMAIN_NAMES[host];
    return host;
  } catch {
    return "";
  }
}

/** Publisher named in a "PUBLISHER: headline" tree title, if we recognise it. */
function sourceFromTitlePrefix(title: string): string {
  const m = /^([A-Za-z][A-Za-z .&']{2,28}?):\s/.exec(title || "");
  if (!m) return "";
  const key = m[1].trim().toLowerCase();
  return TREE_NAMES[key] || KNOWN_SOURCES[key.replace(/\s+/g, "")] || "";
}

/** Human-readable publisher name for a feed entry. */
export function displaySource(e: FeedEntry): string {
  const feedName = e.feed_name || "";
  // TreeOfAlpha items carry feed_name like "tree:the block".
  if (feedName.startsWith("tree:")) {
    const raw = feedName.slice(5).trim().toLowerCase();
    if (TREE_NAMES[raw]) return TREE_NAMES[raw];
    const byUrl = sourceFromUrl(e.link || "");
    if (byUrl) return byUrl;
    const byPrefix = sourceFromTitlePrefix(e.title || "");
    if (byPrefix) return byPrefix;
    return raw ? titleCase(raw) : "TreeOfAlpha";
  }
  if (feedName && KNOWN_SOURCES[feedName]) return KNOWN_SOURCES[feedName];
  const byUrl = sourceFromUrl(e.link || "");
  if (byUrl) return byUrl;
  const byPrefix = sourceFromTitlePrefix(e.title || "");
  if (byPrefix) return byPrefix;
  const src = e.source || "";
  if (src.startsWith("TreeOfAlpha")) return "TreeOfAlpha";
  if (src && src !== "Google News RSS") return src;
  return "Wire";
}

// ── Money parsing for the Funding desk note ────────────────────────────────────

/** Sum of disclosed amounts in a set of titles, in millions. 0 if none found. */
function disclosedMillions(titles: string[]): number {
  let total = 0;
  const re = /[$€£]\s?(\d+(?:\.\d+)?)\s?(k|m|mn|million|bn|billion)?/gi;
  for (const t of titles) {
    let m: RegExpExecArray | null;
    re.lastIndex = 0;
    while ((m = re.exec(t)) !== null) {
      const n = parseFloat(m[1]);
      const unit = (m[2] || "").toLowerCase();
      if (unit.startsWith("b")) total += n * 1000;
      else if (unit === "k") total += n / 1000;
      else if (unit.startsWith("m")) total += n;
      // bare number with no unit → ignore (too ambiguous to sum)
    }
  }
  return Math.round(total);
}

function fmtMillions(m: number): string {
  if (m >= 1000) {
    const bn = m / 1000;
    return `$${bn % 1 === 0 ? bn.toFixed(0) : bn.toFixed(1)}bn`;
  }
  return `$${m}m`;
}

// ── Time helpers (locale-formatted, pure) ──────────────────────────────────────

// UTC so the wire time agrees with the UTC date separators (a story filed at
// 21:34 UTC reads as "21:34" under its "August 21" heading, not a skewed local
// time under the wrong day) — and so SSR and client always match.
function hhmm(ms: number): string {
  if (!ms) return "";
  const d = new Date(ms);
  return d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });
}

// ── Recency + day grouping (UTC, so server and client agree — no hydration drift)

/** UTC calendar day, e.g. "2026-08-24". Stable across SSR/client. */
function utcDayKey(ms: number): string {
  if (!ms) return "undated";
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(
    d.getUTCDate()
  ).padStart(2, "0")}`;
}

/** Absolute day heading, e.g. "Monday, August 24" (UTC). */
function utcDayLabel(ms: number): string {
  if (!ms) return "Undated";
  return new Date(ms).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

// Pure market/price recaps ("$BTC climbed to…", "holdings are back above…", "ETF
// inflow") are wire filler — never a lead or a brief headline. Applied only to the
// "other" bucket; a desk-mapped story (Regulation/Funding/Rails) is always eligible.
function isMarketRecap(s: Story): boolean {
  const t = (s.title || "").toLowerCase();
  return (
    /\b(climbs?|surges?|approaches|hovers?|dips?|rall(?:y|ies|ied)|jumps?|slips?|soars?|trades?\s+around|back\s+above)\b[^.]*\$?\d/.test(
      t
    ) ||
    /\bholdings?\s+(?:are|is)\s+back\b/.test(t) ||
    /\b(?:unrealized\s+(?:profit|loss)|net\s+(?:in|out)flows?|(?:etf|fund)\s+(?:in|out)flows?)\b/.test(
      t
    )
  );
}

/** Highest-scoring story in the tightest recency window that has any — so a fresh
 *  but slightly lower-scored story wins the slot over a stale high-scorer. */
function pickFreshTop(pool: Story[], refMs: number): Story | null {
  if (!pool.length) return null;
  for (const days of [1, 2, 4, 8, 3650]) {
    const cut = refMs - days * DAY_MS;
    const inWin = pool.filter((s) => s.publishedAt >= cut);
    if (inWin.length) {
      return [...inWin].sort(
        (a, b) => b.score - a.score || b.publishedAt - a.publishedAt
      )[0];
    }
  }
  return pool[0];
}

// ── Shaping ────────────────────────────────────────────────────────────────────

function toStory(e: FeedEntry): Story {
  const category = resolveCategory(e);
  const publishedAt = Date.parse(e.published_at || e.posted_at || "") || 0;
  const source = displaySource(e);
  const isConsensus = e.origin === "rss+tree";
  const sources = isConsensus ? 2 : 1;

  const filedBy: string[] = [source];
  if (isConsensus && source !== "TreeOfAlpha") filedBy.push("TreeOfAlpha");

  // deck = the standfirst; drop it when it just echoes the title (feeds often set
  // the snippet to "<title> <source>" — no new information to show under it).
  const rawDeck = (e.snippet || "").trim();
  const nt = norm(e.title || "");
  const nd = norm(rawDeck);
  const deck = nd && nd !== nt && !nt.includes(nd) && !nd.includes(nt) ? rawDeck : "";

  return {
    id: e.id,
    title: e.title,
    deck,
    url: e.link,
    source,
    sources,
    filedBy,
    category,
    section: DESK_OF[category] ?? null,
    sectionLabel: SECTION_LABEL[category],
    publishedAt,
    time: hhmm(publishedAt),
    dayKey: utcDayKey(publishedAt),
    dayLabel: utcDayLabel(publishedAt),
    score: e.score ?? 0,
    origin: e.origin || "rss",
    isConsensus,
    coins: (e.coins || []).filter(Boolean),
    regions: (e.regions || []).filter(Boolean),
    postedToX: Boolean(e.posted_to_x),
    tweetUrl:
      e.tweet_url && e.tweet_url.startsWith("https://x.com/") ? e.tweet_url : null,
  };
}

function deskNote(key: DeskKey, stories: Story[]): string {
  const n = stories.length;
  if (n === 0) return "Quiet so far";
  if (key === "fundraising") {
    const m = disclosedMillions(stories.map((s) => s.title + " " + s.deck));
    if (m > 0) return `${fmtMillions(m)} disclosed today`;
    return `${n} ${n === 1 ? "deal" : "deals"} filed`;
  }
  if (key === "regulation") {
    const regions = new Set(stories.flatMap((s) => s.regions));
    const jur = regions.size;
    return jur > 1
      ? `${n} ${n === 1 ? "filing" : "filings"}, ${jur} jurisdictions`
      : `${n} ${n === 1 ? "filing" : "filings"}`;
  }
  // product
  return `${n} ${n === 1 ? "update" : "updates"} on the rails`;
}

const DAY_MS = 24 * 60 * 60 * 1000;
const EDITION_EPOCH = Date.UTC(2025, 0, 1); // Jan 1, 2025 — sets Edition No. 1's date.

/** Turn the raw feed into a dated edition. `ref` overrides "now" for stable SSR. */
export function shapeEdition(entries: FeedEntry[], updatedAt: string): Edition {
  const stories = entries.map(toStory).filter((s) => s.title && s.url);

  const newest = [...stories].sort(
    (a, b) => b.publishedAt - a.publishedAt || b.score - a.score
  );

  const updatedMs = Date.parse(updatedAt) || newest[0]?.publishedAt || 0;

  // ── Lead: the most important story of the *freshest* day that carries news, so
  //    a new filing takes the top slot instead of a high-scoring week-old story.
  //    Price-wrap "other" dumps stay in the Wire; desk-mapped stories always count.
  const leadPool = newest.filter(
    (s) => s.section !== null || (s.category === "other" && !isMarketRecap(s))
  );
  const lead = pickFreshTop(leadPool, updatedMs) ?? newest[0] ?? null;

  // ── Sixty-second brief: the top three from the day before — a fixed "what you
  //    missed yesterday" recap that rolls over each morning. The feed is sparse,
  //    so when yesterday was quiet we backfill with the most recent earlier
  //    stories (never today's — those belong to the lead and the desks).
  const briefEligible = leadPool.filter((s) => s.id !== lead?.id);
  const todayKey = utcDayKey(updatedMs);
  const yesterdayKey = utcDayKey(updatedMs - DAY_MS);
  const yesterday = briefEligible
    .filter((s) => s.dayKey === yesterdayKey)
    .sort((a, b) => b.score - a.score || b.publishedAt - a.publishedAt);
  const hadYesterday = yesterday.length > 0;
  const briefStories = [...yesterday];
  if (briefStories.length < 3) {
    const chosen = new Set(briefStories.map((s) => s.id));
    const backfill = briefEligible
      .filter(
        (s) => !chosen.has(s.id) && s.dayKey !== todayKey && s.publishedAt < updatedMs
      )
      .sort((a, b) => b.publishedAt - a.publishedAt || b.score - a.score);
    for (const s of backfill) {
      if (briefStories.length >= 3) break;
      briefStories.push(s);
    }
  }
  const brief: BriefLine[] = briefStories.slice(0, 3).map((s, i) => ({
    n: String(i + 1).padStart(2, "0"),
    text: s.deck || s.title,
    id: s.id,
  }));
  const briefLabel = hadYesterday
    ? "The top three from yesterday"
    : "The biggest stories you may have missed";

  // ── Desks: per-section, NEWEST first — a story surfaces at the top of its
  //    category the moment it is filed. The lead is pulled out of its column.
  const desks: Desk[] = DESK_DEFS.map(({ key, category, name }) => {
    const inSection = newest.filter(
      (s) => s.category === category && s.id !== lead?.id
    );
    return {
      key,
      name,
      note: deskNote(key, inSection),
      stories: inSection.slice(0, 5),
    };
  });

  // Wire = everything, newest first (Story.dayKey drives the date separators).
  const wire = newest;

  const dateline = updatedMs
    ? new Date(updatedMs).toLocaleDateString("en-US", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "";
  const hour = updatedMs ? new Date(updatedMs).getHours() : 9;
  const partOfDay = hour < 12 ? "Morning" : hour < 18 ? "Afternoon" : "Evening";
  const editionNo = updatedMs
    ? Math.max(1, Math.floor((updatedMs - EDITION_EPOCH) / DAY_MS))
    : 1;
  const sourceCount = new Set(stories.map((s) => s.source)).size;

  return {
    lead,
    brief,
    briefLabel,
    desks,
    wire,
    updatedAt,
    dateline,
    partOfDay,
    editionNo,
    storyCount: stories.length,
    sourceCount,
  };
}
