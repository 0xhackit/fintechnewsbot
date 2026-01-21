import React from 'react';
import { formatDistanceToNow } from 'date-fns';
import './NewsCard.css';

function NewsCard({ item }) {
  // Note: Removed Google RSS filter - they aggregate from legitimate sources
  // and the feed_name field shows the actual publication

  const getCategoryColor = (category) => {
    const colors = {
      'Stablecoins': 'var(--accent-blue)',
      'RWA': 'var(--accent-purple)',
      'Fintech': 'var(--accent-green)',
      'Tokenization': 'var(--accent-yellow)',
      'Regulation': 'var(--accent-orange)',
      'Funding': 'var(--accent-red)',
    };
    return colors[category] || 'var(--accent-blue)';
  };

  const formatTimeAgo = (dateString) => {
    try {
      const date = new Date(dateString);
      return formatDistanceToNow(date, { addSuffix: true });
    } catch {
      return 'Unknown';
    }
  };

  const getRelevanceLabel = (score) => {
    if (score >= 35) return 'High';
    if (score >= 20) return 'Medium';
    return 'Low';
  };

  return (
    <article className="news-card fade-in">
      <div className="card-header">
        <div className="card-categories">
          {item.categories.map((cat, idx) => (
            <span
              key={idx}
              className="category-tag"
              style={{ borderColor: getCategoryColor(cat), color: getCategoryColor(cat) }}
            >
              {cat}
            </span>
          ))}
        </div>

        <div className="card-meta-right">
          <span className="meta-time">
            {item.published_at ? formatTimeAgo(item.published_at) : 'Unknown'}
          </span>
        </div>
      </div>

      <h3 className="card-title">
        <a href={item.url || item.link} target="_blank" rel="noopener noreferrer">
          {item.title}
        </a>
      </h3>

      {item.snippet && (
        <p className="card-snippet">{item.snippet}</p>
      )}

      <div className="card-footer">
        <div className="card-meta">
          <span className="meta-source">
            {item.source === 'Google News RSS' && item.feed_name
              ? item.feed_name
              : item.source}
          </span>
          <span className="meta-divider">•</span>
          <span className="meta-relevance">Relevance: {getRelevanceLabel(item.score)}</span>
        </div>

        <div className="card-keywords">
          {item.matched_keywords.slice(0, 3).map((kw, idx) => (
            <span key={idx} className="keyword-tag">
              {kw}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

export default NewsCard;
