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
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-zinc-950 border-b border-zinc-800">
          <tr className="text-left text-zinc-400 text-xs uppercase">
            <th className="px-3 sm:px-4 py-3 w-20">Time</th>
            <th className="px-3 sm:px-4 py-3 w-32 hidden lg:table-cell">Source</th>
            <th className="px-3 sm:px-4 py-3">Headline</th>
            <th className="px-3 sm:px-4 py-3 w-64 hidden md:table-cell">Tags</th>
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
              <td className="px-3 sm:px-4 py-4 text-zinc-400 font-mono text-xs whitespace-nowrap align-top">
                {formatTime(item.published_at)}
              </td>

              {/* Source - Hidden on mobile/tablet */}
              <td className="px-3 sm:px-4 py-4 text-zinc-500 text-xs truncate hidden lg:table-cell align-top">
                {item.source === 'Google News RSS' && item.feed_name ? item.feed_name : item.source}
              </td>

              {/* Headline */}
              <td className="px-3 sm:px-4 py-4 text-zinc-100 align-top">
                <div className="flex flex-col gap-1">
                  <span className="line-clamp-2 leading-relaxed">{item.title}</span>
                  <div className="flex items-center gap-2 text-xs text-zinc-600">
                    <span>{getTimeAgo(item.published_at)}</span>
                    {/* Show source on mobile/tablet */}
                    <span className="lg:hidden">• {item.source === 'Google News RSS' && item.feed_name ? item.feed_name : item.source}</span>
                  </div>
                  {/* Show tags on mobile */}
                  <div className="md:hidden mt-2 flex flex-wrap gap-2">
                    {item.categories?.slice(0, 3).map((cat, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 text-xs font-semibold rounded-full whitespace-nowrap"
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
                  </div>
                </div>
              </td>

              {/* Tags - Hidden on mobile */}
              <td className="px-3 sm:px-4 py-4 hidden md:table-cell align-top">
                <div className="flex flex-wrap gap-2">
                  {item.categories?.slice(0, 3).map((cat, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-1 text-xs font-semibold rounded-full whitespace-nowrap"
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
                  {item.matched_keywords?.slice(0, 2).map((kw, idx) => (
                    <span
                      key={`kw-${idx}`}
                      className="px-2.5 py-1 text-xs rounded-full bg-zinc-800/50 text-zinc-400 border border-zinc-700/50 whitespace-nowrap"
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
