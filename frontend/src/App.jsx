import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';
import NewsHeader from './components/NewsHeader';
import CategoryFilter from './components/CategoryFilter';
import NewsFeed from './components/NewsFeed';
import StatsPanel from './components/StatsPanel';

// API base URL - change to your deployed backend URL
const API_BASE = import.meta.env.VITE_API_URL || '/api';

function App() {
  const [news, setNews] = useState([]);
  const [categories, setCategories] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [minScore, setMinScore] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Fetch news data
  const fetchNews = async () => {
    try {
      const params = {
        ...(selectedCategory !== 'All' && { category: selectedCategory }),
        ...(minScore > 0 && { min_score: minScore }),
      };

      const response = await axios.get(`${API_BASE}/news`, { params });
      setNews(response.data.items);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Error fetching news:', err);
      setError('Failed to fetch news. Make sure the backend is running.');
    }
  };

  // Fetch categories
  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API_BASE}/categories`);
      setCategories([
        { name: 'All', count: response.data.categories.reduce((sum, cat) => sum + cat.count, 0) },
        ...response.data.categories
      ]);
    } catch (err) {
      console.error('Error fetching categories:', err);
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/stats`);
      setStats(response.data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  // Initial data load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchNews(), fetchCategories(), fetchStats()]);
      setLoading(false);
    };
    loadData();
  }, []);

  // Refetch news when filters change
  useEffect(() => {
    if (!loading) {
      fetchNews();
    }
  }, [selectedCategory, minScore]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      fetchNews();
      fetchCategories();
      fetchStats();
    }, 5 * 60 * 1000); // 5 minutes

    return () => clearInterval(interval);
  }, [selectedCategory, minScore]);

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading fintech news terminal...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-container">
        <div className="error-content">
          <h2>⚠️ Connection Error</h2>
          <p>{error}</p>
          <button onClick={() => window.location.reload()} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <NewsHeader stats={stats} lastUpdate={lastUpdate} />

      <div className="main-content">
        <aside className="sidebar">
          <CategoryFilter
            categories={categories}
            selectedCategory={selectedCategory}
            onSelectCategory={setSelectedCategory}
            minScore={minScore}
            onScoreChange={setMinScore}
          />

          {stats && <StatsPanel stats={stats} />}
        </aside>

        <main className="feed-container">
          <NewsFeed
            news={news}
            selectedCategory={selectedCategory}
          />
        </main>
      </div>
    </div>
  );
}

export default App;
