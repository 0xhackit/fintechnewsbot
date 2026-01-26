# Telegram Alerts Fix Summary

**Date:** January 23, 2026
**Issue:** No Telegram posts for 2 days

---

## Root Cause Analysis

### Primary Issue: GitHub Actions Not Running
The `alerts_auto_publish.yml` workflow (scheduled every 5 minutes) hasn't executed since Jan 21, causing:
- ❌ No fresh news fetched (`items_last24h.json` was 2 days old)
- ❌ No alerts generated
- ❌ No Telegram posts sent

**Likely Causes:**
1. GitHub Actions disabled or failing
2. Missing environment secrets (TG_API_ID, TG_API_HASH, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
3. Workflow permissions issue

### Secondary Issue: MIN_ALERT_SCORE Too High
- Was set to **50** (very conservative)
- Many quality stories scored 35-45 and were filtered:
  - Capital One acquires Brex for $5.15B (score 35)
  - Nomura tokenized Bitcoin fund (score 39)
  - BitGo raises $213M for IPO (score 35)

---

## Fixes Applied

### 1. ✅ Lowered Alert Threshold
**File:** `scripts/run_alerts.py:21`
```python
# Before
MIN_ALERT_SCORE = 50  # Raised to 50 to only post high-quality news

# After
MIN_ALERT_SCORE = 35  # Lowered to 35 to catch more quality stories (funding, launches, etc.)
```

**Impact:**
- Went from 4 drafts → **8 drafts**
- Now catches important M&A, funding, and launch stories

### 2. ✅ Ran Pipeline Manually
Executed fresh fetch and scoring:
```bash
python3 run.py
python3 scripts/run_alerts.py --mode prepare
```

**Results:**
- Fetched 39 fresh items (last 24h)
- Generated 8 alerts ready for posting
- Updated `out/alerts_drafts.json`

### 3. ✅ Created Posting Script
**File:** `post_alerts_now.py`

Quick script to manually post alerts when GitHub Actions fails:
```bash
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"
python3 post_alerts_now.py
```

### 4. ✅ Redesigned UI to Light Mode
Transformed the entire frontend to clean, minimal design (Tree of Alpha style):
- Changed from dark (zinc-950) to light mode (white/gray-50)
- Simplified Header component (removed terminal styling)
- Redesigned LiveStream (clean list layout, subtle dividers)
- Updated CommandInput (simple search bar with filter chips)
- Changed fonts from monospace to sans-serif (Inter, Segoe UI)

**Deployed to:** https://fintech-news-mvp.vercel.app

---

## Current Status

### ✅ Ready to Post: 8 Alerts

1. **Superstate Raises $82.5 Million** - Tokenization platform funding
2. **Nomura's Laser Digital** - Tokenized Bitcoin yield fund (5% returns)
3. **AIXC Corporate Expansion** - AIxC Hub ecosystem growth
4. **Citi Ethereum Analysis** - Address poisoning scams identified
5. **Capital One Acquires Brex** - $5.15B fintech acquisition
6. **Capital One + Brex** - Stablecoin payment enabler deal
7. **Bitwise Bitcoin-Gold ETF** - Actively managed crypto ETF
8. **BitGo Raises $213M** - Crypto custodian IPO funding

All alerts are in `out/alerts_drafts.json` with proper HTML formatting.

---

## Next Steps (Required)

### 1. Fix GitHub Actions (Priority 1)

**Check Workflow Status:**
```bash
# Go to: https://github.com/0xhackit/fintechnewsbot/actions
# Look for "Auto-Publish Alerts" workflow
# Check if it's running or has errors
```

**Verify Secrets:**
Go to: `GitHub Repo → Settings → Secrets and variables → Actions`

Required secrets:
- `TG_API_ID` - Telegram API ID from https://my.telegram.org
- `TG_API_HASH` - Telegram API hash
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `TELEGRAM_CHAT_ID` - Your group chat ID (starts with -)

**Test Manually:**
```bash
# Trigger workflow manually
gh workflow run alerts_auto_publish.yml
```

### 2. Post Current Alerts (Priority 2)

**Option A: Use the script**
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
python3 post_alerts_now.py
```

**Option B: Via GitHub Actions**
```bash
# If secrets are configured, manually trigger the workflow
gh workflow run alerts_auto_publish.yml --ref main
```

### 3. Monitor Going Forward

Once GitHub Actions is fixed:
- Workflow runs every 5 minutes automatically
- Fresh news fetched daily at 08:00 UTC
- Alerts auto-posted to Telegram
- State tracked in `state/seen_alerts.json`

**Check logs:**
```bash
# View recent workflow runs
gh run list --workflow=alerts_auto_publish.yml --limit 5

# View specific run logs
gh run view <run_id> --log
```

---

## Configuration Reference

### Alert Thresholds
```python
MIN_ALERT_SCORE = 35        # Minimum score to post (was 50)
SIMILARITY_THRESHOLD = 0.75  # 75% similar = duplicate
EXCLUDE_TELEGRAM_SOURCES = True  # Wait for news coverage
```

### Scoring System
```python
# Tier 1 patterns: 25 points each (max 60)
# - "launches", "raises $X", "acquires", "partnership"

# Tier 2 patterns: 10 points each (max 30)
# - "pilot", "expands", "integrates"

# Penalties:
# - Commentary: -20 per pattern (max -50)
# - Listicle: -100 per pattern (max -200)
# - Generic: -50 per pattern (max -100)
# - Telegram: -15 vs RSS articles

# Bonuses:
# - Freshness: +10 (<6h), +4 (<24h)
```

### Config Settings
```json
{
  "alerts": {
    "auto_approve": true,
    "post_to_telegram": true,
    "post_to_x": false,
    "min_score_for_telegram": 35,
    "exclude_telegram_sources": true
  }
}
```

---

## Files Changed

### Core Fixes
- `scripts/run_alerts.py` - Lowered MIN_ALERT_SCORE to 35
- `post_alerts_now.py` - New manual posting script
- `TELEGRAM_ALERT_RULES.md` - Documentation
- `out/alerts_drafts.json` - 8 ready-to-post alerts
- `state/seen_alerts.json` - Updated state (107 seen items)

### UI Redesign (Light Mode)
- `frontend/src/index.css` - Light mode colors, fonts
- `frontend/src/components/Header.jsx` - Minimal header
- `frontend/src/components/LiveStream.jsx` - Clean list layout
- `frontend/src/components/CommandInput.jsx` - Simple search bar
- `frontend/src/pages/Terminal.jsx` - Light mode wrapper
- `frontend/src/pages/Landing.jsx` - New landing page
- `frontend/src/App.jsx` - Router setup

---

## Testing

### Local Test
```bash
# 1. Fetch fresh news
python3 run.py

# 2. Generate alerts
python3 scripts/run_alerts.py --mode prepare

# 3. Check output
cat out/alerts_drafts.json | jq '.[] | .title'

# 4. Post to Telegram (with your credentials)
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python3 post_alerts_now.py
```

### Verify on Telegram
After posting, you should see 8 messages in your Telegram group with:
- Bold headlines
- Clickable "..." links
- HTML formatting preserved

---

## Troubleshooting

### Problem: No drafts generated
```bash
# Check items
cat out/items_last24h.json | jq 'length'  # Should be > 0

# Check scores
cat out/items_last24h.json | jq '.[] | .score' | sort -rn | head -10
```

### Problem: Telegram posting fails
```bash
# Test bot connection
python3 -c "
import asyncio
from telegram import Bot
bot = Bot(token='YOUR_TOKEN')
asyncio.run(bot.get_me())
"

# Test chat access
python3 -c "
import asyncio
from telegram import Bot
bot = Bot(token='YOUR_TOKEN')
asyncio.run(bot.send_message(chat_id='YOUR_CHAT_ID', text='Test'))
"
```

### Problem: GitHub Action still not running
1. Check if Actions are enabled: `Settings → Actions → General → Allow all actions`
2. Check workflow permissions: `Settings → Actions → General → Workflow permissions → Read and write`
3. Check secrets are set: `Settings → Secrets and variables → Actions`
4. View workflow file: `.github/workflows/alerts_auto_publish.yml`

---

## Summary

**What Was Broken:**
- GitHub Actions workflow not running for 2 days
- Alert threshold too high (50), missing quality stories

**What's Fixed:**
- ✅ Lowered threshold to 35
- ✅ Generated 8 fresh alerts
- ✅ Created manual posting script
- ✅ Redesigned UI to clean light mode

**What You Need to Do:**
1. Fix GitHub Actions (check secrets and workflow status)
2. Post the 8 generated alerts using `post_alerts_now.py`
3. Monitor that automated posting resumes

**Files to Check:**
- `out/alerts_drafts.json` - 8 alerts ready
- `post_alerts_now.py` - Posting script
- `.github/workflows/alerts_auto_publish.yml` - Workflow definition
