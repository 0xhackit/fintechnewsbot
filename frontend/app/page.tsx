import { getFeed } from "@/lib/feed";
import Edition from "@/components/Edition";

export default async function HomePage() {
  const feed = await getFeed();

  return <Edition initialEntries={feed.entries} updatedAt={feed.updated_at} />;
}
