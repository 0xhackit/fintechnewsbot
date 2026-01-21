import React from 'react';
import { format } from 'date-fns';

function StoryDrawer({ item, onClose }) {
  if (!item) return null;

  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return format(date, 'MMM dd, yyyy HH:mm');
    } catch {
      return 'Unknown date';
    }
  };

  const getScoreLabel = (score) => {
    if (score >= 35) return 'HIGH';
    if (score >= 20) return 'MEDIUM';
    return 'LOW';
  };

  const getScoreColor = (score) => {
    if (score >= 35) return 'text-emerald-400 border-emerald-400';
    if (score >= 20) return 'text-yellow-400 border-yellow-400';
    return 'text-zinc-500 border-zinc-500';
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full md:w-[600px] bg-zinc-950 border-l border-zinc-800 overflow-y-auto z-50 shadow-2xl">
      {/* Header */}
      <div className="sticky top-0 bg-zinc-950 border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <span className="text-xs uppercase text-zinc-500 tracking-wider">Story Details</span>
        <button
          onClick={onClose}
          className="text-zinc-400 hover:text-zinc-100 transition-colors text-xl"
        >
          ×
        </button>
      </div>

      {/* Content */}
      <div className="p-6 space-y-6">
        {/* Title */}
        <div>
          <h2 className="text-xl font-bold text-zinc-100 leading-tight mb-2">
            {item.title}
          </h2>
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            <span>{formatDate(item.published_at)}</span>
            <span>•</span>
            <span>{item.source === 'Google News RSS' && item.feed_name ? item.feed_name : item.source}</span>
          </div>
        </div>

        {/* Score & Relevance */}
        <div className="flex items-center gap-4">
          <div className={`px-3 py-1 border rounded text-xs font-mono font-bold ${getScoreColor(item.score)}`}>
            {item.score} / {getScoreLabel(item.score)}
          </div>
        </div>

        {/* Snippet */}
        {item.snippet && (
          <div className="bg-zinc-900 border border-zinc-800 rounded p-4">
            <div className="text-xs uppercase text-zinc-500 mb-2">Summary</div>
            <p className="text-sm text-zinc-300 leading-relaxed">{item.snippet}</p>
          </div>
        )}

        {/* Links */}
        <div className="space-y-2">
          <div className="text-xs uppercase text-zinc-500">Links</div>
          <a
            href={item.url || item.link}
            target="_blank"
            rel="noopener noreferrer"
            className="block px-4 py-2 bg-zinc-900 border border-zinc-800 rounded hover:border-emerald-400 transition-colors text-sm text-emerald-400 font-mono truncate"
          >
            {item.url || item.link}
          </a>
        </div>

        {/* Topics */}
        {item.matched_topics && item.matched_topics.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs uppercase text-zinc-500">Topics</div>
            <div className="flex flex-wrap gap-2">
              {item.matched_topics.map((topic, idx) => (
                <span
                  key={idx}
                  className="px-3 py-1 bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-300"
                >
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Keywords */}
        {item.matched_keywords && item.matched_keywords.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs uppercase text-zinc-500">Keywords</div>
            <div className="flex flex-wrap gap-2">
              {item.matched_keywords.map((kw, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-blue-500/10 border border-blue-500/30 rounded text-xs text-blue-400 font-mono"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Score Breakdown */}
        {item.score_breakdown && (
          <div className="space-y-2">
            <div className="text-xs uppercase text-zinc-500">Score Breakdown</div>
            <div className="bg-zinc-900 border border-zinc-800 rounded p-4 space-y-1 font-mono text-xs">
              {Object.entries(item.score_breakdown).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-zinc-400">{key}:</span>
                  <span className="text-zinc-200">{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Why It Matters (placeholder) */}
        <div className="space-y-2">
          <div className="text-xs uppercase text-zinc-500">Why It Matters</div>
          <div className="bg-zinc-900 border border-zinc-800 rounded p-4 text-sm text-zinc-400 italic">
            {item.score >= 35
              ? 'High relevance: Multiple keywords matched, recent publication, strong engagement signals.'
              : item.score >= 20
              ? 'Medium relevance: Key topics matched, moderate engagement.'
              : 'Lower relevance: Contextual match, older publication.'}
          </div>
        </div>
      </div>
    </div>
  );
}

export default StoryDrawer;
