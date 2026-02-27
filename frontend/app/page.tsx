import { getFeed, getWeeklyHighlights } from "@/lib/feed";
import PostItem from "@/components/PostItem";
import WeeklyHighlights from "@/components/WeeklyHighlights";

export default async function HomePage() {
  const feed = await getFeed();
  const entries = feed.entries;
  const highlights = getWeeklyHighlights(entries);

  return (
    <main className="feed">
      <WeeklyHighlights highlights={highlights} />

      <div className="section-divider">
        <h2 className="section-title">Latest News</h2>
      </div>

      {entries.length === 0 ? (
        <div className="empty-state">
          <p>No articles yet</p>
          <p>The feed updates every 5 minutes.</p>
        </div>
      ) : (
        <div className="news-feed">
          {entries.map((entry) => (
            <PostItem key={entry.id} entry={entry} />
          ))}
        </div>
      )}
    </main>
  );
}
