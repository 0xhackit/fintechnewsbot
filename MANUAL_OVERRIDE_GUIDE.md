# Manual Override System - Complete Guide

This guide explains how to view ALL scraped data and manually publish items that were filtered out by the automatic scoring system.

---

## Overview

Your alert system automatically filters items based on:
- **Score threshold**: Only items with score ≥35 are published
- **Deduplication**: Items marked as "seen" are skipped
- **Content quality**: Commentary, listicles, and generic news are filtered

Sometimes quality stories get filtered out due to low scores. The manual override system lets you:
1. **View all scraped data** (including filtered items)
2. **Force-publish specific items** (bypass score filter)
3. **Review why items were filtered** (see scores and keywords)

---

## Quick Start

### 1. View All Scraped Data

```bash
# Show summary statistics
python3 view_all_items.py --summary-only

# View all items (sorted by score, highest first)
python3 view_all_items.py

# View only filtered items (score < 35)
python3 view_all_items.py --status filtered

# View filtered items with scores 25-35
python3 view_all_items.py --status filtered --min-score 25
```

### 2. Force Publish Specific Items

```bash
# Dry run (preview without posting)
python3 force_publish.py --indices 1 2 3 --dry-run

# Actually post items by index
python3 force_publish.py --indices 1 2 3

# Post by item ID (from view_all_items.py output)
python3 force_publish.py --ids 3b0a15ffc69343dd bd4cf72757eeed0e
```

---

## Detailed Usage

### `view_all_items.py` - View and Filter Scraped Data

#### Basic Commands

```bash
# View all 39 items
python3 view_all_items.py

# Show only summary (no item details)
python3 view_all_items.py --summary-only

# Limit to first 10 results
python3 view_all_items.py --limit 10
```

#### Filter by Score

```bash
# Items with score 30-40 (near the threshold)
python3 view_all_items.py --min-score 30 --max-score 40

# High-score items (80+)
python3 view_all_items.py --min-score 80

# Very low-score items (<20)
python3 view_all_items.py --max-score 20
```

#### Filter by Status

```bash
# Only filtered items (score < 35)
python3 view_all_items.py --status filtered

# Only items that pass filter (score ≥35)
python3 view_all_items.py --status passes

# Only unseen items (not posted yet)
python3 view_all_items.py --status unseen

# Only seen items (already posted)
python3 view_all_items.py --status seen

# Only items in draft queue
python3 view_all_items.py --status draft
```

#### Filter by Topic

```bash
# Items about tokenization
python3 view_all_items.py --topic tokenized

# Items about stablecoins
python3 view_all_items.py --topic stablecoin

# Items about M&A
python3 view_all_items.py --topic "M&A"
```

#### Filter by Keyword

```bash
# Items mentioning "bitcoin"
python3 view_all_items.py --keyword bitcoin

# Items mentioning "acquisition"
python3 view_all_items.py --keyword acquisition

# Items mentioning "raises"
python3 view_all_items.py --keyword raises
```

#### Sorting

```bash
# Sort by score (default)
python3 view_all_items.py --sort score

# Sort by date (newest first)
python3 view_all_items.py --sort date

# Sort by title (alphabetical)
python3 view_all_items.py --sort title
```

#### Export IDs

```bash
# Export matching item IDs to a file
python3 view_all_items.py --status filtered --export-ids filtered_ids.json

# Then use with force_publish.py
python3 force_publish.py --ids-file filtered_ids.json --dry-run
```

#### Combine Filters

```bash
# Filtered items about tokenization with score 25-35
python3 view_all_items.py --status filtered --topic tokenized --min-score 25

# Unseen bitcoin items sorted by date
python3 view_all_items.py --status unseen --keyword bitcoin --sort date --limit 5
```

---

### `force_publish.py` - Manually Publish Items

#### Basic Commands

```bash
# Publish by index (1-based, from view_all_items.py)
python3 force_publish.py --indices 1 2 5

# Publish by item ID (full or partial)
python3 force_publish.py --ids 3b0a15ffc69343dd bd4cf72757eeed0e

# Publish from a file of IDs
python3 force_publish.py --ids-file selected_ids.json
```

#### Dry Run (Preview)

```bash
# Preview messages without posting
python3 force_publish.py --indices 1 2 --dry-run

# Preview shows:
# - Item titles and scores
# - Formatted Telegram message
# - No actual posting
# - No state updates
```

#### Advanced Options

```bash
# Post without marking as seen (can repost later)
python3 force_publish.py --indices 1 --no-mark-seen

# Useful for testing or temporary posts
```

#### Requirements

```bash
# Set environment variables first
export TELEGRAM_BOT_TOKEN="your_token_here"
export TELEGRAM_CHAT_ID="your_group_id_here"

# Then run force_publish.py
python3 force_publish.py --indices 1
```

---

## Common Workflows

### Workflow 1: Review and Publish Filtered Items

```bash
# Step 1: View filtered items near the threshold
python3 view_all_items.py --status filtered --min-score 25 --limit 10

# Step 2: Preview specific items
python3 force_publish.py --indices 1 3 5 --dry-run

# Step 3: Publish if they look good
python3 force_publish.py --indices 1 3 5
```

### Workflow 2: Find and Publish by Topic

```bash
# Step 1: Find items about a specific topic
python3 view_all_items.py --topic "M&A" --status filtered

# Step 2: Export matching IDs
python3 view_all_items.py --topic "M&A" --status filtered --export-ids ma_items.json

# Step 3: Review and publish
python3 force_publish.py --ids-file ma_items.json --dry-run
python3 force_publish.py --ids-file ma_items.json
```

### Workflow 3: Daily Review of All Scraped Data

```bash
# Step 1: Check summary
python3 view_all_items.py --summary-only

# Step 2: Review high-score filtered items (28-35)
python3 view_all_items.py --status filtered --min-score 28

# Step 3: Publish worthy items
python3 force_publish.py --indices [indices from step 2]
```

---

## Understanding the Output

### `view_all_items.py` Output

```
================================================================================
[1] Score: 14 | ❌ FILTERED
Title: Stablecoin supply growth stalls as regulation, Treasury yields bite
Source: cointelegraph | Published: 2026-01-22
Topics: Stablecoin adoption
Keywords: stablecoin, issuance, regulation, compliance
URL: https://cointelegraph.com/news/stablecoin-supply-plateaus-regulation-treasury-yi...
ID: 3b0a15ffc69343dd...
================================================================================
```

**Fields explained:**
- **[1]**: Index number (use with `--indices` in force_publish.py)
- **Score: 14**: Relevance score (35 is threshold)
- **Status indicators**:
  - `❌ FILTERED` - Score below threshold
  - `✅ PASSES` - Score above threshold
  - `👁️ SEEN` - Already posted/seen
  - `📤 DRAFT` - In current draft queue
- **ID**: Use with `--ids` in force_publish.py (first 16 chars shown)

### Score Distribution Guide

- **80+**: High-priority (major announcements, big funding)
- **50-79**: Good quality (medium funding, partnerships)
- **35-49**: Passes threshold (interesting news)
- **25-35**: Borderline (might be worth manual review)
- **<25**: Low relevance (commentary, generic news)

---

## Examples

### Example 1: Find Interesting Filtered Stories

```bash
# View filtered items with scores 28-35 (just below threshold)
$ python3 view_all_items.py --status filtered --min-score 28 --limit 5

# Output shows borderline items that might be worth publishing
```

### Example 2: Publish All Bitcoin News

```bash
# Step 1: Find bitcoin items
$ python3 view_all_items.py --keyword bitcoin --export-ids bitcoin_items.json

# Step 2: Preview
$ python3 force_publish.py --ids-file bitcoin_items.json --dry-run

# Step 3: Publish
$ python3 force_publish.py --ids-file bitcoin_items.json
```

### Example 3: Review Yesterday's Filtered Items

```bash
# View all filtered items sorted by date
$ python3 view_all_items.py --status filtered --sort date --limit 20

# Manually select interesting ones by index
$ python3 force_publish.py --indices 2 5 7 12
```

---

## Configuration

### Environment Variables (Required for Posting)

```bash
# Telegram Bot Token (from @BotFather)
export TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

# Telegram Chat ID (group or channel)
export TELEGRAM_CHAT_ID="-1001234567890"
```

### Where Data Comes From

- **`out/items_last24h.json`**: All scraped items (39 total)
  - Generated by `python run.py`
  - Contains items from last 24 hours
  - Includes scores, topics, keywords

- **`state/seen_alerts.json`**: Tracking seen items
  - Prevents duplicate posts
  - Updated by auto-publish workflow
  - Can be manually edited if needed

- **`out/alerts_drafts.json`**: Current draft queue
  - Contains items ready to post (score ≥35)
  - Generated by `python scripts/run_alerts.py --mode prepare`
  - Posted by workflow or `post_alerts_now.py`

---

## Troubleshooting

### "No items file found"

**Problem**: `out/items_last24h.json` doesn't exist

**Solution**:
```bash
# Fetch fresh news first
python3 run.py
```

### "Missing environment variables"

**Problem**: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set

**Solution**:
```bash
# Set environment variables
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Or add to ~/.bashrc or ~/.zshrc
```

### "Failed to post: Forbidden"

**Problem**: Bot doesn't have permission to post in the group

**Solution**:
1. Make sure bot is added to the group
2. Make sure bot is an admin
3. Check that TELEGRAM_CHAT_ID is correct (starts with `-`)

### Items Show as "SEEN" but Weren't Posted

**Problem**: Items were marked as seen during testing/debugging

**Solution**:
```bash
# Option 1: Use --no-mark-seen flag
python3 force_publish.py --indices 1 --no-mark-seen

# Option 2: Remove from seen state (see below)
```

### Manually Edit Seen State

```bash
# View seen items
cat state/seen_alerts.json | jq '.seen | length'

# Remove specific IDs from seen state (use Python)
python3 -c "
import json
from pathlib import Path

state = json.loads(Path('state/seen_alerts.json').read_text())
# Remove specific ID
state['seen'] = [id for id in state['seen'] if not id.startswith('3b0a15ffc')]
state['seen_titles'] = [t for t in state['seen_titles'] if not t['id'].startswith('3b0a15ffc')]
Path('state/seen_alerts.json').write_text(json.dumps(state, indent=2))
"
```

---

## Tips

### Best Practices

1. **Always dry-run first**: Use `--dry-run` to preview before posting
2. **Review scores**: Items with score 25-35 are often borderline and worth reviewing
3. **Check topics**: Filter by topic to find niche stories your audience cares about
4. **Export IDs**: Use `--export-ids` to save interesting items for later
5. **Monitor summary**: Run `--summary-only` daily to see what's being scraped

### Score Interpretation

- **Score < 20**: Usually not worth publishing (commentary, generic news)
- **Score 20-30**: Might be interesting for specific topics
- **Score 30-35**: Borderline - review manually
- **Score 35-50**: Passes filter - already published automatically
- **Score 50+**: High quality - already published automatically

### Common Reasons for Low Scores

- **Commentary/opinion pieces**: -10 penalty
- **Listicles**: -10 penalty ("Top 5...", "Best 10...")
- **Generic content**: -10 penalty
- **Old news**: Freshness penalty after 24h
- **Few matched keywords**: Low tier1/tier2 scores

---

## Integration with Automatic System

### How the Scripts Work Together

1. **`run.py`**: Fetches news, generates `out/items_last24h.json` (39 items)
2. **`scripts/run_alerts.py`**: Filters items (score ≥35), generates `out/alerts_drafts.json` (8 items)
3. **`post_alerts_now.py`**: Posts drafts to Telegram, updates `state/seen_alerts.json`
4. **GitHub Actions**: Runs steps 1-3 automatically every 5 minutes

### Manual Override Fits In

- **`view_all_items.py`**: Shows ALL items from step 1 (including the 31 filtered items)
- **`force_publish.py`**: Posts specific items directly to Telegram (bypass step 2 filter)

### State Management

Both automatic and manual systems share the same state file (`state/seen_alerts.json`):
- Automatic system marks posted items as "seen"
- Manual system can also mark items as "seen" (or skip with `--no-mark-seen`)
- Both systems respect "seen" status to prevent duplicates

---

## Summary

### Quick Reference

```bash
# View filtered items worth reviewing
python3 view_all_items.py --status filtered --min-score 25 --limit 10

# Preview specific items before posting
python3 force_publish.py --indices 1 2 3 --dry-run

# Post specific items
python3 force_publish.py --indices 1 2 3

# Find and publish by topic
python3 view_all_items.py --topic tokenized --export-ids tokens.json
python3 force_publish.py --ids-file tokens.json
```

### Files You Need to Know

- **`out/items_last24h.json`**: All scraped data (39 items)
- **`out/alerts_drafts.json`**: Filtered items ready to post (8 items)
- **`state/seen_alerts.json`**: Tracking to prevent duplicates
- **`view_all_items.py`**: View and filter all items
- **`force_publish.py`**: Manually publish specific items

### Help

```bash
# View help for each script
python3 view_all_items.py --help
python3 force_publish.py --help
```

---

**🎉 You now have full control over your news pipeline!**

Use `view_all_items.py` to review all scraped data, and `force_publish.py` to manually publish worthy stories that were filtered out.
