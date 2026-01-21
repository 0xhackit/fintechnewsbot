import React, { useState, useRef, useEffect } from 'react';

const COMMANDS = [
  { cmd: '/stablecoins', desc: 'Filter stablecoin news' },
  { cmd: '/rwa', desc: 'Real-world assets & tokenization' },
  { cmd: '/banks', desc: 'Traditional bank partnerships' },
  { cmd: '/apac', desc: 'Asia-Pacific region news' },
  { cmd: '/launches', desc: 'Product launches & pilots' },
  { cmd: '/funding', desc: 'Funding & M&A announcements' },
  { cmd: '/entities/', desc: 'Search by entity name (e.g. /entities/visa)' },
];

function CommandInput({ onCommand, activeFilter }) {
  const [input, setInput] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef(null);

  useEffect(() => {
    // Auto-focus input on mount
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    // Show suggestions when typing "/"
    if (input.startsWith('/')) {
      const query = input.toLowerCase();
      const filtered = COMMANDS.filter(c => c.cmd.toLowerCase().startsWith(query));
      setSuggestions(filtered);
      setSelectedIndex(-1);
    } else {
      setSuggestions([]);
    }
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (selectedIndex >= 0 && suggestions.length > 0) {
        // Select from suggestions
        executeCommand(suggestions[selectedIndex].cmd);
      } else if (input.trim()) {
        // Execute typed command
        executeCommand(input.trim());
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, -1));
    } else if (e.key === 'Escape') {
      setInput('');
      setSuggestions([]);
      setSelectedIndex(-1);
    }
  };

  const executeCommand = (cmd) => {
    onCommand(cmd);
    setInput('');
    setSuggestions([]);
    setSelectedIndex(-1);
  };

  return (
    <div className="relative w-full">
      {/* Command Input Bar */}
      <div className="flex items-center gap-3 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3">
        <span className="text-emerald-400 text-base font-bold">$</span>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type / for commands..."
          className="flex-1 bg-transparent text-zinc-100 text-base outline-none placeholder-zinc-600"
        />
        {activeFilter && (
          <button
            onClick={() => onCommand(null)}
            className="text-sm text-zinc-400 hover:text-zinc-200 transition-colors px-2"
          >
            Clear
          </button>
        )}
      </div>

      {/* Autocomplete Suggestions */}
      {suggestions.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-zinc-900 border border-zinc-800 rounded shadow-lg z-50 max-h-60 overflow-y-auto">
          {suggestions.map((item, idx) => (
            <div
              key={item.cmd}
              onClick={() => executeCommand(item.cmd)}
              className={`px-3 py-2 cursor-pointer flex items-center justify-between ${
                idx === selectedIndex ? 'bg-emerald-500/10 ring-1 ring-emerald-400/50' : 'hover:bg-zinc-800'
              }`}
            >
              <span className="text-emerald-400 text-sm font-mono">{item.cmd}</span>
              <span className="text-zinc-400 text-xs">{item.desc}</span>
            </div>
          ))}
        </div>
      )}

      {/* Active Filter Breadcrumb */}
      {activeFilter && (
        <div className="mt-2 flex items-center gap-2 text-xs">
          <span className="text-zinc-500">Active filter:</span>
          <span className="text-emerald-400 font-mono bg-zinc-900 px-2 py-1 rounded border border-zinc-800">
            {activeFilter}
          </span>
        </div>
      )}
    </div>
  );
}

export default CommandInput;
