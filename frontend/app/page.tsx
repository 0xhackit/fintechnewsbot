import { getFeed } from "@/lib/feed";
import FeedTabs from "@/components/FeedTabs";

export default async function HomePage() {
  const feed = await getFeed();

  return (
    <main className="feed">
      <FeedTabs initialEntries={feed.entries} updatedAt={feed.updated_at} />
    </main>
  );
}
