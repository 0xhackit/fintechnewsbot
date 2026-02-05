# Scoring & Deduplication System - How It Works

## Overview

Your bot has **two separate deduplication systems** that work at different stages:

1. **Pipeline deduplication** (`src/dedupe.py`) - Runs during `python run.py`
2. **Alert deduplication** (`scripts/run_alerts.py`) - Runs during alert preparation

**The problem:** These systems work differently, and the alert deduplication only checks against **previously posted items**, not against **items in the current batch**.

---

## Current Flow

### Stage 1: News Fetching (`python run.py`)

```
1. Fetch from RSS feeds → 500+ raw items
2. Normalize & match keywords → ~200 matched items
3. Filter noise & crypto anchors → ~100 relevant items
4. Hard dedupe (exact URL matching) → ~80 unique items
5. Score each item → scored items
6. Cluster & soft dedupe (82% similar) → ~60 clustered items
   └─> Picks 1 representative per cluster
7. Save to out/items_last24h.json
```

**Output:** `out/items_last24h.json` with deduplicated items

### Stage 2: Alert Preparation (`python scripts/run_alerts.py --mode prepare`)

```
1. Load from out/items_last24h.json → ~60 items
2. Filter: score >= 35 → ~30 items pass
3. Check against state/seen_alerts.json
   └─> For each item:
       - Is it in seen list? Skip
       - Is it similar to previously seen title? Skip
       - Otherwise: ADD TO DRAFTS
4. Save to out/alerts_drafts.json
5. Mark as "seen" in state/seen_alerts.json
```

**Output:** `out/alerts_drafts.json` with items to post

---

## The Duplicate Problem

### Issue: Cluster Deduplication Threshold Too High

**Setting:** `sim_threshold = 0.82` (82% Jaccard similarity required)

**What this means:**
- Uses Jaccard similarity on normalized title tokens
- Only clusters if **82%+ of words match**
- **Too strict** - misses semantic duplicates

**Example that FAILS to cluster:**
```
Title 1: "Fidelity's stablecoin FIDD goes live for retail investors"
Tokens: {fidelity, stablecoin, fidd, goes, live, retail, investors}

Title 2: "Fidelity Investments announces launch of stablecoin FIDD"
Tokens: {fidelity, investments, announces, launch, stablecoin, fidd}

Jaccard similarity: 3 shared / 10 total = 0.30 (30%)
Result: NOT clustered (need 82%)
```

Both stories get posted!

### Why 6 Fidelity Stories Were Posted

Let's analyze the actual titles:

1. "Fidelity Investments Prepares Stablecoin Launch..."
2. "Banks may lose $500B after Fidelity's token launches..."
3. "Fidelity plans to launch a stablecoin"
4. "Fidelity Investments Announces Launch of Stablecoin (FIDD)"
5. "Fidelity's stablecoin FIDD goes live..."
6. "FIDELITY INVESTMENTS® EXPANDS DIGITAL ASSET..."

**Jaccard similarity between these:**
- #1 vs #3: ~40% (different wording)
- #1 vs #4: ~45% (different wording)
- #4 vs #5: ~35% (different wording)
- All below 82% threshold!

**Result:** Each creates its own cluster, all get posted

---

## How Deduplication SHOULD Work

### Option 1: Lower Cluster Threshold (Quick Fix)

**Change in `src/dedupe.py` line 165:**
```python
# OLD
def cluster_and_select(items, now_utc=None, sim_threshold: float = 0.82):

# NEW
def cluster_and_select(items, now_utc=None, sim_threshold: float = 0.60):
```

**Effect:**
- 60% similarity instead of 82%
- More aggressive clustering
- Fidelity stories would cluster together

**Trade-off:**
- Might over-cluster different stories
- Could miss legitimately different news

### Option 2: Entity-Based Clustering (Better)

Add entity extraction to clustering:

```python
def cluster_and_select(items, now_utc=None, sim_threshold: float = 0.70):
    """Enhanced clustering with entity awareness."""

    enriched = []
    for it in items:
        tok = _tokenize(it.get("title") or "")
        entity = extract_main_entity(it.get("title") or "")
        enriched.append((it, tok, entity))

    clusters = []
    for it, tok, entity in enriched:
        placed = False
        for cl in clusters:
            rep_tok = cl[0][1]
            rep_entity = cl[0][2]

            # If same entity + similar enough → cluster
            if entity and rep_entity and entity == rep_entity:
                if _jaccard(tok, rep_tok) >= 0.50:  # Lower threshold for same entity
                    cl.append((it, tok, entity))
                    placed = True
                    break
            # Different entities → higher threshold
            elif _jaccard(tok, rep_tok) >= sim_threshold:
                cl.append((it, tok, entity))
                placed = True
                break

        if not placed:
            clusters.append([(it, tok, entity)])

    # ... rest of clustering logic
```

**Effect:**
- "Fidelity" stories cluster at 50% similarity
- Different companies need 70% similarity
- Best of both worlds

### Option 3: Time-Based Clustering (Safest)

Cluster stories about the same entity within a time window:

```python
def cluster_and_select(items, now_utc=None, sim_threshold: float = 0.70):
    """Time-aware clustering."""

    # Sort by entity and published_at
    items_sorted = sorted(items, key=lambda x: (
        extract_main_entity(x.get("title", "")),
        x.get("published_at", "")
    ))

    clusters = []
    for it in items_sorted:
        entity = extract_main_entity(it.get("title", ""))
        pub_time = parse_time(it.get("published_at"))

        # Check if can join existing cluster
        placed = False
        for cl in clusters:
            rep = cl[0][0]
            rep_entity = extract_main_entity(rep.get("title", ""))
            rep_time = parse_time(rep.get("published_at"))

            # Same entity + within 48 hours + some similarity → cluster
            if entity == rep_entity:
                time_diff = abs((pub_time - rep_time).total_seconds() / 3600)
                if time_diff <= 48:  # Within 48 hours
                    tok = _tokenize(it.get("title", ""))
                    rep_tok = _tokenize(rep.get("title", ""))
                    if _jaccard(tok, rep_tok) >= 0.40:  # Very low threshold
                        cl.append((it, tok))
                        placed = True
                        break

        if not placed:
            clusters.append([(it, _tokenize(it.get("title", "")))])
```

**Effect:**
- Fidelity stories within 48 hours cluster together
- Even with low similarity (40%)
- Time-bounded to avoid over-clustering

---

## Recommended Fix

### Immediate (Quick Win)

**Lower the clustering threshold from 82% to 65%:**

```bash
# Edit src/dedupe.py line 165
sed -i '' 's/sim_threshold: float = 0.82/sim_threshold: float = 0.65/' src/dedupe.py
```

**Expected impact:**
- 6 Fidelity stories → 1-2 stories
- 2 CME stories → 1 story
- 2 SBI stories → 1 story

### Short-term (Better Quality)

**Implement entity-based clustering:**

1. Add entity extraction to `src/dedupe.py`
2. Use 50% threshold for same entity
3. Use 70% threshold for different entities

### Long-term (Best Solution)

**Implement time + entity clustering:**

1. Cluster by entity + time window (48 hours)
2. Very low similarity threshold (40%)
3. Prevents over-clustering while catching duplicates

---

## Current Deduplication Settings

### In `src/dedupe.py`

```python
# Hard dedupe (exact URL matching)
def hard_dedupe(items):
    # Removes exact URL duplicates
    # Works well, no issues

# Soft dedupe (title clustering)
def cluster_and_select(items, sim_threshold=0.82):  # ← TOO HIGH
    # Groups similar titles
    # Picks 1 representative per cluster
    # Applies consensus boost (+5 to +15 points)
```

### In `scripts/run_alerts.py`

```python
# Alert-level deduplication
SIMILARITY_THRESHOLD = 0.75  # For standard stories
LAUNCH_STORY_THRESHOLD = 0.60  # For launch stories

# Checks against state/seen_alerts.json
# Only prevents re-posting PREVIOUSLY seen items
# Does NOT dedupe within current batch!
```

**The gap:**
- Pipeline clusters at 82% → Multiple Fidelity stories pass through
- Alert script checks at 75% → But only against old posts, not current batch
- Result: All Fidelity stories get posted

---

## Testing the Fix

### Test with current data:

```bash
# Before fix
python3 << 'EOF'
from src.dedupe import cluster_and_select
import json

items = json.loads(open('out/items_last24h.json').read())
fidelity_items = [i for i in items if 'fidelity' in i.get('title', '').lower()]

print(f"Fidelity items before clustering: {len(fidelity_items)}")
for item in fidelity_items:
    print(f"  - {item.get('title')}")

# Cluster with current threshold (0.82)
clustered = cluster_and_select(fidelity_items, sim_threshold=0.82)
print(f"\nAfter clustering (0.82): {len(clustered)} clusters")

# Cluster with lower threshold (0.65)
clustered_65 = cluster_and_select(fidelity_items, sim_threshold=0.65)
print(f"After clustering (0.65): {len(clustered_65)} clusters")

# Cluster with very low threshold (0.50)
clustered_50 = cluster_and_select(fidelity_items, sim_threshold=0.50)
print(f"After clustering (0.50): {len(clustered_50)} clusters")
EOF
```

---

## Recommended Action

### Step 1: Lower clustering threshold to 0.65

```bash
# Edit src/dedupe.py
sed -i '' 's/sim_threshold: float = 0.82/sim_threshold: float = 0.65/' src/dedupe.py
```

### Step 2: Test on current data

```bash
python run.py
cat out/items_last24h.json | jq '[.[] | select(.title | contains("Fidelity"))] | length'
# Should show 1-2 items instead of 6
```

### Step 3: Monitor for 24 hours

Check if:
- ✅ Duplicates are reduced
- ✅ Important different stories still get through
- ❌ Over-clustering (different stories blocked)

### Step 4: Fine-tune if needed

- Too many duplicates still? → Lower to 0.60
- Missing different stories? → Raise to 0.70

---

## Summary

**Current state:**
- ❌ 82% clustering threshold is too high
- ❌ 6 Fidelity stories posted (should be 1)
- ❌ 2 CME stories posted (should be 1)
- ❌ 2 SBI stories posted (should be 1)

**Root cause:**
- Jaccard similarity too strict
- Different wording = different clusters
- All pass through to alerts

**Quick fix:**
- Lower threshold to 65%
- Test for 24 hours
- Adjust as needed

**Better fix (future):**
- Add entity extraction
- Use different thresholds for same/different entities
- Time-bounded clustering

**Best fix (future):**
- Entity + time clustering
- Very low threshold for same entity + time
- Prevents all semantic duplicates
