# Fintech News MVP

Automated fintech news aggregator with multi-platform alerts to **Telegram** and **X (Twitter)**.

## What it does
- Pulls from Google News RSS, Telegram channels, and custom feeds
- Normalizes items (HTML strip, URL canonicalization, date parsing)
- Keyword + topic matching with scoring
- Hard-dedupes by canonical URL
- **Automated alerts** to Telegram and X (Twitter)
- **Manual review workflow** via GitHub issues
- **Auto-approve mode** for hands-free posting
- Outputs:
  - `out/items_last24h.json`
  - `out/digest.md`
  - `out/alerts_drafts.json`

## 🚀 Quick Start - X API (Free)

**Get posting to X in 5 minutes** with the Free Tier (50 posts/day):

See **[QUICK_START.md](QUICK_START.md)** for step-by-step setup.

**TL;DR:**
1. Get free X API credentials from https://developer.twitter.com
2. Add 4 secrets to GitHub (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
3. Done! Alerts will post to both Telegram and X

## Features

### Multi-Platform Posting
- ✅ **Telegram** - Rich HTML formatting with inline links
- ✅ **X (Twitter)** - Auto-formatted tweets (title + link)
- ✅ **Free Tier Compatible** - Works with X API Free (50 posts/day)

### Flexible Review Modes
- **Manual Review** (default) - Approve via GitHub issues before posting
- **Auto-Approve** - Automatic posting without review

### Smart Filtering
- Topic-based matching (Stablecoins, RWA, Crypto fintech)
- Digital asset banks tracking (JPMorgan, Goldman Sachs, Stripe, Coinbase, etc.)
- Keyword scoring and ranking

## Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt