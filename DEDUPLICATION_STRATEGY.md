# Deduplication Strategy for News Items

## Current Problem

Stories like "X bank launched a fund" appear multiple times from different sources, creating noise in the feed. We need better deduplication to catch these semantic duplicates while keeping genuinely different stories.

## Current System (run_alerts.py:scripts/run_alerts.py)

### How It Works Now

```python
SIMILARITY_THRESHOLD = 0.75  # 75% similarity to be considered duplicate

def normalize_title_for_comparison(title):
    - Lowercase
    - Remove source attribution (" - Reuters", " | Bloomberg")
    - Remove prefixes ("Breaking:", "Exclusive:")
    - Remove suffixes ("(updated)")
    - Normalize whitespace

def title_similarity(title1, title2):
    - Uses SequenceMatcher (longest common subsequence)
    - Returns 0.0 (completely different) to 1.0 (identical)
```

### Limitations

1. **Sequential matching only**: "Bank of America launches Bitcoin fund" vs "BofA launches BTC fund" = LOW similarity (different words, same story)

2. **No entity extraction**: Doesn't recognize that "JPMorgan", "JP Morgan", and "JPM" are the same entity

3. **No semantic understanding**: Can't tell that "launches fund" and "debuts new product" are the same event

4. **Single threshold**: 75% for everything - doesn't account for story type

5. **Limited history**: Only keeps last 100 seen titles (line 238-239)

## Recommended Solutions

### Option 1: Entity-Based Deduplication (Recommended)

Extract key entities and event types, then match on those:

**Key entities:**
- Company/bank names (normalize variations)
- Products (fund, ETF, platform, etc.)
- Actions (launch, debut, introduce, unveil, etc.)

**Example:**
```
Title 1: "JPMorgan launches Bitcoin ETF"
Title 2: "JP Morgan debuts BTC exchange-traded fund"

Extract:
  Entity: JPMorgan/JP Morgan → normalized: "jpmorgan"
  Action: launch/debut → normalized: "launch"
  Product: Bitcoin ETF/BTC ETF → normalized: "bitcoin_etf"

Match: jpmorgan + launch + bitcoin_etf = DUPLICATE ✓
```

**Implementation:**
- Add entity normalization dictionary
- Extract [Company] + [Action] + [Product] pattern
- Match on normalized tuple
- Keep stricter thresholds for non-launch stories

### Option 2: Two-Tier Similarity

Use different thresholds for different story types:

```python
# High-impact stories: stricter deduplication
if "launch" in title or "raises" in title or "acquires" in title:
    SIMILARITY_THRESHOLD = 0.60  # 60% = more aggressive dedup
else:
    SIMILARITY_THRESHOLD = 0.75  # 75% = current behavior
```

**Pros:** Simple, catches more duplicates for launch stories
**Cons:** Still misses semantic duplicates (JP Morgan vs JPMorgan)

### Option 3: Keyword Fingerprinting

Create a fingerprint from key terms:

```python
def extract_keywords(title):
    # Extract: company names, action verbs, product types
    keywords = set()

    # Companies (from known list or NER)
    if "jpmorgan" in title.lower() or "jp morgan" in title.lower():
        keywords.add("jpmorgan")

    # Actions
    for action in ["launch", "debut", "introduce", "unveil"]:
        if action in title.lower():
            keywords.add("launch_event")

    # Products
    for product in ["fund", "etf", "platform"]:
        if product in title.lower():
            keywords.add(product)

    return frozenset(keywords)

# If 80%+ keywords match = duplicate
```

**Pros:** Catches semantic duplicates, language-agnostic
**Cons:** Requires maintaining keyword lists

### Option 4: Hybrid Approach (Best)

Combine multiple signals:

```python
def is_duplicate(new_title, seen_titles):
    for seen in seen_titles:
        # Signal 1: Text similarity
        text_sim = title_similarity(new_title, seen)

        # Signal 2: Entity overlap
        entity_sim = entity_overlap(new_title, seen)

        # Signal 3: Event type match
        same_event_type = detect_event_type(new_title) == detect_event_type(seen)

        # Weighted score
        if same_event_type and (text_sim > 0.5 or entity_sim > 0.7):
            return True
        elif text_sim > 0.75:
            return True

    return False
```

## Quick Win Implementation

### Immediate Fix (5 minutes)

Add launch-specific deduplication to `run_alerts.py`:

```python
def is_launch_story(title: str) -> bool:
    """Check if title is about a product launch."""
    launch_keywords = ["launch", "launches", "launched", "debut", "debuts",
                       "introduce", "introduces", "unveil", "unveils"]
    return any(kw in title.lower() for kw in launch_keywords)

def extract_launch_entity(title: str) -> str | None:
    """Extract company/product from launch story."""
    # Simple extraction: first 2-3 words before launch keyword
    title_lower = title.lower()
    for kw in ["launch", "debut", "introduce", "unveil"]:
        if kw in title_lower:
            idx = title_lower.index(kw)
            # Get first ~30 chars before keyword
            entity = title[:idx].strip().split()[:3]
            return " ".join(entity).lower()
    return None

# In main loop, before similarity check:
if is_launch_story(title):
    entity = extract_launch_entity(title)

    # Check if we've seen a launch from this entity recently
    for seen in seen_titles[-50:]:  # Check last 50 titles
        if is_launch_story(seen.get("title", "")):
            seen_entity = extract_launch_entity(seen.get("title", ""))

            # If same entity launching something, very likely duplicate
            if entity and seen_entity and entity == seen_entity:
                skipped_similar += 1
                print(f"🔁 Duplicate launch: \"{title[:70]}...\"")
                print(f"   Previous: \"{seen.get('title', '')[:70]}...\"")
                continue
```

### Medium-Term Fix (1-2 hours)

Create entity normalization dictionary:

```python
ENTITY_ALIASES = {
    "jpmorgan": ["jp morgan", "jpmorgan chase", "jpm"],
    "bankofamerica": ["bank of america", "bofa", "boa"],
    "goldman": ["goldman sachs", "gs"],
    "blackrock": ["blackrock", "black rock"],
    # ... add more as needed
}

def normalize_entity(text: str) -> set:
    """Normalize company/entity names to canonical form."""
    text_lower = text.lower()
    normalized = set()

    for canonical, aliases in ENTITY_ALIASES.items():
        if any(alias in text_lower for alias in aliases):
            normalized.add(canonical)

    return normalized
```

### Long-Term Fix (Future Enhancement)

Use NLP library for entity extraction:

```python
import spacy

nlp = spacy.load("en_core_web_sm")

def extract_entities(title: str) -> set:
    """Extract named entities using NLP."""
    doc = nlp(title)
    return {ent.text.lower() for ent in doc.ents if ent.label_ in ["ORG", "PRODUCT"]}
```

## Configuration Options

Add to `config.json`:

```json
{
  "deduplication": {
    "similarity_threshold": 0.75,
    "launch_story_threshold": 0.60,
    "enable_entity_matching": true,
    "entity_match_threshold": 0.7,
    "seen_titles_limit": 100
  }
}
```

## Testing Strategy

1. **Create test cases** with known duplicates:
   ```
   "JPMorgan launches Bitcoin ETF"
   "JP Morgan debuts BTC exchange-traded fund"
   → Should match as duplicate

   "JPMorgan launches Bitcoin ETF"
   "Goldman Sachs launches Bitcoin ETF"
   → Should NOT match (different companies)
   ```

2. **Run on historical data** to measure:
   - False positives (good stories marked as duplicates)
   - False negatives (duplicates that got through)
   - Optimal threshold values

3. **A/B test** with different threshold values:
   - 0.60, 0.65, 0.70, 0.75
   - Measure quality of alerts

## Metrics to Track

- **Deduplication rate**: % of items caught as duplicates
- **False positive rate**: Good stories incorrectly filtered
- **User feedback**: Which duplicates still get through
- **Entity coverage**: % of launch stories with extracted entities

## Implementation Priority

1. **Immediate** (today): Add launch-specific deduplication
2. **This week**: Create entity alias dictionary for top 20 companies
3. **Next week**: Add two-tier similarity thresholds
4. **Future**: Integrate NLP entity extraction

## Example Scenarios

### Scenario 1: Multiple sources cover same launch

**Input:**
```
[theblock]    "Superstate raises $82.5M Series B for blockchain IPO platform"
[decrypt]     "Superstate Raises $82.5 Million in Series B Funding"
[coindesk]    "Crypto startup Superstate secures $82M Series B"
```

**Current behavior**: All 3 pass (similarity ~60-70%)
**Improved behavior**: First one passes, others marked as duplicate

### Scenario 2: Different companies, same event type

**Input:**
```
"JPMorgan launches Bitcoin ETF"
"Goldman Sachs launches Bitcoin ETF"
```

**Current behavior**: Both pass (low text similarity)
**Improved behavior**: Both pass (different entities) ✓

### Scenario 3: Same company, different products

**Input:**
```
"JPMorgan launches Bitcoin ETF in January"
"JPMorgan launches Ethereum fund in February"
```

**Current behavior**: Both pass (low similarity)
**Improved behavior**: Both pass (different products, different months) ✓

## Recommended Next Steps

1. Review current `items_last24h.json` for duplicate patterns
2. Identify top 20 companies/entities that appear most often
3. Implement quick win (launch-specific dedup)
4. Test on last week's data
5. Iterate based on results

## Code Locations

- **Deduplication logic**: `scripts/run_alerts.py` lines 84-116
- **Similarity threshold**: Line 17 (`SIMILARITY_THRESHOLD = 0.75`)
- **Normalization**: Lines 65-81 (`normalize_title_for_comparison`)
- **Seen titles storage**: Lines 224-229, 238-239

## Files to Modify

1. **`scripts/run_alerts.py`** - Add improved deduplication
2. **`config.json`** - Add deduplication settings (optional)
3. **Create `src/entity_matcher.py`** - Entity normalization logic (future)
4. **Create `data/entity_aliases.json`** - Company name mappings (future)
