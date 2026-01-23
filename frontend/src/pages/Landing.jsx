import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

function Landing() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({ total: 0, highPriority: 0, sources: 0 });
  const [previewItems, setPreviewItems] = useState([]);
  const [typedCommand, setTypedCommand] = useState('');
  const [showCursor, setShowCursor] = useState(true);
  const commandToType = '/stablecoins';

  // Fetch stats and preview items
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get(`${API_BASE}/news`);
        const items = response.data.items || [];

        const highPriority = items.filter(item => (item.score || 0) >= 70).length;
        const sourcesSet = new Set(items.map(item => item.source));

        setStats({
          total: items.length,
          highPriority,
          sources: sourcesSet.size
        });

        // Get top 3 items for preview
        const topItems = items
          .sort((a, b) => (b.score || 0) - (a.score || 0))
          .slice(0, 3);
        setPreviewItems(topItems);
      } catch (err) {
        console.error('Error fetching data:', err);
      }
    };

    fetchData();
  }, []);

  // Typing animation
  useEffect(() => {
    if (typedCommand.length < commandToType.length) {
      const timeout = setTimeout(() => {
        setTypedCommand(commandToType.slice(0, typedCommand.length + 1));
      }, 150);
      return () => clearTimeout(timeout);
    }
  }, [typedCommand]);

  // Cursor blink
  useEffect(() => {
    const interval = setInterval(() => {
      setShowCursor(prev => !prev);
    }, 500);
    return () => clearInterval(interval);
  }, []);

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
      'Stablecoins': '#4a9eff',
      'RWA': '#a55eea',
      'Fintech': '#00d97e',
      'Institutional': '#22d3ee',
    };
    return colors[category] || '#4a9eff';
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        {/* Animated grid background */}
        <div className="absolute inset-0 bg-grid-pattern opacity-5"></div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-24">
          {/* Logo and Title */}
          <div className="text-center mb-12 fade-in">
            <div className="flex items-center justify-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-lg bg-zinc-800 flex items-center justify-center border border-zinc-700">
                <span className="text-emerald-400 text-2xl font-bold">F</span>
              </div>
              <h1 className="text-4xl md:text-5xl font-bold font-mono tracking-tight text-emerald-400">
                FINTECH_ONCHAIN
              </h1>
            </div>

            <h2 className="text-2xl md:text-3xl font-semibold text-zinc-100 mb-4">
              Real-Time Intelligence for Institutional Crypto
            </h2>

            <p className="text-lg text-zinc-400 max-w-2xl mx-auto mb-8">
              Track stablecoins, RWA tokenization, and major bank crypto moves—all in one terminal feed.
              No noise. Just signal.
            </p>

            {/* Live Stats */}
            <div className="flex flex-wrap items-center justify-center gap-6 mb-10">
              <div className="flex items-center gap-2 text-sm">
                <span className="text-emerald-400">🔥</span>
                <span className="text-zinc-300 font-semibold">{stats.highPriority} high-priority</span>
                <span className="text-zinc-500">stories today</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-emerald-400">📊</span>
                <span className="text-zinc-300 font-semibold">{stats.total} articles</span>
                <span className="text-zinc-500">from {stats.sources} sources</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
                <span className="text-zinc-300 font-semibold">Updated</span>
                <span className="text-zinc-500">2 minutes ago</span>
              </div>
            </div>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => navigate('/terminal')}
                className="px-8 py-4 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-lg transition-all duration-200 transform hover:scale-105 glow-emerald text-lg"
              >
                Launch Terminal →
              </button>
              <button
                onClick={() => document.getElementById('preview').scrollIntoView({ behavior: 'smooth' })}
                className="px-8 py-4 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-zinc-100 font-semibold rounded-lg transition-all duration-200"
              >
                See Live Preview
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Live Preview Section */}
      <div id="preview" className="py-20 bg-zinc-900/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h3 className="text-3xl font-bold text-zinc-100 mb-4">
              See What You're Missing
            </h3>
            <p className="text-zinc-400 text-lg">
              Command-line filtering makes it instant
            </p>
          </div>

          {/* Interactive Command Demo */}
          <div className="max-w-4xl mx-auto mb-12">
            <div className="border-2 border-zinc-700 bg-zinc-950/80 backdrop-blur rounded-lg p-6 command-center-glow">
              <div className="mb-3">
                <div className="text-xs text-zinc-500 font-mono mb-2">Try it yourself:</div>
              </div>

              <div className="bg-zinc-900/60 border border-zinc-700 rounded-lg px-4 py-3 font-mono">
                <div className="flex items-center gap-3">
                  <span className="text-emerald-400 text-xl">$</span>
                  <span className="text-zinc-100 text-lg">
                    {typedCommand}
                    {showCursor && typedCommand.length === commandToType.length && (
                      <span className="text-emerald-400">_</span>
                    )}
                  </span>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-xs text-zinc-500">Quick filters:</span>
                {['/stablecoins', '/rwa', '/banks', '/apac'].map((cmd) => (
                  <button
                    key={cmd}
                    onClick={() => navigate('/terminal')}
                    className="px-2 py-1 text-xs rounded bg-zinc-800/50 text-zinc-400 hover:text-emerald-400 hover:bg-zinc-800 transition-all font-mono"
                  >
                    {cmd}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Live Story Cards */}
          <div className="max-w-4xl mx-auto space-y-4">
            {previewItems.slice(0, 3).map((item, idx) => {
              const priority = (item.score || 0) >= 70 ? 'high' : 'medium';
              return (
                <div
                  key={item.id}
                  className={`border border-zinc-800 rounded-lg p-6 transition-all duration-200 hover:bg-zinc-900/50 hover:border-zinc-700 fade-in ${
                    priority === 'high' ? 'border-l-4 border-l-emerald-400' : ''
                  }`}
                  style={{ animationDelay: `${idx * 0.1}s` }}
                >
                  <div className="flex items-center flex-wrap gap-3 mb-3 text-xs text-zinc-500 font-mono">
                    {priority === 'high' && <span className="text-emerald-400">🔥</span>}
                    <span>T+0 14:23</span>
                    <span className="text-zinc-700">•</span>
                    <span className="text-zinc-400">{item.source}</span>
                    {(item.cluster_size || 1) > 1 && (
                      <>
                        <span className="text-zinc-700">•</span>
                        <span className="text-emerald-400">📊 {item.cluster_size} sources</span>
                      </>
                    )}
                  </div>

                  <h3 className="text-lg md:text-xl font-semibold text-zinc-50 leading-tight mb-3">
                    {item.title}
                  </h3>

                  {item.snippet && (
                    <p className="text-sm text-zinc-400 leading-relaxed mb-4 line-clamp-2">
                      {item.snippet}
                    </p>
                  )}

                  <div className="flex flex-wrap gap-2">
                    {item.matched_topics?.slice(0, 3).map((cat, i) => {
                      const shortTag = getShortTag(cat);
                      return (
                        <span
                          key={i}
                          className="px-2.5 py-1 text-xs font-semibold rounded-full"
                          style={{
                            color: getCategoryColor(shortTag),
                            borderColor: getCategoryColor(shortTag),
                            backgroundColor: `${getCategoryColor(shortTag)}15`,
                            border: `1px solid ${getCategoryColor(shortTag)}40`
                          }}
                        >
                          {shortTag}
                        </span>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="text-center mt-10">
            <button
              onClick={() => navigate('/terminal')}
              className="px-8 py-4 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-lg transition-all duration-200 transform hover:scale-105 text-lg"
            >
              View Full Feed →
            </button>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="py-20 border-t border-zinc-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h3 className="text-3xl font-bold text-zinc-100 mb-4">
              Built for Speed, Not Distraction
            </h3>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="border border-zinc-800 rounded-lg p-6 bg-zinc-900/30">
              <div className="text-3xl mb-4">⚡</div>
              <h4 className="text-xl font-semibold text-zinc-100 mb-3">Command-Line Filtering</h4>
              <p className="text-zinc-400 mb-3">
                Type /stablecoins, /rwa, /banks. Filter 500+ daily stories in &lt;1 second.
              </p>
              <code className="text-xs text-emerald-400 font-mono bg-zinc-950 px-2 py-1 rounded">
                $ /entities/jpmorgan
              </code>
            </div>

            {/* Feature 2 */}
            <div className="border border-zinc-800 rounded-lg p-6 bg-zinc-900/30">
              <div className="text-3xl mb-4">📊</div>
              <h4 className="text-xl font-semibold text-zinc-100 mb-3">Multi-Source Intelligence</h4>
              <p className="text-zinc-400 mb-3">
                Aggregates Bloomberg, Coindesk, Reuters, Telegram alpha channels, Twitter.
              </p>
              <div className="text-xs text-zinc-500">Auto-deduplicated and scored</div>
            </div>

            {/* Feature 3 */}
            <div className="border border-zinc-800 rounded-lg p-6 bg-zinc-900/30">
              <div className="text-3xl mb-4">🎯</div>
              <h4 className="text-xl font-semibold text-zinc-100 mb-3">Smart Relevance Scoring</h4>
              <p className="text-zinc-400 mb-3">
                ML-powered ranking surfaces what matters to institutional decision-makers.
              </p>
              <div className="text-xs text-zinc-500">Score ≥70 = high priority 🔥</div>
            </div>

            {/* Feature 4 */}
            <div className="border border-zinc-800 rounded-lg p-6 bg-zinc-900/30">
              <div className="text-3xl mb-4">🕐</div>
              <h4 className="text-xl font-semibold text-zinc-100 mb-3">T+ Time Format</h4>
              <p className="text-zinc-400 mb-3">
                Know exactly when news broke. T+0 = today, T+1 = yesterday, T+2 = 2 days ago.
              </p>
              <code className="text-xs text-emerald-400 font-mono bg-zinc-950 px-2 py-1 rounded">
                T+0 14:23
              </code>
            </div>

            {/* Feature 5 */}
            <div className="border border-zinc-800 rounded-lg p-6 bg-zinc-900/30">
              <div className="text-3xl mb-4">🔥</div>
              <h4 className="text-xl font-semibold text-zinc-100 mb-3">Priority Indicators</h4>
              <p className="text-zinc-400 mb-3">
                High-impact stories flagged automatically. Never miss market-moving events.
              </p>
              <div className="text-xs text-zinc-500">Visual highlighting + left border</div>
            </div>

            {/* Feature 6 */}
            <div className="border border-zinc-800 rounded-lg p-6 bg-zinc-900/30">
              <div className="text-3xl mb-4">⚙️</div>
              <h4 className="text-xl font-semibold text-zinc-100 mb-3">Terminal-First UX</h4>
              <p className="text-zinc-400 mb-3">
                No clicks, no scrolling through tabs. Just type and filter instantly.
              </p>
              <div className="text-xs text-zinc-500">Keyboard shortcuts everywhere</div>
            </div>
          </div>
        </div>
      </div>

      {/* Command Reference */}
      <div className="py-20 bg-zinc-900/30 border-t border-zinc-800">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h3 className="text-3xl font-bold text-zinc-100 mb-4">
              Master the Terminal in 60s
            </h3>
            <p className="text-zinc-400">All available commands at a glance</p>
          </div>

          <div className="border border-zinc-800 rounded-lg bg-zinc-950/80 p-8">
            <div className="mb-8">
              <h4 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-4">
                Filtering
              </h4>
              <div className="space-y-2 font-mono text-sm">
                <div className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                  <code className="text-emerald-400">/stablecoins</code>
                  <span className="text-zinc-400">USDC, USDT, Circle news</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                  <code className="text-emerald-400">/rwa</code>
                  <span className="text-zinc-400">Tokenization, private credit</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                  <code className="text-emerald-400">/banks</code>
                  <span className="text-zinc-400">JPM, Citi, Goldman moves</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                  <code className="text-emerald-400">/apac</code>
                  <span className="text-zinc-400">Asia-Pacific region</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                  <code className="text-emerald-400">/launches</code>
                  <span className="text-zinc-400">New products & pilots</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                  <code className="text-emerald-400">/funding</code>
                  <span className="text-zinc-400">Raises, M&A, Series rounds</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <code className="text-emerald-400">/entities/visa</code>
                  <span className="text-zinc-400">Search specific companies</span>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-4">
                Sorting
              </h4>
              <div className="space-y-2 font-mono text-sm">
                <div className="flex items-center justify-between py-2 border-b border-zinc-800/50">
                  <code className="text-emerald-400">/latest</code>
                  <span className="text-zinc-400">Most recent first</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <code className="text-emerald-400">/relevant</code>
                  <span className="text-zinc-400">Highest priority first</span>
                </div>
              </div>
            </div>
          </div>

          <div className="text-center mt-10">
            <button
              onClick={() => navigate('/terminal')}
              className="px-8 py-4 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-semibold rounded-lg transition-all duration-200 transform hover:scale-105 text-lg"
            >
              Start Using Commands →
            </button>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="py-20 border-t border-zinc-800">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h3 className="text-3xl md:text-4xl font-bold text-zinc-100 mb-6">
            Get Started Today
          </h3>
          <p className="text-xl text-zinc-400 mb-4">
            🆓 Public Beta • Full Access • No Credit Card
          </p>
          <p className="text-zinc-500 mb-8">
            Join hundreds of crypto VCs, treasury teams, and traders using FINTECH_ONCHAIN
          </p>

          <button
            onClick={() => navigate('/terminal')}
            className="px-10 py-5 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-bold rounded-lg transition-all duration-200 transform hover:scale-105 text-xl glow-emerald"
          >
            Launch Terminal Now →
          </button>

          <div className="mt-12 pt-12 border-t border-zinc-800">
            <p className="text-sm text-zinc-500 mb-2">Built for institutional crypto intelligence</p>
            <div className="flex items-center justify-center gap-6 text-xs text-zinc-600">
              <span>v2.1</span>
              <span>•</span>
              <span>99.8% uptime</span>
              <span>•</span>
              <span>Updated every 5 minutes</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Landing;
