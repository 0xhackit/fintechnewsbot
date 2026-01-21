import React from 'react';
import './StatsPanel.css';

function StatsPanel({ stats }) {
  const scorePercent = (count) => {
    if (stats.total_items === 0) return 0;
    return Math.round((count / stats.total_items) * 100);
  };

  return (
    <div className="stats-panel">
      <h3 className="stats-title">Feed Analytics</h3>

      <div className="stats-section">
        <div className="stats-label">Score Distribution</div>
        <div className="score-bars">
          <div className="score-bar">
            <div className="bar-label">
              <span>High (35+)</span>
              <span className="mono">{stats.score_distribution.high}</span>
            </div>
            <div className="bar-track">
              <div
                className="bar-fill bar-high"
                style={{ width: `${scorePercent(stats.score_distribution.high)}%` }}
              />
            </div>
          </div>

          <div className="score-bar">
            <div className="bar-label">
              <span>Medium (20-34)</span>
              <span className="mono">{stats.score_distribution.medium}</span>
            </div>
            <div className="bar-track">
              <div
                className="bar-fill bar-medium"
                style={{ width: `${scorePercent(stats.score_distribution.medium)}%` }}
              />
            </div>
          </div>

          <div className="score-bar">
            <div className="bar-label">
              <span>Low (&lt;20)</span>
              <span className="mono">{stats.score_distribution.low}</span>
            </div>
            <div className="bar-track">
              <div
                className="bar-fill bar-low"
                style={{ width: `${scorePercent(stats.score_distribution.low)}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="stats-section">
        <div className="stats-label">Source Types</div>
        <div className="source-list">
          {Object.entries(stats.source_types || {}).map(([type, count]) => (
            <div key={type} className="source-item">
              <span className="source-name">{type}</span>
              <span className="source-count mono">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="stats-footer">
        <div className="stats-meta mono">
          Lookback: {stats.lookback_hours}h
        </div>
      </div>
    </div>
  );
}

export default StatsPanel;
