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

const STOPWORDS = new Set([
  "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
  "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
  "has", "have", "had", "do", "does", "did", "will", "would", "could",
  "should", "may", "might", "its", "it", "this", "that", "as", "not",
]);

function tokenize(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((w) => w.length > 1 && !STOPWORDS.has(w))
  );
}

function jaccardSimilarity(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 1;
  let intersection = 0;
  for (const token of a) {
    if (b.has(token)) intersection++;
  }
  const union = a.size + b.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

/** Top articles from the past 7 days, ranked by score, deduped by Jaccard similarity */
export function getWeeklyHighlights(
  entries: FeedEntry[],
  limit: number = 5
): FeedEntry[] {
  const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const selected: { entry: FeedEntry; tokens: Set<string> }[] = [];

  const candidates = entries
    .filter((e) => new Date(e.posted_at).getTime() >= sevenDaysAgo)
    .sort((a, b) => b.score - a.score);

  for (const entry of candidates) {
    if (selected.length >= limit) break;

    const tokens = tokenize(entry.title);
    const isDuplicate = selected.some(
      (s) => jaccardSimilarity(tokens, s.tokens) > 0.35
    );

    if (!isDuplicate) {
      selected.push({ entry, tokens });
    }
  }

  return selected.map((s) => s.entry);
}
