# Telegram Alert Rules

## Overview
This document explains the rules for posting news alerts to the Telegram group to prevent spam and ensure high-quality signal.

## Rules Implemented

### 1. **Telegram Posts Are NOT Auto-Posted**
- Telegram channel posts are **excluded** from auto-posting to the Telegram group
- Rationale: Wait for actual news coverage before alerting the group
- Example: If a Telegram channel says "Coinbase launches stablecoin", we don't post it immediately
- We wait for a Bloomberg/Reuters/Coindesk article about it before posting

### 2. **Downrank Telegram Sources**
- Telegram posts get a **-15 point scoring penalty** vs news articles
- Google News RSS articles are prioritized over Telegram announcements
- This ensures news coverage ranks higher than social media rumors

### 3. **Minimum Score Threshold**
- Only items with **score ≥ 50** are eligible for Telegram alerts
- Raised from MIN_ALERT_SCORE = 20 to MIN_ALERT_SCORE = 50
- Filters out low-quality, speculative, or unverified content

### 4. **Deduplication Still Applies**
- Similarity threshold: 0.75 (75% similar titles are considered duplicates)
- Prevents posting the same story multiple times even if from different sources
- Keeps last 100 seen titles for comparison

## Scoring Changes

### Source Penalty (New)
```python
# In src/app.py score_item()
if source_type == 'telegram':
    source_penalty = -15  # Telegram posts get -15 point penalty
```

### Score Breakdown
```json
{
  "tier1": 2,              // Launch patterns (25 points each)
  "tier2": 1,              // Activity patterns (10 points each)
  "commentary": 0,         // Commentary penalty (-20 each)
  "listicle": 0,           // Listicle penalty (-100 each)
  "generic": 0,            // Generic penalty (-50 each)
  "freshness": 10,         // Freshness bonus (10 for <6h)
  "source_penalty": -15,   // NEW: Telegram downrank
  "launch_score": 60,
  "commentary_penalty": 0,
  "listicle_penalty": 0,
  "generic_penalty": 0
}
```

## Alert Filter Logic

### In `scripts/run_alerts.py`

```python
# Exclude Telegram sources
if EXCLUDE_TELEGRAM_SOURCES and source_type == "telegram":
    skipped_telegram += 1
    print(f"📱 Skipping Telegram post (wait for news coverage): \"{title[:70]}...\"")
    continue

# Minimum score filter
if score < MIN_ALERT_SCORE:  # MIN_ALERT_SCORE = 50
    skipped_low_score += 1
    continue
```

## Example Scenarios

### ❌ Scenario 1: Telegram Announcement Only
- **Source**: Telegram channel "WuBlockchain"
- **Title**: "Breaking: Coinbase to launch USDC payment rails"
- **Action**: ❌ NOT posted to group
- **Reason**: source_type = "telegram" → excluded

### ✅ Scenario 2: News Article After Telegram
- **Source**: Coindesk RSS
- **Title**: "Coinbase Launches USDC Payment Rails for Merchants"
- **Score**: 60 (launch_score=60 + freshness=10 + source_penalty=0)
- **Action**: ✅ Posted to group
- **Reason**: score ≥ 50, source_type = "rss"

### ❌ Scenario 3: Low Score News
- **Source**: Blog commentary
- **Title**: "Why Coinbase's USDC move could be big"
- **Score**: 30 (commentary_penalty=-20)
- **Action**: ❌ NOT posted
- **Reason**: score < 50

## Config Changes

### `config.json`
```json
{
  "alerts": {
    "auto_approve": true,
    "post_to_telegram": true,
    "post_to_x": false,
    "min_score_for_telegram": 50,
    "exclude_telegram_sources": true,
    "note": "Only post RSS/Google News articles with score >= 50. Telegram posts are excluded to prevent spam."
  }
}
```

## Benefits

1. **Reduces Spam**: No unverified Telegram rumors posted
2. **Higher Signal**: Only quality news articles (score ≥ 50) posted
3. **Prevents Duplicates**: Same story from multiple sources only posted once
4. **Maintains Trust**: Group members see verified news, not speculation
5. **Better UX**: Telegram posts still visible in web UI but not pushed to group

## Terminal View

Telegram posts are still available in the terminal UI:
- Users can filter with `/telegram` (if that filter is added)
- Shows with T+ timestamp like other sources
- Just not auto-posted to alert the entire group

## Summary

**Key Rule**: Telegram posts are for internal visibility only. Only post to the group when there's actual news coverage (RSS/Google News) with high relevance score (≥50).
