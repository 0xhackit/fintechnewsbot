import { FeedEntry } from "@/lib/feed";

function relativeTime(isoString: string): string {
  if (!isoString) return "";
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;
  if (diffMs < 0) return "just now";
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m`;
  if (diffHr < 24) return `${diffHr}h`;
  return `${diffDay}d`;
}

/** Known feed_name → display name */
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

/** Well-known domains → clean display names */
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
};

/** Extract a clean source name from a URL */
function sourceFromUrl(url: string): string {
  try {
    const hostname = new URL(url).hostname.replace(/^www\./, "");
    if (DOMAIN_NAMES[hostname]) return DOMAIN_NAMES[hostname];
    return hostname;
  } catch {
    return "";
  }
}

/** Resolve a human-readable source name */
function displaySource(feedName: string, source: string, link: string): string {
  // 1. Known feed name
  if (feedName && KNOWN_SOURCES[feedName]) return KNOWN_SOURCES[feedName];
  // 2. Extract source from article URL
  if (link) {
    const name = sourceFromUrl(link);
    if (name) return name;
  }
  // 3. Last resort
  if (source && source !== "Google News RSS") return source;
  return "";
}

export default function PostItem({ entry }: { entry: FeedEntry }) {
  const source = displaySource(entry.feed_name || "", entry.source || "", entry.link || "");
  const hasRealTweet = entry.tweet_url && entry.tweet_url.startsWith("https://x.com/");

  return (
    <article className="post-item">
      <div className="post-content">
        <a href={entry.link} target="_blank" rel="noopener noreferrer" className="post-title-link">
          <h3 className="post-title">{entry.title}</h3>
        </a>
        {entry.snippet && (
          <p className="post-snippet">{entry.snippet}</p>
        )}
        <div className="post-meta">
          {source && <span className="post-source">{source}</span>}
          {source && <span className="post-meta-dot">&middot;</span>}
          <span className="post-time">{relativeTime(entry.posted_at)}</span>
          {hasRealTweet && (
            <a
              href={entry.tweet_url!}
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
  );
}
