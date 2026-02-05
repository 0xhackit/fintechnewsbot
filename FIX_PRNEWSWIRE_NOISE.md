# Fix: PRNewswire False Positives

## Problem

**Item posted:** "Aker Horizons ASA: Notice of Extraordinary General Meeting"
- URL: https://www.prnewswire.com/news-releases/aker-horizons-asa-notice-of-extraordinary-general-meeting-302679946.html
- **Not related to crypto/fintech at all** - just a corporate meeting notice
- Company liquidation announcement, nothing to do with blockchain

## Root Cause

The `prnewswire_fintech` RSS feed is including general corporate press releases that happen to be tagged as "financial technology" by PR Newswire's categorization system.

**Current feed:**
```
https://www.prnewswire.com/rss/financial-services-latest-news/financial-technology-latest-news-list.rss
```

This feed includes:
- ✅ Legitimate fintech news (Stripe, Plaid, etc.)
- ❌ Generic corporate announcements
- ❌ Earnings reports
- ❌ Executive appointments
- ❌ **General meetings / liquidations** ← This is what happened

## Why It Passed Filters

The item should have been blocked by:
1. **Keyword matching** - Should fail (no matched keywords)
2. **Crypto anchor check** - Should fail (no crypto keywords)
3. **Noise filter** - Might pass (not explicitly noise)

**Investigation needed**: Why did it pass through when it has:
- No matched keywords
- No crypto anchors
- No relevance to fintech

## Solutions

### Option 1: Remove PRNewswire Feed (Recommended)

**Pros:**
- Eliminates noise source completely
- Other feeds already cover major fintech news
- PRNewswire often duplicates news from other sources

**Cons:**
- Might miss some exclusive PR announcements

**Implementation:**
```json
// In config.json, remove this line:
"prnewswire_fintech": "https://www.prnewswire.com/rss/..."
```

### Option 2: Add Stricter PRNewswire Filtering

Add source-specific noise patterns for PR Newswire:

**In `src/app.py`:**
```python
PR_NEWSWIRE_NOISE = [
    "notice of extraordinary general meeting",
    "notice of annual general meeting",
    "notice of meeting",
    "earnings call",
    "quarterly results",
    "executive appointment",
    "appoints new",
    "announces leadership",
    "board of directors",
    "dividend announcement",
    "delisting",
    "liquidation",
]

def is_pr_newswire_noise(item: dict) -> bool:
    """Filter out generic PR Newswire corporate announcements."""
    if "prnewswire" not in item.get('url', '').lower():
        return False

    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    return any(pattern in text for pattern in PR_NEWSWIRE_NOISE)
```

**Then add check in main():**
```python
if is_pr_newswire_noise(m):
    continue
```

### Option 3: Require Crypto Anchors for ALL RSS Feeds

Currently crypto anchor check is bypassed for Telegram. Enforce it for all RSS:

**In `src/app.py` line 302:**
```python
# OLD: Only check non-Telegram sources
if (m.get("source_type") or "").lower() != "telegram":
    if not has_crypto_anchor(m):
        continue

# NEW: Check ALL sources except Telegram
if (m.get("source_type") or "").lower() == "google_news_rss":
    # Google News needs keyword matching OR crypto anchor
    if not (m.get("matched_keywords") or has_crypto_anchor(m)):
        continue
elif (m.get("source_type") or "").lower() != "telegram":
    # Direct RSS feeds MUST have crypto anchor
    if not has_crypto_anchor(m):
        continue
```

### Option 4: Whitelist Direct RSS Sources

Only allow crypto-focused direct RSS feeds, block general financial news:

**Allowed direct RSS (crypto-native):**
- coindesk.com
- cointelegraph.com
- decrypt.co
- theblock.co
- blockworks.co
- dlnews.com
- ledgerinsights.com

**Requires crypto anchor:**
- prnewswire.com
- techcrunch.com
- ft.com
- wsj.com
- finextra.com
- pymnts.com
- fintechfutures.com

## Recommended Fix

**Implement Option 1 + Option 2:**

1. **Remove PRNewswire feed** from `config.json`
2. **Add PR noise filter** as backup (in case we re-enable it later)

### Step 1: Remove from config.json

```bash
# Edit config.json, remove this line:
"prnewswire_fintech": "https://www.prnewswire.com/rss/financial-services-latest-news/financial-technology-latest-news-list.rss",
```

### Step 2: Add noise filter in src/app.py

Add after NOISE_PATTERNS definition:

```python
# PR Newswire-specific noise (corporate announcements)
PR_NEWSWIRE_NOISE = [
    "notice of extraordinary general meeting",
    "notice of annual general meeting",
    "notice of meeting",
    "earnings call",
    "quarterly results",
    "quarterly earnings",
    "financial results",
    "executive appointment",
    "appoints new",
    "announces appointment of",
    "announces leadership",
    "board of directors announces",
    "dividend announcement",
    "declares dividend",
    "delisting notice",
    "liquidation notice",
    "voluntary delisting",
    "annual shareholders meeting",
]

def is_pr_noise(item: dict) -> bool:
    """Filter out generic PR announcements."""
    url = item.get('url', '').lower()
    if "prnewswire" not in url and "businesswire" not in url:
        return False

    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    return any(pattern in text for pattern in PR_NEWSWIRE_NOISE)
```

Then add check in main() after is_noise() check:

```python
if is_noise(m):
    continue
if is_pr_noise(m):
    continue
```

## Testing

After fix, test with the problematic item:

```python
item = {
    "title": "Aker Horizons ASA: Notice of Extraordinary General Meeting",
    "snippet": "Board proposes liquidation and delisting",
    "url": "https://www.prnewswire.com/news-releases/aker-horizons-asa-notice-of-extraordinary-general-meeting-302679946.html"
}

# Should return True (is noise)
assert is_pr_noise(item) == True
```

## Implementation Priority

1. **Immediate**: Remove PRNewswire from config.json
2. **Short-term**: Add PR noise filter for safety
3. **Monitor**: Check if we're missing legitimate news from PR

## Expected Impact

- **Remove 1 noise source** (PRNewswire)
- **Reduce false positives** by ~5-10 items/day
- **No impact on important news** (other feeds cover the same stories)

## Other Potential Noise Sources

After fixing PRNewswire, also review:
- **TechCrunch fintech** - May include non-crypto startup news
- **PYMNTS** - Very broad fintech coverage
- **Fintech Futures** - General banking/fintech news

Consider adding similar noise filters or requiring crypto anchors for these.
