export interface FeedEntry {
  id: string;
  title: string;
  link: string;
  snippet: string;
  score: number;
  matched_topics: string[];
  ai_category?: string;
  ai_priority?: string;
  posted_at: string;
  source?: string;
  feed_name?: string;
  published_at?: string;
  posted_to_telegram: boolean;
  telegram_message_id?: number | null;
  posted_to_x: boolean;
  tweet_id?: string | null;
  tweet_text?: string | null;
  tweet_url?: string | null;
}

export interface Feed {
  updated_at: string;
  entries: FeedEntry[];
}

const PROD_FEED_URL =
  "https://raw.githubusercontent.com/0xhackit/fintechnewsbot/main/out/feed.json";

function getFeedUrl(): string {
  // In development, use the local API route that reads from ../out/feed.json
  if (process.env.NODE_ENV === "development") {
    return "http://localhost:3000/api/feed";
  }
  return PROD_FEED_URL;
}

export async function getFeed(): Promise<Feed> {
  const url = getFeedUrl();
  const res = await fetch(url, {
    next: { revalidate: 300 },
  });

  if (!res.ok) {
    console.error(`Feed fetch failed: ${res.status}`);
    return { updated_at: "", entries: [] };
  }

  return res.json();
}

/** Top articles from the past 7 days, ranked by score, deduped by title */
export function getWeeklyHighlights(
  entries: FeedEntry[],
  limit: number = 5
): FeedEntry[] {
  const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const seen = new Set<string>();

  return entries
    .filter((e) => {
      const ts = new Date(e.posted_at).getTime();
      if (ts < sevenDaysAgo) return false;
      // Dedupe by normalized title
      const key = e.title.toLowerCase().trim();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}
