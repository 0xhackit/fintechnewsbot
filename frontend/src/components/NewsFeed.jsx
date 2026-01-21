import React from 'react';
import NewsCard from './NewsCard';
import './NewsFeed.css';

function NewsFeed({ news, selectedCategory }) {
  if (news.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">📭</div>
        <h2>No Stories Found</h2>
        <p>Try adjusting your filters or check back later for new content.</p>
      </div>
    );
  }

  return (
    <div className="news-feed">
      <div className="feed-header">
        <h2 className="feed-title">
          {selectedCategory === 'All' ? 'All Stories' : selectedCategory}
        </h2>
        <span className="feed-count mono">{news.length} items</span>
      </div>

      <div className="news-grid">
        {news.map((item, index) => (
          <NewsCard key={`${item.link}-${index}`} item={item} />
        ))}
      </div>
    </div>
  );
}

export default NewsFeed;
