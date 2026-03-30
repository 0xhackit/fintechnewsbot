# Fintech News Bot

Automated fintech/crypto news aggregator that fetches, scores, deduplicates, and publishes articles to Telegram and X (Twitter) via GitHub Actions.

## Project Structure

```
src/                    # Core pipeline modules
  app.py                # Main orchestrator: fetch -> normalize -> match -> filter -> score -> dedupe -> output
  fetchers.py           # Google News RSS + Telegram channel ingestion (Telethon)
  normalize.py          # Raw items -> canonical format (stable_id, canonical_url, published_at)
  match.py              # Keyword + topic matching (case-folding, word boundaries, phrases)
  dedupe.py             # Hard dedupe (URL/title) + soft clustering (Jaccard >= 0.65, consensus boost)
  improved_scoring.py   # Scoring engine: institution weighting, financial impact, regulatory priority
  dedup_agent.py        # Unified dedup: SQLite DB + seen_titles + feed.json + session cache + AI tiebreaker
  ranking_agent.py      # AI ranking: Claude Haiku determines tier (high/medium/low/reject) + platform eligibility
  output.py             # Write JSON + Markdown digest
  utils.py              # HTTP session with retries, HTML stripping, URL canonicalization
  ai_filter.py          # AI classification (Claude Haiku) + quality review (typo fix, title cleanup)

scripts/
  run_alerts.py         # Prepare alert drafts: blocklist -> score filter -> dedup agent -> ranking agent -> quality review
  publish_telegram.py   # Post to Telegram (prepare/approve/dry-run/publish modes)
  publish_x.py          # Post to X: news-wire format (title + @handle), OG images, peak-hour scheduling

run.py                  # Entry point: runs src/app.py main()
post_alerts_now.py      # Quick Telegram posting script for GitHub Actions
force_publish.py        # Manual override: bypass filters and post directly
feed_writer.py          # Rolling 7-day feed.json management (upsert by ID, prune old entries)
config.json             # All configuration: RSS feeds, Telegram channels, keywords, topics, alerts settings
blocklist.json          # Blocked URLs, keywords, sources
state/
  seen_alerts.json      # Dedup state: seen IDs + seen titles (last 500)
  posted_articles.db    # SQLite DB for dedup agent (URL hash + fuzzy title matching)
  x_daily_count.json    # Daily X posting counter (cap 40/day)
out/
  items_last24h.json    # Pipeline output: scored + deduped articles
  alerts_drafts.json    # Drafts ready for posting (title, link, message_html, tier, post_to_x)
  feed.json             # Rolling feed of posted articles (7-day window)
  digest.md             # Markdown summary
```

## Pipeline Flow

```
GitHub Actions (every 5 min) -> python run.py
  |
  v
FETCH: Google News RSS (20+ feeds) + Telegram (12 channels)
  -> NORMALIZE: parse dates, strip HTML, canonicalize URLs, generate stable_id
  -> MATCH: keyword + topic matching
  -> FILTER: noise patterns, PR newswire junk, blocklist, crypto-anchor gate
  -> HARD DEDUPE: exact URL or normalized title
  -> SCORE: tier1/tier2 patterns + institution bonus + financial impact + regulatory + freshness
  -> SOFT DEDUPE: Jaccard clustering (>= 0.65), consensus boost from multiple sources
  -> OUTPUT: out/items_last24h.json + out/digest.md
  |
  v
python scripts/run_alerts.py --mode prepare
  -> Load items with score >= 35
  -> Skip: no title/link, Telegram sources, blocklisted, low score
  -> Dedup Agent: unified check (SQLite + seen_titles + feed.json + session cache + AI tiebreaker)
  -> Ranking Agent: Claude Haiku assigns tier (high/medium/low/reject) + post_to_x flag
  -> Quality Review: typo fix + title cleanup (Claude Haiku)
  -> Write out/alerts_drafts.json (includes tier, post_to_x, category)
  |
  v
python post_alerts_now.py                     # -> Telegram (all drafts)
python scripts/publish_x.py --from-drafts     # -> X (only drafts with post_to_x=true)
```

## Key Configuration (config.json)

- `alerts.auto_approve`: true = auto-publish, false = manual review
- `alerts.post_to_telegram`: enable/disable Telegram posting
- `alerts.post_to_x`: enable/disable X posting
- `alerts.min_score_for_telegram`: minimum score threshold (currently 50)
- `alerts.exclude_telegram_sources`: skip Telegram-sourced articles in alerts
- `lookback_hours`: time window for articles (default 24)
- `google_news_rss.feeds`: RSS feed URLs keyed by name
- `telegram.channels`: list of public channel usernames to ingest
- `keywords`: list of keywords for matching
- `topics`: structured topic definitions with "any" matching

## Scoring System (improved_scoring.py)

- **Tier 1 patterns** (launch, unveil, partners, raises): up to +60
- **Tier 2 patterns** (deploy, enable, settle, tokenize): up to +30
- **Institution bonus**: +30 regulators, +20 major banks, +10 crypto-native
- **Financial impact**: +50 ($X trillion), +40 ($X billion), +30 ($X00 million)
- **Regulatory bonus**: +40 regulator + action keyword, +15 keyword only
- **Freshness**: +10 (0-6h), +4 (6-24h)
- **Penalties**: commentary -50, listicle -200, generic -100, Telegram source -15
- **Hard reject**: listicle or generic content forced to -50
- **Smart overrides**: regulator+keyword min 50, financial+institution min 45, central bank+crypto min 50

## Dedup Agent (dedup_agent.py)

Unified duplicate detection consolidating all dedup sources:

**Sources checked:**
- SQLite `posted_articles.db` (last 500 posted articles)
- `seen_alerts.json` titles (last 500)
- `feed.json` entries (rolling 7-day window)
- Session cache (articles approved in current batch)

**Detection methods (cheapest first):**
1. Exact URL hash match (SHA-256 of canonical URL)
2. Entity + event + Jaccard matching (same entity + same event type: seq >= 0.50 or jac >= 0.30)
3. Multi-entity match (2+ shared entities + jac >= 0.10)
4. Entity + token overlap (shared entity + jac >= 0.25)
5. High Jaccard alone (jac >= 0.50)
6. SequenceMatcher (>= 0.75, or >= 0.60 for launch stories)
7. AI tiebreaker (Claude Haiku) for borderline cases (shared entity + jac 0.15-0.25)

## Ranking Agent (ranking_agent.py)

AI-powered quality gate using Claude Haiku. Evaluates each article and returns:
- **tier**: high / medium / low / reject
- **post_to_telegram**: bool
- **post_to_x**: bool (only "high" tier gets posted to X)
- **category**: payments, crypto, banking, regulation, etc.

Falls back to score-based heuristics when `ANTHROPIC_API_KEY` is not set.

## X Posting (publish_x.py)

- **News-wire format**: posts article title with one @company handle substituted for engagement
- **OG image**: fetches og:image from article URL and attaches to tweet
- **Immediate posting**: all X-eligible drafts post immediately when news is detected (no queuing)
- **Daily rate guard**: caps at 40 posts/day (free tier = 50/day)
- **feed.json dedup**: skips articles already posted to X (URL + title similarity check)

## Environment Variables

### Required for GitHub Actions
- `TG_API_ID`, `TG_API_HASH` - Telegram API (for fetching channels)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - Telegram Bot (for posting)
- `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` - Twitter API v2
- `ANTHROPIC_API_KEY` - (optional) enables AI ranking, dedup tiebreaker, and quality review

## Common Commands

```bash
# Run full pipeline locally
python run.py

# Prepare alert drafts
python scripts/run_alerts.py --mode prepare

# Prepare without AI (ranking falls back to score-based heuristics)
python scripts/run_alerts.py --mode prepare --no-ai

# Post drafts to Telegram
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx python post_alerts_now.py

# Post drafts to X
X_API_KEY=xxx X_API_SECRET=xxx X_ACCESS_TOKEN=xxx X_ACCESS_SECRET=xxx python scripts/publish_x.py --from-drafts

# Dry run X (preview without posting)
python scripts/publish_x.py --from-drafts --dry-run

# Dry run Telegram (preview without posting)
python scripts/publish_telegram.py --dry-run

# Manual override publish
python force_publish.py
```

## Important Notes

- GitHub Actions workflow runs every 5 minutes with concurrency limit of 1
- Telegram failure does NOT block X posting (independent steps)
- `state/seen_alerts.json` tracks last 500 seen titles to prevent re-posting
- Ranking agent auto-enables when `ANTHROPIC_API_KEY` is set; falls back to score thresholds otherwise
- `filtered_log.txt` logs all AI-rejected articles for review
- The bot commits state changes back to the repo after each run
- X posts use plain article titles (news-wire style) — no AI rewriting or editorial commentary
