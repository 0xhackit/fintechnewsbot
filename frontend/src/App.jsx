import React, { useState, useEffect } from 'react';
import axios from 'axios';
import CommandInput from './components/CommandInput';
import LiveStream from './components/LiveStream';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

// Major banks for /banks filter
const MAJOR_BANKS = [
  'JPMorgan', 'JPM', 'JP Morgan', 'Citi', 'Citigroup', 'Citibank',
  'HSBC', 'Standard Chartered', 'BNY', 'Bank of New York', 'BNY Mellon',
  'UBS', 'Goldman Sachs', 'Morgan Stanley', 'Wells Fargo', 'Bank of America', 'BofA'
];

function App() {
  const [allItems, setAllItems] = useState([]);
  const [filteredItems, setFilteredItems] = useState([]);
  const [activeFilter, setActiveFilter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch all news items
  const fetchNews = async () => {
    try {
      const response = await axios.get(`${API_BASE}/news`);
      const items = response.data.items || [];

      // Sort by published_at descending (newest first)
      const sorted = [...items].sort((a, b) => {
        const dateA = new Date(a.published_at || 0);
        const dateB = new Date(b.published_at || 0);
        return dateB - dateA;
      });

      setAllItems(sorted);
      setFilteredItems(sorted);
      setError(null);
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
      // Clear filter
      setActiveFilter(null);
      setFilteredItems(allItems);
      return;
    }

    const cmdLower = cmd.toLowerCase();
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
        // Look for APAC countries/terms in title/snippet
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
      // Unknown command - show all
      filtered = allItems;
    }

    setFilteredItems(filtered);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <div className="text-emerald-400 text-xl mb-2 font-mono">Loading...</div>
          <div className="text-zinc-600 text-sm">Fetching fintech news feed</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-400 text-xl mb-2">⚠ Connection Error</div>
          <div className="text-zinc-400 text-sm mb-4">{error}</div>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-zinc-900 border border-zinc-800 text-zinc-100 text-sm rounded hover:bg-zinc-800 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <div className="border-b border-zinc-800 px-4 sm:px-6 py-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
          <div>
            <h1 className="text-lg sm:text-xl font-bold font-mono text-emerald-400">
              FINTECH_ONCHAIN <span className="text-xs text-zinc-700">v2.0</span>
            </h1>
            <p className="text-xs text-zinc-500 mt-0.5">Real-time fintech & institutional crypto intelligence</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-emerald-400 rounded-full blink"></span>
            <span className="text-sm text-emerald-400 font-mono font-semibold">LIVE</span>
          </div>
        </div>

        {/* Command Input */}
        <div className="max-w-3xl">
          <CommandInput
            onCommand={handleCommand}
            activeFilter={activeFilter}
          />
        </div>
      </div>

      {/* Main Content */}
      <div className="px-4 sm:px-6 py-4">
        <LiveStream items={filteredItems} />
      </div>
    </div>
  );
}

export default App;
