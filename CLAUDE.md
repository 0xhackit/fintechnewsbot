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
  output.py             # Write JSON + Markdown digest
  utils.py              # HTTP session with retries, HTML stripping, URL canonicalization
  ai_filter.py          # AI classification (Claude Haiku) + SQLite duplicate detection (not yet active)

scripts/
  run_alerts.py         # Prepare alert drafts from scored items. Filters: blocklist, score threshold,
                        #   title similarity (SequenceMatcher + Jaccard + entity matching), AI filter (optional)
  publish_telegram.py   # Post to Telegram (prepare/approve/dry-run/publish modes)
  publish_x.py          # Post to X via Twitter API v2 + OAuth 1.0a (--from-drafts or --from-issue-file)

run.py                  # Entry point: runs src/app.py main()
post_alerts_now.py      # Quick Telegram posting script for GitHub Actions
force_publish.py        # Manual override: bypass filters and post directly
config.json             # All configuration: RSS feeds, Telegram channels, keywords, topics, alerts settings
blocklist.json          # Blocked URLs, keywords, sources
state/
  seen_alerts.json      # Dedup state: seen IDs + seen titles (last 100)
  posted_articles.db    # SQLite DB for AI filter dedup (created when AI filter is enabled)
out/
  items_last24h.json    # Pipeline output: scored + deduped articles
  alerts_drafts.json    # Drafts ready for posting (title, link, message_html)
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
  -> Dedup vs seen_titles: SequenceMatcher + Jaccard token overlap + entity matching
  -> (Optional) AI filter: SQLite dedup + Claude Haiku classification
  -> Write out/alerts_drafts.json
  |
  v
python post_alerts_now.py          # -> Telegram
python scripts/publish_x.py --from-drafts  # -> X
```

## Key Configuration (config.json)

- `alerts.auto_approve`: true = auto-publish, false = manual review
- `alerts.post_to_telegram`: enable/disable Telegram posting
- `alerts.post_to_x`: enable/disable X posting
- `alerts.min_score_for_telegram`: minimum score threshold (currently 50)
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

## Dedup in run_alerts.py

Three complementary methods to catch paraphrased duplicates:
1. **SequenceMatcher**: character-level similarity (threshold 0.75, or 0.60 for launches)
2. **Jaccard token overlap**: shared meaningful words after stopword removal
3. **Entity + event matching**: known company names (~50 entities) + event type detection

Decision logic:
- Shared entity + Jaccard >= 0.25 = duplicate
- Jaccard >= 0.50 alone = duplicate
- Same entity + same event type: SequenceMatcher >= 0.50 OR Jaccard >= 0.30

## Environment Variables

### Required for GitHub Actions
- `TG_API_ID`, `TG_API_HASH` - Telegram API (for fetching channels)
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - Telegram Bot (for posting)
- `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` - Twitter API v2
- `ANTHROPIC_API_KEY` - (optional) enables AI classification filter

## Common Commands

```bash
# Run full pipeline locally
python run.py

# Prepare alert drafts
python scripts/run_alerts.py --mode prepare

# Prepare without AI filter
python scripts/run_alerts.py --mode prepare --no-ai

# Post drafts to Telegram
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx python post_alerts_now.py

# Post drafts to X
X_API_KEY=xxx X_API_SECRET=xxx X_ACCESS_TOKEN=xxx X_ACCESS_SECRET=xxx python scripts/publish_x.py --from-drafts

# Dry run Telegram (preview without posting)
python scripts/publish_telegram.py --dry-run

# Manual override publish
python force_publish.py
```

## Important Notes

- GitHub Actions workflow runs every 5 minutes with concurrency limit of 1
- Telegram failure does NOT block X posting (independent steps)
- `state/seen_alerts.json` tracks last 100 seen titles to prevent re-posting
- The AI filter (`src/ai_filter.py`) auto-enables when `ANTHROPIC_API_KEY` is set
- `filtered_log.txt` logs all AI-rejected articles for review
- The bot commits state changes back to the repo after each run
