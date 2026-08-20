"use client";

import { usePathname } from "next/navigation";

/**
 * The shared site header for the admin/tools routes (/analyze, /dashboard).
 * The home route ("/") is the Broadsheet edition, which renders its own
 * masthead — so this returns null there to avoid a double header.
 */
export default function SiteChrome() {
  const pathname = usePathname();
  if (pathname === "/") return null;

  return (
    <header className="header">
      <a href="/" className="header-brand">
        <h1>Fintech Onchain</h1>
      </a>
      <nav className="nav-links">
        <a href="/" className="nav-link">Feed</a>
        <a href="/analyze" className="nav-link">Analyze</a>
      </nav>
      <div className="live-badge">
        <span className="live-dot" />
        Live
      </div>
    </header>
  );
}
