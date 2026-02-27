import { FeedEntry, getPostLink } from "@/lib/feed";

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

/** Map feed_name slugs to display names */
function displaySource(feedName: string, source: string): string {
  const names: Record<string, string> = {
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
  if (feedName && names[feedName]) return names[feedName];
  if (feedName) return feedName;
  if (source) return source;
  return "";
}

export default function PostItem({ entry }: { entry: FeedEntry }) {
  const href = getPostLink(entry);
  const source = displaySource(entry.feed_name || "", entry.source || "");

  return (
    <article className="post-item">
      <div className="post-content">
        <a href={href} target="_blank" rel="noopener noreferrer" className="post-title-link">
          <h3 className="post-title">{entry.title}</h3>
        </a>
        {entry.snippet && (
          <p className="post-snippet">{entry.snippet}</p>
        )}
        <div className="post-meta">
          {source && (
            <a
              href={entry.link}
              target="_blank"
              rel="noopener noreferrer"
              className="post-source-link"
            >
              {source}
            </a>
          )}
          {source && <span className="post-meta-dot">&middot;</span>}
          <span className="post-time">{relativeTime(entry.posted_at)}</span>
          {entry.posted_to_x && entry.tweet_url && (
            <a
              href={entry.tweet_url}
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
