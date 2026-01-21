import React from 'react';
import './CategoryFilter.css';

function CategoryFilter({ categories, selectedCategory, onSelectCategory, minScore, onScoreChange }) {
  return (
    <div className="category-filter">
      <div className="filter-section">
        <h3 className="filter-title">Categories</h3>
        <div className="category-list">
          {categories.map((cat) => (
            <button
              key={cat.name}
              className={`category-button ${selectedCategory === cat.name ? 'active' : ''}`}
              onClick={() => onSelectCategory(cat.name)}
            >
              <span className="category-name">{cat.name}</span>
              <span className="category-count mono">{cat.count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="filter-section">
        <h3 className="filter-title">Min Score</h3>
        <div className="score-slider-container">
          <input
            type="range"
            min="0"
            max="100"
            value={minScore}
            onChange={(e) => onScoreChange(Number(e.target.value))}
            className="score-slider"
          />
          <div className="score-labels">
            <span className="score-value mono">{minScore}</span>
            <span className="score-hint">Higher = More relevant</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CategoryFilter;
