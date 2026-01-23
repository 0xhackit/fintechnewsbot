import React from 'react';

function Header({ lastUpdated }) {
  return (
    <div className="sticky top-0 z-20 bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
        {/* Left side: Logo */}
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">
            Fintech Onchain
          </h1>
        </div>

        {/* Right side: LIVE indicator */}
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 bg-green-500 rounded-full"></span>
          <span className="text-sm text-gray-600">Live</span>
        </div>
      </div>
    </div>
  );
}

export default Header;
