import React, { useState, useRef, useEffect } from 'react';

const FILTERS = [
  { cmd: '/latest', desc: 'Sort by latest' },
  { cmd: '/relevant', desc: 'Sort by relevance' },
  { cmd: '/stablecoins', desc: 'Stablecoin news' },
  { cmd: '/rwa', desc: 'Real-world assets' },
  { cmd: '/banks', desc: 'Bank partnerships' },
  { cmd: '/apac', desc: 'Asia-Pacific news' },
  { cmd: '/launches', desc: 'Product launches' },
  { cmd: '/funding', desc: 'Funding & M&A' },
  { cmd: '/entities/', desc: 'Search by entity' },
];

function CommandInput({ onCommand, activeFilter }) {
  const [input, setInput] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const inputRef = useRef(null);

  const executeCommand = (cmd) => {
    onCommand(cmd);
    setInput('');
    setShowFilters(false);
  };

  return (
    <div className="relative w-full max-w-3xl mx-auto">
      {/* Search/Filter Bar */}
      <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 shadow-sm">
        <div className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onFocus={() => setShowFilters(true)}
            onBlur={() => setTimeout(() => setShowFilters(false), 200)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && input.trim()) {
                executeCommand(input.trim());
              }
            }}
            placeholder="Search or filter news..."
            className="flex-1 bg-transparent text-gray-900 outline-none placeholder-gray-400"
          />
          {activeFilter && (
            <button
              onClick={() => onCommand(null)}
              className="text-sm text-gray-500 hover:text-gray-700 px-2"
            >
              Clear
            </button>
          )}
        </div>

        {/* Filter chips */}
        {!showFilters && (
          <div className="flex flex-wrap gap-2 mt-3">
            {FILTERS.slice(0, 6).map((filter) => (
              <button
                key={filter.cmd}
                onClick={() => executeCommand(filter.cmd)}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  activeFilter === filter.cmd
                    ? 'bg-blue-100 text-blue-700 border border-blue-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-gray-200'
                }`}
              >
                {filter.desc}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Dropdown Suggestions */}
      {showFilters && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-60 overflow-y-auto">
          {FILTERS.map((item) => (
            <div
              key={item.cmd}
              onClick={() => executeCommand(item.cmd)}
              className="px-4 py-2.5 cursor-pointer hover:bg-gray-50 flex items-center justify-between border-b border-gray-100 last:border-b-0"
            >
              <span className="text-sm font-medium text-gray-900">{item.cmd}</span>
              <span className="text-xs text-gray-500">{item.desc}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default CommandInput;
