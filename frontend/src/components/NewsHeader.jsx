import React from 'react';
import { formatDistanceToNow } from 'date-fns';
import './NewsHeader.css';

function NewsHeader({ stats, lastUpdate }) {
  return (
    <header className="news-header">
      <div className="header-top">
        <div className="header-brand">
          <div className="brand-icon">📊</div>
          <div className="brand-text">
            <h1>FINTECH NEWS TERMINAL</h1>
            <p className="brand-subtitle">Real-time Digital Assets & Payments Intelligence</p>
          </div>
        </div>

        <div className="header-status">
          <div className="status-indicator">
            <span className="status-dot pulse"></span>
            <span className="status-text">LIVE</span>
          </div>
          {lastUpdate && (
            <div className="last-update mono">
              Updated {formatDistanceToNow(lastUpdate, { addSuffix: true })}
            </div>
          )}
        </div>
      </div>

      {stats && (
        <div className="header-stats">
          <div className="stat-item">
            <span className="stat-label">Total Stories</span>
            <span className="stat-value">{stats.total_items}</span>
          </div>
          <div className="stat-divider"></div>
          <div className="stat-item">
            <span className="stat-label">High Priority</span>
            <span className="stat-value stat-high">{stats.score_distribution.high}</span>
          </div>
          <div className="stat-divider"></div>
          <div className="stat-item">
            <span className="stat-label">Recent (6h)</span>
            <span className="stat-value stat-fresh">{stats.recent_count}</span>
          </div>
          <div className="stat-divider"></div>
          <div className="stat-item">
            <span className="stat-label">Sources</span>
            <span className="stat-value">
              {Object.keys(stats.source_types || {}).length}
            </span>
          </div>
        </div>
      )}
    </header>
  );
}

export default NewsHeader;
