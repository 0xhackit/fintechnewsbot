import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Header from '../components/Header';
import CommandInput from '../components/CommandInput';
import LiveStream from '../components/LiveStream';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

// Major banks for /banks filter
const MAJOR_BANKS = [
  'JPMorgan', 'JPM', 'JP Morgan', 'Citi', 'Citigroup', 'Citibank',
  'HSBC', 'Standard Chartered', 'BNY', 'Bank of New York', 'BNY Mellon',
  'UBS', 'Goldman Sachs', 'Morgan Stanley', 'Wells Fargo', 'Bank of America', 'BofA'
];

function Terminal() {
  const [allItems, setAllItems] = useState([]);
  const [filteredItems, setFilteredItems] = useState([]);
  const [activeFilter, setActiveFilter] = useState(null);
  const [sortMode, setSortMode] = useState('relevant');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [bootComplete, setBootComplete] = useState(false);

  // Terminal boot animation
  useEffect(() => {
    const timer = setTimeout(() => {
      setBootComplete(true);
    }, 800);
    return () => clearTimeout(timer);
  }, []);

  // Sort items based on current sort mode
  const sortItems = (items, mode) => {
    const sorted = [...items];
    if (mode === 'latest') {
      sorted.sort((a, b) => {
        const dateA = new Date(a.published_at || 0);
        const dateB = new Date(b.published_at || 0);
        return dateB - dateA;
      });
    } else {
      sorted.sort((a, b) => {
        const scoreA = a.score || 0;
        const scoreB = b.score || 0;
        if (scoreB !== scoreA) {
          return scoreB - scoreA;
        }
        const dateA = new Date(a.published_at || 0);
        const dateB = new Date(b.published_at || 0);
        return dateB - dateA;
      });
    }
    return sorted;
  };

  // Fetch all news items
  const fetchNews = async () => {
    try {
      const response = await axios.get(`${API_BASE}/news`);
      const items = response.data.items || [];

      const sorted = sortItems(items, sortMode);

      setAllItems(items);
      setFilteredItems(sorted);
      setError(null);

      if (items.length > 0) {
        const mostRecent = items.reduce((latest, item) => {
          const itemDate = new Date(item.published_at || 0);
          const latestDate = new Date(latest || 0);
          return itemDate > latestDate ? item.published_at : latest;
        }, null);
        setLastUpdated(mostRecent);
      } else {
        setLastUpdated(new Date().toISOString());
      }
    } catch (err) {
      console.error('Error fetching news:', err);
      setError('Failed to fetch news. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => {
    fetchNews();
  }, []);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(fetchNews, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Command parser and filter logic
  const handleCommand = (cmd) => {
    if (!cmd) {
      setActiveFilter(null);
      const sorted = sortItems(allItems, sortMode);
      setFilteredItems(sorted);
      return;
    }

    const cmdLower = cmd.toLowerCase();

    if (cmdLower === '/latest') {
      setSortMode('latest');
      setActiveFilter(cmd);
      const sorted = sortItems(activeFilter ? filteredItems : allItems, 'latest');
      setFilteredItems(sorted);
      return;
    } else if (cmdLower === '/relevant') {
      setSortMode('relevant');
      setActiveFilter(cmd);
      const sorted = sortItems(activeFilter ? filteredItems : allItems, 'relevant');
      setFilteredItems(sorted);
      return;
    }

    setActiveFilter(cmd);

    let filtered = [];

    if (cmdLower === '/stablecoins') {
      filtered = allItems.filter(item => {
        const topics = (item.matched_topics || []).map(t => t.toLowerCase());
        const keywords = (item.matched_keywords || []).map(k => k.toLowerCase());
        return topics.some(t => t.includes('stablecoin')) ||
          keywords.some(k => ['stablecoin', 'usdc', 'usdt', 'tether', 'circle'].includes(k));
      });
    } else if (cmdLower === '/rwa') {
      filtered = allItems.filter(item => {
        const topics = (item.matched_topics || []).map(t => t.toLowerCase());
        const keywords = (item.matched_keywords || []).map(k => k.toLowerCase());
        return topics.some(t => t.includes('tokeniz') || t.includes('rwa') || t.includes('private credit') || t.includes('treasur')) ||
          keywords.some(k => k.includes('tokeniz') || k.includes('rwa'));
      });
    } else if (cmdLower === '/banks') {
      filtered = allItems.filter(item => {
        const title = (item.title || '').toLowerCase();
        const snippet = (item.snippet || '').toLowerCase();
        const source = (item.source || '').toLowerCase();
        return MAJOR_BANKS.some(bank =>
          title.includes(bank.toLowerCase()) ||
          snippet.includes(bank.toLowerCase()) ||
          source.includes(bank.toLowerCase())
        );
      });
    } else if (cmdLower === '/apac') {
      filtered = allItems.filter(item => {
        const text = `${item.title} ${item.snippet}`.toLowerCase();
        const apacTerms = ['singapore', 'hong kong', 'japan', 'korea', 'china', 'india', 'apac', 'asia', 'australia'];
        return apacTerms.some(term => text.includes(term));
      });
    } else if (cmdLower === '/launches') {
      filtered = allItems.filter(item => {
        const keywords = (item.matched_keywords || []).map(k => k.toLowerCase());
        const topics = (item.matched_topics || []).map(t => t.toLowerCase());
        const title = (item.title || '').toLowerCase();
        const launchTerms = ['launch', 'pilot', 'partnership', 'rollout', 'introduces', 'unveils'];
        return topics.some(t => t.includes('launch')) ||
          keywords.some(k => launchTerms.includes(k)) ||
          launchTerms.some(term => title.includes(term));
      });
    } else if (cmdLower === '/funding') {
      filtered = allItems.filter(item => {
        const keywords = (item.matched_keywords || []).map(k => k.toLowerCase());
        const title = (item.title || '').toLowerCase();
        const fundingTerms = ['funding', 'raises', 'raised', 'series a', 'series b', 'series c', 'm&a', 'acquisition', 'acquires'];
        return keywords.some(k => fundingTerms.includes(k)) ||
          fundingTerms.some(term => title.includes(term));
      });
    } else if (cmdLower.startsWith('/entities/')) {
      const entity = cmdLower.replace('/entities/', '').trim();
      if (entity) {
        filtered = allItems.filter(item => {
          const text = `${item.title} ${item.snippet} ${item.source}`.toLowerCase();
          return text.includes(entity);
        });
      }
    } else {
      filtered = allItems;
    }

    const sorted = sortItems(filtered, sortMode);
    setFilteredItems(sorted);
  };

  if (!bootComplete) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-gray-900 text-xl mb-3 font-semibold">
            Fintech Onchain
          </div>
          <div className="text-gray-500 text-sm mb-4">Loading...</div>
          <div className="w-48 h-1 bg-gray-200 rounded-full overflow-hidden mx-auto">
            <div className="h-full bg-blue-600 shimmer"></div>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center fade-in">
        <div className="text-center">
          <div className="text-gray-900 text-xl mb-3 font-semibold">Loading feed...</div>
          <div className="w-48 h-1 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-blue-600 shimmer"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center fade-in">
        <div className="text-center">
          <div className="text-red-600 text-xl mb-2 font-semibold">⚠ Connection Error</div>
          <div className="text-gray-600 text-sm mb-4">{error}</div>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-3 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-all duration-300"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 fade-in">
      <Header lastUpdated={lastUpdated} />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <CommandInput
            onCommand={handleCommand}
            activeFilter={activeFilter}
          />
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          <LiveStream items={filteredItems} />
        </div>
      </div>
    </div>
  );
}

export default Terminal;
