import type { Category } from "./categories";

export interface FeedEntry {
  id: string;
  title: string;
  link: string;
  snippet: string;
  score: number;
  matched_topics: string[];
  ai_category?: string;
  ai_priority?: string;
  /** Site section, stamped by src/categorize.py. See lib/categories.ts. */
  category?: Category;
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
  // v2 metadata surfaced on the public feed cards (absent on pre-v2 entries).
  regions?: string[];
  primary_region?: string | null;
  coins?: string[];
  origin?: string; // rss | tree | rss+tree (consensus)
  source_tier?: string;
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
