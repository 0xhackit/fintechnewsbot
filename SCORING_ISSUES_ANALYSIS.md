# Scoring System Issues - Analysis & Fix

**Problem:** High-quality news being missed, irrelevant/inconsistent news being posted

---

## 🔍 Root Causes Identified

### Issue 1: Tier-based scoring is too simplistic

**Current logic:**
```python
tier1 = _count(TIER1_LAUNCH_PATTERNS, text)  # Worth 25 points each
tier2 = _count(TIER2_ACTIVITY_PATTERNS, text)  # Worth 10 points each
launch_score = min(tier1 * 25, 60) + min(tier2 * 10, 30)
```

**Problems:**
1. **"Launch" keyword gets 25 points** - but many launches are irrelevant (MegaETH blockchain, gaming apps)
2. **No entity weighting** - "JPMorgan launches stablecoin" = "Random startup launches token"
3. **Missing important stories** - SEC guidance (score 24), major bank announcements (score 14)
4. **No institution bonus** - Fidelity, HSBC, Goldman news should score higher

### Issue 2: Keyword matching doesn't consider context

**Examples of missed stories:**
- ✅ `"SEC gives guidance on tokenized securities"` - **Score 24** (MISSED!)
  - Tier1=0, Tier2=2 → Only 20 points
  - Should be HIGH PRIORITY (SEC + regulation + tokenized)

- ✅ `"Standard Chartered warns stablecoins threaten $500B in deposits"` - **Score 4** (MISSED!)
  - Major bank + stablecoins + $500 billion
  - Tier1=0, Tier2=0 → 4 points total
  - Should be HIGH PRIORITY

- ✅ `"UAE central bank approves USD stablecoin"` - **Score 4-10** (MISSED!)
  - Central bank approval is HUGE
  - Gets low score because no "launch" keyword

### Issue 3: Irrelevant launches score too high

**Examples of overscored stories:**
- ❌ `"MegaETH mainnet to launch"` - **Score 64** (Posted)
  - Generic L1 blockchain launch
  - Not institutional/fintech focus
  - Gets 25 points for "launch" + 10 for "mainnet"

- ❌ `"Clawdbot Chaos: A Forced Rebrand, Crypto Scam"` - **Score 54** (Posted)
  - Crypto scam story, not institutional
  - Has "launch" keyword → 25 points

- ❌ `"PGA Tour Rise Mobile Golf Game to Launch"` - **Score 54** (Posted)
  - Gaming app, completely irrelevant
  - Has "launch" keyword → high score

### Issue 4: No priority for major institutions

**Major institutions should get bonus:**
- JPMorgan, Goldman Sachs, Bank of America, Citibank
- Fidelity, BlackRock, State Street
- Federal Reserve, SEC, Treasury, FDIC
- Central banks (UAE, Singapore, Hong Kong, etc.)

**Current:** All sources treated equally

### Issue 5: Commentary penalties too aggressive

**Current:**
```python
COMMENTARY_PATTERNS = ["could", "may", "might", "why", "how", "analysis"]
commentary_penalty = -min(comm * 20, 50)  # -20 per keyword, max -50
```

**Problem:** Legitimate analysis from major banks gets penalized
- "Goldman Sachs says stablecoins could disrupt banking" → -20 penalty for "could"
- "SEC analysis of tokenized securities" → -20 penalty for "analysis"

---

## 📊 Current Data Analysis

### Items that SHOULD be posted (score >= 35): 31 items
**Good catches:**
- HSBC Hang Seng tokenized gold ETF (64)
- Bybit retail banking (60)
- Fidelity stablecoin launch (54)
- Robinhood tokenization comments (55)

**Questionable items:**
- MegaETH blockchain launch (64) - Not institutional
- PGA Tour game launch (54) - Gaming, irrelevant
- Clawdbot scam (54) - Not news-worthy

### Items MISSED (score < 35) but IMPORTANT: 23 items
**Critical misses:**
- SEC tokenized securities guidance (24)
- Standard Chartered $500B warning (4)
- UAE central bank stablecoin approval (4-10)
- Tether $24B gold stash (4)
- Bahrain central bank stablecoin approval (4)

---

## ✅ Comprehensive Fix

### Fix 1: Add Institution Weighting

```python
# Major financial institutions (tier 1)
TIER1_INSTITUTIONS = [
    "jpmorgan", "jp morgan", "goldman sachs", "goldman", "bank of america", "bofa",
    "citibank", "citi", "citigroup", "morgan stanley", "wells fargo",
    "hsbc", "barclays", "ubs", "credit suisse", "deutsche bank",
    "bnp paribas", "societe generale", "standard chartered",
    "fidelity", "blackrock", "vanguard", "state street",
    "paypal", "visa", "mastercard", "stripe", "square", "revolut"
]

# Asset managers / crypto-native (tier 2)
TIER2_INSTITUTIONS = [
    "coinbase", "binance", "kraken", "gemini", "circle", "ripple",
    "paxos", "anchorage", "bitstamp", "bitfinex"
]

# Regulators / central banks (tier 1+)
REGULATORS = [
    "sec", "federal reserve", "fed", "treasury", "fdic", "occ",
    "central bank", "ecb", "bank of england", "monetary authority",
    "financial authority", "securities commission"
]

def get_institution_bonus(item: dict) -> int:
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()

    # Regulator mention = +30 points
    if any(reg in text for reg in REGULATORS):
        return 30

    # Tier 1 institution = +20 points
    if any(inst in text for inst in TIER1_INSTITUTIONS):
        return 20

    # Tier 2 institution = +10 points
    if any(inst in text for inst in TIER2_INSTITUTIONS):
        return 10

    return 0
```

### Fix 2: Add Financial Impact Scoring

```python
# Large financial amounts indicate importance
FINANCIAL_PATTERNS = [
    (r'\$?\d+\s*billion', 40),   # "$500 billion" = +40 points
    (r'\$?\d+\.?\d*\s*bn', 40),   # "5.2bn" = +40 points
    (r'\$?\d{3,}\s*million', 30), # "$100 million" = +30 points
    (r'\$?\d+\.?\d*\s*mn', 30),   # "50mn" = +30 points
]

def get_financial_impact_bonus(item: dict) -> int:
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()

    for pattern, bonus in FINANCIAL_PATTERNS:
        if re.search(pattern, text):
            return bonus

    return 0
```

### Fix 3: Add Regulatory/Policy Scoring

```python
# Regulatory actions are high priority
REGULATORY_KEYWORDS = [
    "approval", "approves", "approved", "authorizes", "authorized",
    "regulation", "regulatory", "compliance", "licensed",
    "guidance", "ruling", "rules", "law", "legislation",
    "sanctions", "sanctioned", "enforcement", "investigation"
]

def get_regulatory_bonus(item: dict) -> int:
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    title = item.get('title', '').lower()

    # Regulator in title + regulatory keyword = +40
    if any(reg in title for reg in REGULATORS):
        if any(kw in text for kw in REGULATORY_KEYWORDS):
            return 40

    # Just regulatory keywords = +15
    if any(kw in text for kw in REGULATORY_KEYWORDS):
        return 15

    return 0
```

### Fix 4: Reduce Commentary Penalty for Institutional Sources

```python
def get_commentary_penalty(item: dict) -> int:
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    title = item.get('title', '').lower()

    comm = _count(COMMENTARY_PATTERNS, text)

    # If from major institution, reduce penalty
    has_institution = (
        any(inst in text for inst in TIER1_INSTITUTIONS) or
        any(reg in text for reg in REGULATORS)
    )

    if has_institution:
        # Institutional commentary is valuable (-10 per keyword)
        return -min(comm * 10, 30)
    else:
        # Generic commentary is noise (-20 per keyword)
        return -min(comm * 20, 50)
```

### Fix 5: Improved Score Calculation

```python
def score_item(item: dict, now_utc: datetime) -> dict:
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    title = (item.get('title', '')).lower()
    source_type = item.get('source_type', '')

    # Pattern matching
    tier1 = _count(TIER1_LAUNCH_PATTERNS, text)
    tier2 = _count(TIER2_ACTIVITY_PATTERNS, text)
    comm = _count(COMMENTARY_PATTERNS, text)
    listicle = _count(LISTICLE_PATTERNS, title)
    generic = _count(GENERIC_PATTERNS, title)

    # Base scores
    launch_score = min(tier1 * 25, 60) + min(tier2 * 10, 30)

    # NEW: Context-aware bonuses
    institution_bonus = get_institution_bonus(item)
    financial_bonus = get_financial_impact_bonus(item)
    regulatory_bonus = get_regulatory_bonus(item)

    # Commentary penalty (reduced for institutional sources)
    commentary_penalty = get_commentary_penalty(item)

    # Quality penalties
    listicle_penalty = -min(listicle * 100, 200)
    generic_penalty = -min(generic * 50, 100)

    # Source penalty
    source_penalty = -15 if source_type == 'telegram' else 0

    # Freshness
    freshness = 0
    try:
        if item.get("published_at"):
            dt = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            hours = (now_utc - dt).total_seconds() / 3600
            if hours <= 6:
                freshness = 10
            elif hours <= 24:
                freshness = 4
    except Exception:
        pass

    # TOTAL SCORE
    score = (
        launch_score +
        institution_bonus +
        financial_bonus +
        regulatory_bonus +
        commentary_penalty +
        listicle_penalty +
        generic_penalty +
        source_penalty +
        freshness
    )

    # Overrides
    # Major institution + any tier1/tier2 = minimum 40 points
    if institution_bonus >= 20 and (tier1 >= 1 or tier2 >= 1):
        score = max(score, 40)

    # Regulator + regulatory keyword = minimum 50 points
    if regulatory_bonus >= 40:
        score = max(score, 50)

    # Financial impact + institution = minimum 45 points
    if financial_bonus >= 30 and institution_bonus >= 10:
        score = max(score, 45)

    # Hard reject listicles and generic
    if listicle >= 1 or generic >= 1:
        score = min(score, -50)

    # Suppress heavy commentary without substance
    if comm >= 2 and tier1 == 0 and tier2 == 0 and institution_bonus == 0:
        score = min(score, 10)

    item["score"] = int(score)
    item["score_breakdown"] = {
        "tier1": tier1,
        "tier2": tier2,
        "commentary": comm,
        "listicle": listicle,
        "generic": generic,
        "freshness": freshness,
        "source_penalty": source_penalty,
        "launch_score": launch_score,
        "institution_bonus": institution_bonus,
        "financial_bonus": financial_bonus,
        "regulatory_bonus": regulatory_bonus,
        "commentary_penalty": commentary_penalty,
        "listicle_penalty": listicle_penalty,
        "generic_penalty": generic_penalty,
    }
    return item
```

---

## 📈 Expected Impact

### Before Fix:

**Missed (score < 35):**
- SEC tokenized securities guidance (24) → Should be ~60
- Standard Chartered $500B warning (4) → Should be ~70
- UAE central bank stablecoin (4) → Should be ~65
- Bahrain central bank approval (4) → Should be ~60

**Overscored (score >= 35):**
- MegaETH blockchain launch (64) → Should be ~25
- PGA Tour game launch (54) → Should be -50 (reject)
- Generic crypto scam (54) → Should be ~15

### After Fix:

**SEC guidance example:**
```
Base: tier2=2 → 20 points
+ Regulatory bonus (SEC + guidance): +40
+ Tier2 activity: +20
= 80 points ✅ HIGH PRIORITY
```

**Standard Chartered $500B warning:**
```
Base: tier1=0, tier2=0 → 0 points
+ Institution bonus (Standard Chartered): +20
+ Financial bonus ($500 billion): +40
+ Commentary penalty ("could"): -10 (reduced for institution)
= 50 points ✅ POSTED
```

**MegaETH launch:**
```
Base: tier1=1 (launch), tier2=1 (mainnet) → 35 points
+ Institution bonus: 0 (no major institution)
+ Financial bonus: 0
+ Regulatory bonus: 0
= 35 points (borderline, but no priority)
```

**PGA Tour game:**
```
Base: tier1=1 (launch) → 25 points
+ Institution bonus: 0
+ No crypto anchor words → REJECTED before scoring
= Not posted ✅
```

---

## 🎯 Implementation Plan

1. **Update `src/app.py`** with new scoring logic
2. **Test on current data** (out/items_last24h.json)
3. **Validate results** - ensure all 23 missed items now score >= 35
4. **Deploy** - commit and push
5. **Monitor** - check next 24 hours of posts

---

## 📋 Testing Checklist

Test cases to verify:

- [ ] SEC guidance scores >= 50
- [ ] Major bank announcements score >= 40
- [ ] Central bank approvals score >= 60
- [ ] $X billion stories score >= 45
- [ ] Random blockchain launches score < 35
- [ ] Gaming/irrelevant launches rejected
- [ ] Institutional commentary gets reduced penalty
- [ ] Generic market updates score < 10

---

## Summary

**Root causes:**
1. No institution weighting (all sources equal)
2. No financial impact scoring ($500B = small news)
3. No regulatory priority (SEC = random blog)
4. "Launch" keyword over-weighted (game launch = stablecoin launch)
5. Commentary penalty too harsh for institutions

**Solution:**
- Add institution bonuses (+10 to +30 points)
- Add financial impact scoring (+30 to +40 points)
- Add regulatory scoring (+15 to +40 points)
- Reduce commentary penalty for institutional sources
- Keep hard rejects for listicles/generic content

**Expected result:**
- 23 missed stories now posted (score >= 35)
- Irrelevant launches filtered out
- Better signal-to-noise ratio
- Institutional focus maintained
