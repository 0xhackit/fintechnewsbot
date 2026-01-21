import React from 'react';
import { formatDistanceToNow, format } from 'date-fns';

function LiveStream({ items }) {
  const formatTime = (dateString) => {
    try {
      const date = new Date(dateString);
      return format(date, 'HH:mm');
    } catch {
      return '--:--';
    }
  };

  const getTimeAgo = (dateString) => {
    try {
      const date = new Date(dateString);
      return formatDistanceToNow(date, { addSuffix: true });
    } catch {
      return 'unknown';
    }
  };

  const getCategoryColor = (category) => {
    const colors = {
      'Stablecoins': '#4a9eff',
      'RWA': '#a55eea',
      'Fintech': '#00d97e',
      'Tokenization': '#f7b731',
      'Regulation': '#ff6348',
      'Funding': '#ff4757',
    };
    return colors[category] || '#4a9eff';
  };

  if (items.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500 text-sm">
        No items found. Try a different filter.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto -mx-2 sm:mx-0">
      <table className="w-full text-sm min-w-[640px]">
        <thead className="sticky top-0 bg-zinc-950 border-b border-zinc-800">
          <tr className="text-left text-zinc-400 text-xs uppercase">
            <th className="px-3 sm:px-4 py-3 w-16 sm:w-20">Time</th>
            <th className="px-3 sm:px-4 py-3 w-24 sm:w-32 hidden sm:table-cell">Source</th>
            <th className="px-3 sm:px-4 py-3">Headline</th>
            <th className="px-3 sm:px-4 py-3 w-48 sm:w-56">Tags</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              onClick={() => window.open(item.url || item.link, '_blank')}
              className="border-b border-zinc-800/50 cursor-pointer transition-all hover:bg-zinc-900"
            >
              {/* Time */}
              <td className="px-3 sm:px-4 py-4 text-zinc-400 font-mono text-xs whitespace-nowrap">
                {formatTime(item.published_at)}
              </td>

              {/* Source - Hidden on mobile */}
              <td className="px-3 sm:px-4 py-4 text-zinc-500 text-xs truncate hidden sm:table-cell">
                {item.source === 'Google News RSS' && item.feed_name ? item.feed_name : item.source}
              </td>

              {/* Headline */}
              <td className="px-3 sm:px-4 py-4 text-zinc-100">
                <div className="flex flex-col sm:flex-row sm:items-start gap-1 sm:gap-3">
                  <span className="flex-1 line-clamp-2">{item.title}</span>
                  <span className="text-zinc-600 text-xs whitespace-nowrap">
                    {getTimeAgo(item.published_at)}
                  </span>
                </div>
                {/* Show source on mobile */}
                <div className="sm:hidden mt-1 text-zinc-500 text-xs">
                  {item.source === 'Google News RSS' && item.feed_name ? item.feed_name : item.source}
                </div>
              </td>

              {/* Tags */}
              <td className="px-3 sm:px-4 py-4">
                <div className="flex flex-wrap gap-1.5">
                  {item.categories?.slice(0, 2).map((cat, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 text-xs font-semibold rounded-full whitespace-nowrap"
                      style={{
                        color: getCategoryColor(cat),
                        borderColor: getCategoryColor(cat),
                        backgroundColor: `${getCategoryColor(cat)}15`,
                        border: `1px solid ${getCategoryColor(cat)}40`
                      }}
                    >
                      {cat}
                    </span>
                  ))}
                  {item.matched_keywords?.slice(0, 1).map((kw, idx) => (
                    <span
                      key={`kw-${idx}`}
                      className="px-2 py-0.5 text-xs rounded-full bg-zinc-800/50 text-zinc-400 border border-zinc-700/50 whitespace-nowrap hidden sm:inline-block"
                    >
                      {kw.toLowerCase()}
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default LiveStream;
