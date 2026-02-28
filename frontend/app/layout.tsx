import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fintech Onchain",
  description:
    "Real-time fintech and crypto news, scored and curated automatically.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
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
        {children}
      </body>
    </html>
  );
}
