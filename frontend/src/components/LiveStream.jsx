import React from 'react';
import { formatDistanceToNow, format } from 'date-fns';

function LiveStream({ items, onSelectItem, selectedId }) {
  const formatTime = (dateString) => {
    try {
      const date = new Date(dateString);
      return format(date, 'HH:mm');
    } catch {
      return '--:--';
    }
  };

  const getScoreColor = (score) => {
    if (score >= 35) return 'text-emerald-400';
    if (score >= 20) return 'text-yellow-400';
    return 'text-zinc-500';
  };

  const getTimeAgo = (dateString) => {
    try {
      const date = new Date(dateString);
      return formatDistanceToNow(date, { addSuffix: true });
    } catch {
      return 'unknown';
    }
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
            <th className="px-3 py-2 w-16">Time</th>
            <th className="px-3 py-2 w-16 text-right">Score</th>
            <th className="px-3 py-2 w-32">Source</th>
            <th className="px-3 py-2">Headline</th>
            <th className="px-3 py-2 w-48">Tags</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              onClick={() => onSelectItem(item)}
              className={`
                border-b border-zinc-800/50 cursor-pointer transition-all
                hover:bg-zinc-900
                ${selectedId === item.id ? 'bg-emerald-500/10 ring-1 ring-emerald-400/50' : ''}
              `}
            >
              {/* Time */}
              <td className="px-3 py-2 text-zinc-400 font-mono text-xs whitespace-nowrap">
                {formatTime(item.published_at)}
              </td>

              {/* Score */}
              <td className={`px-3 py-2 text-right font-mono text-xs font-bold ${getScoreColor(item.score)}`}>
                {item.score}
              </td>

              {/* Source */}
              <td className="px-3 py-2 text-zinc-500 text-xs truncate">
                {item.source === 'Google News RSS' && item.feed_name ? item.feed_name : item.source}
              </td>

              {/* Headline */}
              <td className="px-3 py-2 text-zinc-100">
                <div className="flex items-start gap-2">
                  <span className="flex-1 line-clamp-2">{item.title}</span>
                  <span className="text-zinc-600 text-xs whitespace-nowrap">
                    {getTimeAgo(item.published_at)}
                  </span>
                </div>
              </td>

              {/* Tags */}
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1">
                  {item.matched_topics?.slice(0, 2).map((topic, idx) => (
                    <span
                      key={idx}
                      className="px-1.5 py-0.5 text-xs bg-zinc-800 text-zinc-300 rounded border border-zinc-700"
                    >
                      {topic.split(' ')[0].toLowerCase()}
                    </span>
                  ))}
                  {item.matched_keywords?.slice(0, 2).map((kw, idx) => (
                    <span
                      key={`kw-${idx}`}
                      className="px-1.5 py-0.5 text-xs bg-blue-500/10 text-blue-400 rounded border border-blue-500/30"
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
