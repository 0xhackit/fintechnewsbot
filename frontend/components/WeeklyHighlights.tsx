import { FeedEntry } from "@/lib/feed";

export default function WeeklyHighlights({
  highlights,
}: {
  highlights: FeedEntry[];
}) {
  if (highlights.length === 0) return null;

  return (
    <section className="highlights">
      <div className="highlights-header">
        <svg className="highlights-icon" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
          <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
        </svg>
        <h2 className="highlights-heading">Weekly Highlights</h2>
      </div>
      <ol className="highlights-list">
        {highlights.map((entry, i) => (
          <li key={entry.id} className="highlights-item">
            <span className="highlights-rank">{i + 1}</span>
            <span className="highlights-title">{entry.title}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
