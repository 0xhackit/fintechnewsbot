import { getFeed, getWeeklyHighlights } from "@/lib/feed";
import FeedTabs from "@/components/FeedTabs";

export default async function HomePage() {
  const feed = await getFeed();
  const entries = feed.entries;
  const highlights = getWeeklyHighlights(entries);

  return (
    <main className="feed">
      <FeedTabs
        initialEntries={entries}
        initialHighlights={highlights}
        updatedAt={feed.updated_at}
      />
    </main>
  );
}
