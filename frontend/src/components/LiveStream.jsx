import React from 'react';
import { format, differenceInDays, differenceInHours } from 'date-fns';

function LiveStream({ items }) {
  const formatTime = (dateString) => {
    try {
      const date = new Date(dateString);
      return format(date, 'HH:mm');
    } catch {
      return '--:--';
    }
  };

  const formatRelativeTime = (dateString) => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const hoursAgo = differenceInHours(now, date);

      if (hoursAgo < 1) {
        return 'Just now';
      } else if (hoursAgo < 24) {
        return `${hoursAgo}h ago`;
      } else {
        const daysAgo = differenceInDays(now, date);
        return `${daysAgo}d ago`;
      }
    } catch {
      return '--';
    }
  };

  const getShortTag = (topic) => {
    const mapping = {
      'Stablecoin adoption': 'Stablecoins',
      'Crypto-native fintech launches': 'Fintech',
      'Tokenization & RWA': 'RWA',
      'Institutional crypto': 'Institutional',
    };
    return mapping[topic] || topic;
  };

  const getCategoryColor = (category) => {
    const colors = {
      'Stablecoins': 'bg-blue-50 text-blue-700 border-blue-200',
      'Stablecoin adoption': 'bg-blue-50 text-blue-700 border-blue-200',
      'RWA': 'bg-purple-50 text-purple-700 border-purple-200',
      'Tokenization': 'bg-amber-50 text-amber-700 border-amber-200',
      'Tokenization & RWA': 'bg-purple-50 text-purple-700 border-purple-200',
      'Regulation': 'bg-red-50 text-red-700 border-red-200',
      'Funding': 'bg-pink-50 text-pink-700 border-pink-200',
      'Fintech': 'bg-green-50 text-green-700 border-green-200',
      'Crypto-native fintech launches': 'bg-green-50 text-green-700 border-green-200',
      'Institutional crypto': 'bg-cyan-50 text-cyan-700 border-cyan-200',
      'Institutional': 'bg-cyan-50 text-cyan-700 border-cyan-200',
    };
    return colors[category] || 'bg-blue-50 text-blue-700 border-blue-200';
  };

  const getScorePriority = (score) => {
    if (score >= 70) return 'high';
    if (score >= 40) return 'medium';
    return 'low';
  };

  if (items.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500 text-sm">
        No items found. Try a different filter.
      </div>
    );
  };

  return (
    <div className="space-y-1">
      {items.map((item, index) => {
        const priority = getScorePriority(item.score || 0);
        const hasMultipleSources = (item.cluster_size || 1) > 1;

        return (
          <div
            key={item.id}
            onClick={() => window.open(item.url || item.link, '_blank')}
            className="p-4 cursor-pointer transition-colors duration-150 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
          >
            {/* Meta line: Time + Source */}
            <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
              <span>{formatRelativeTime(item.published_at)}</span>
              <span>·</span>
              <span className="text-gray-400">
                {item.source === 'Google News RSS' && item.feed_name ? item.feed_name : item.source}
              </span>
              {hasMultipleSources && (
                <>
                  <span>·</span>
                  <span className="text-blue-600 font-medium">
                    {item.cluster_size} sources
                  </span>
                </>
              )}
            </div>

            {/* Headline */}
            <h3 className="text-base font-medium text-gray-900 leading-snug mb-2">
              {item.title}
            </h3>

            {/* Snippet */}
            {item.snippet && (
              <p className="text-sm text-gray-600 leading-relaxed mb-3 line-clamp-2">
                {item.snippet}
              </p>
            )}

            {/* Tags */}
            <div className="flex flex-wrap gap-1.5">
              {item.matched_topics?.slice(0, 3).map((cat, idx) => {
                const shortTag = getShortTag(cat);
                return (
                  <span
                    key={idx}
                    className={`px-2 py-0.5 text-xs font-medium rounded border ${getCategoryColor(shortTag)}`}
                  >
                    {shortTag}
                  </span>
                );
              })}
              {item.matched_keywords?.slice(0, 2).map((kw, idx) => (
                <span
                  key={`kw-${idx}`}
                  className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-600 border border-gray-200"
                >
                  {kw.toLowerCase()}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default LiveStream;
