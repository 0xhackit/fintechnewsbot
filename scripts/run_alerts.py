#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher

# Ensure the project root is importable so `from src.ai_filter import ...` works
# when run from the project directory (e.g., `python scripts/run_alerts.py`)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

STATE_PATH = Path("state/seen_alerts.json")
DRAFTS_PATH = Path("out/alerts_drafts.json")
BLOCKLIST_PATH = Path("blocklist.json")

# Change this if your pipeline writes items elsewhere
ITEMS_PATH = Path("out/items_last24h.json")

# Minimum similarity threshold for considering titles as duplicates
# 0.0 = completely different, 1.0 = identical
SIMILARITY_THRESHOLD = 0.75

# Lower threshold for launch/funding stories (more aggressive dedup)
LAUNCH_STORY_THRESHOLD = 0.60

# Minimum score for an item to become an alert
# Items with score below this threshold will be filtered out
MIN_ALERT_SCORE = 35  # Lowered to 35 to catch more quality stories (funding, launches, etc.)

# Exclude Telegram sources from alerts (wait for news article coverage)
EXCLUDE_TELEGRAM_SOURCES = True

# ---------------------------------------------------------------------------
# AI Filter toggle: set to True to enable AI classification + SQLite dedup.
# Requires ANTHROPIC_API_KEY environment variable.
# When disabled, the pipeline works exactly as before.
# ---------------------------------------------------------------------------
ENABLE_AI_FILTER = bool(os.environ.get("ANTHROPIC_API_KEY"))


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_blocklisted(item: dict) -> tuple[bool, str]:
    """Check if an item matches any blocklist rule. Returns (blocked, reason)."""
    blocklist = load_json(BLOCKLIST_PATH, {"blocked_urls": [], "blocked_keywords": [], "blocked_sources": []})

    item_url = (item.get("link") or item.get("url") or "").strip()
    if item_url in blocklist.get("blocked_urls", []):
        return True, f"blocked URL: {item_url}"

    title_lower = (item.get("title") or "").lower()
    for keyword in blocklist.get("blocked_keywords", []):
        if keyword.lower() in title_lower:
            return True, f"blocked keyword: {keyword}"

    source = (item.get("source") or "").strip()
    if source in blocklist.get("blocked_sources", []):
        return True, f"blocked source: {source}"

    return False, ""


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def stable_item_id(item: dict) -> str:
    title = (item.get("title") or "").strip().lower()
    link = (item.get("link") or item.get("url") or "").strip().lower()
    base = f"{title}|{link}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def has_date(item: dict) -> bool:
    # support either published_at or published fields (depending on your pipeline)
    return bool(item.get("published_at") or item.get("published"))


def clean_title(title: str) -> str:
    t = (title or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def build_message_html(title: str, link: str) -> str:
    # Telegram HTML formatting: bold + ... anchor
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_link = link.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<b>{safe_title}</b> <a href=\"{safe_link}\">...</a>"


def normalize_title_for_comparison(title: str) -> str:
    """
    Normalize title for similarity comparison by removing common variations.
    """
    t = title.lower().strip()

    # Remove source attribution (e.g., " - Reuters", " | Bloomberg")
    t = re.sub(r'\s*[-|]\s*[a-z\s]+$', '', t)

    # Remove common prefixes/suffixes
    t = re.sub(r'^(breaking|exclusive|alert|update):\s*', '', t)
    t = re.sub(r'\s*\(updated\)$', '', t)

    # Normalize whitespace
    t = re.sub(r'\s+', ' ', t).strip()

    return t


def title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity between two titles (0.0 to 1.0).
    Uses SequenceMatcher to find longest common subsequence.
    """
    norm1 = normalize_title_for_comparison(title1)
    norm2 = normalize_title_for_comparison(title2)

    return SequenceMatcher(None, norm1, norm2).ratio()


# ---------------------------------------------------------------------------
# Token-based (Jaccard) similarity — catches paraphrased duplicates that
# SequenceMatcher misses (e.g., "CME launches 24/7 crypto futures" vs
# "CME targets May launch for 24/7 crypto derivatives trading")
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "as", "by", "from", "at", "is", "are", "was", "were", "be", "been",
    "being", "it", "its", "this", "that", "these", "those", "after",
    "before", "into", "over", "under", "about", "amid", "says", "said",
    "report", "reports", "new", "will", "has", "have", "had", "not", "but",
    "than", "more", "up", "out", "also", "could", "may", "can",
}


def _tokenize_title(title: str) -> set[str]:
    """Tokenize a title into meaningful words (lowercase, no stopwords, no short words)."""
    t = normalize_title_for_comparison(title)
    t = re.sub(r"[^a-z0-9/\s]", " ", t)  # keep / for things like 24/7
    tokens = {w for w in t.split() if w and w not in _STOPWORDS and len(w) > 2}
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity: |intersection| / |union|."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Known entity names — used for entity-based dedup. When two titles mention
# the same entity and have overlapping keywords, they're likely the same story.
# ---------------------------------------------------------------------------

_KNOWN_ENTITIES = [
    "jpmorgan", "jp morgan", "goldman sachs", "goldman", "bank of america",
    "citigroup", "citi", "morgan stanley", "wells fargo", "hsbc",
    "barclays", "ubs", "deutsche bank", "bnp paribas", "standard chartered",
    "blackrock", "fidelity", "vanguard", "state street", "franklin templeton",
    "paypal", "visa", "mastercard", "stripe", "square", "block", "revolut",
    "wise", "plaid", "marqeta", "adyen", "checkout.com", "klarna", "affirm",
    "coinbase", "binance", "kraken", "gemini", "circle", "ripple",
    "paxos", "anchorage", "anchorage digital", "bitstamp", "bybit", "okx",
    "tether", "robinhood", "sofi", "brex",
    "cme", "cme group", "sec", "cftc", "fed", "federal reserve",
    "payoneer", "grab", "wirex",
]


def extract_entities(title: str) -> set[str]:
    """
    Extract all known entities mentioned in a title.
    Returns a set of canonical entity names.
    """
    t = title.lower()
    found = set()
    # Check longest names first to avoid partial matches
    for entity in sorted(_KNOWN_ENTITIES, key=len, reverse=True):
        if entity in t:
            # Use the shortest canonical form (e.g., "cme" not "cme group")
            found.add(entity.split()[0])
    return found


def get_event_type(title: str) -> str | None:
    """
    Determine the event type from a title.
    Returns: 'launch', 'funding', 'acquisition', or None
    """
    title_lower = title.lower()

    # Launch keywords
    if any(kw in title_lower for kw in ["launch", "launches", "launched", "launching",
                                         "debut", "debuts", "debuted",
                                         "introduce", "introduces", "introduced",
                                         "unveil", "unveils", "unveiled",
                                         "release", "releases", "released"]):
        return "launch"

    # Funding keywords
    if any(kw in title_lower for kw in ["raises", "raised", "raise", "raising",
                                        "funding", "funds", "funded",
                                        "investment", "invests", "invested",
                                        "series a", "series b", "series c",
                                        "seed round", "round"]):
        return "funding"

    # M&A keywords
    if any(kw in title_lower for kw in ["acquires", "acquired", "acquisition",
                                        "merger", "merges", "merged",
                                        "buys", "bought", "purchase"]):
        return "acquisition"

    return None


def is_launch_or_funding_story(title: str) -> bool:
    """
    Check if title is about a product launch, funding round, or M&A.
    These stories are especially prone to duplicates across sources.
    """
    return get_event_type(title) is not None


def extract_key_entity(title: str) -> str:
    """
    Extract the primary company/entity from a title.
    Simple extraction: get first 2-3 words (usually the company name).
    """
    # Remove common prefixes
    t = re.sub(r'^(breaking|exclusive|alert|update):\s*', '', title, flags=re.IGNORECASE)

    # Get first few words (likely company name)
    words = t.strip().split()[:3]

    # Normalize to lowercase for comparison
    return " ".join(words).lower()


def normalize_entity_name(entity: str) -> str:
    """
    Normalize company/entity names to catch variations.
    E.g., "JP Morgan" vs "JPMorgan" vs "JPM"
    """
    entity_lower = entity.lower().strip()

    # Common aliases for major financial institutions
    # Add more as you discover duplicates
    aliases = {
        # Format: canonical_name: [list of variations]
        "jpmorgan": ["jp morgan", "jpmorgan chase", "jpm", "jpmorgan chase"],
        "bankofamerica": ["bank of america", "bofa", "boa", "b of a"],
        "goldman": ["goldman sachs", "goldman", "gs"],
        "blackrock": ["blackrock", "black rock"],
        "coinbase": ["coinbase", "coinbase global"],
        "circle": ["circle", "circle internet"],
        "ripple": ["ripple", "ripple labs"],
        "binance": ["binance", "binance.us", "binance us"],
        "kraken": ["kraken", "kraken digital"],
        "gemini": ["gemini", "gemini trust"],
    }

    # Check if entity matches any alias
    for canonical, variations in aliases.items():
        if any(var in entity_lower for var in variations):
            return canonical

    # If no match, return normalized entity
    return entity_lower


def is_similar_to_seen(title: str, seen_titles: list[dict], threshold: float = SIMILARITY_THRESHOLD) -> tuple[bool, str | None]:
    """
    Check if title is similar to any previously seen title.

    Uses THREE complementary methods:
      1. SequenceMatcher (catches reworded titles with similar character sequences)
      2. Jaccard token overlap (catches paraphrased titles sharing key terms)
      3. Entity + event matching (catches "CME launches X" vs "CME targets X launch")

    Args:
        title: Title to check
        seen_titles: List of dicts with 'title' and optionally 'link'
        threshold: Base SequenceMatcher similarity threshold (0.0 to 1.0)

    Returns:
        Tuple of (is_similar, similar_title)
    """
    current_event_type = get_event_type(title)
    is_launch = current_event_type is not None
    current_tokens = _tokenize_title(title)
    current_entities = extract_entities(title)

    # Use stricter threshold for launch/funding stories
    if is_launch:
        threshold = LAUNCH_STORY_THRESHOLD

    for seen in seen_titles:
        seen_title = seen.get("title", "")
        if not seen_title:
            continue

        # --- Method 1: SequenceMatcher (original) ---
        seq_sim = title_similarity(title, seen_title)

        # --- Method 2: Jaccard token overlap ---
        seen_tokens = _tokenize_title(seen_title)
        jac_sim = _jaccard(current_tokens, seen_tokens)

        # --- Method 3: Entity + event overlap ---
        seen_entities = extract_entities(seen_title)
        shared_entities = current_entities & seen_entities
        seen_event_type = get_event_type(seen_title)

        # ----- Decision logic -----

        # (A) High SequenceMatcher similarity — same as before
        if is_launch and seen_event_type is not None:
            if shared_entities and current_event_type == seen_event_type:
                # Same entity + same event: very aggressive dedup
                if seq_sim >= 0.50 or jac_sim >= 0.30:
                    return True, seen_title
            elif shared_entities:
                # Same entity, different event: be careful
                if seq_sim >= 0.80:
                    return True, seen_title
            else:
                if seq_sim >= 0.85:
                    return True, seen_title
        else:
            if seq_sim >= threshold:
                return True, seen_title

        # (B) Shared entity + meaningful token overlap = same story.
        #     E.g., "Payoneer Adds Stablecoin Capabilities" vs
        #           "Payoneer, Wirex add stablecoin payment capabilities"
        #     Jaccard 0.30 with a shared entity is strong evidence.
        if shared_entities and jac_sim >= 0.25:
            return True, seen_title

        # (C) High Jaccard alone (no known entity, but heavy word overlap)
        #     E.g., two articles about the same niche topic from different outlets
        if jac_sim >= 0.50:
            return True, seen_title

    return False, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["prepare"], default="prepare")
    ap.add_argument("--no-ai", action="store_true", help="Disable AI filter even if ANTHROPIC_API_KEY is set")
    args = ap.parse_args()

    # ---------------------------------------------------------------------------
    # Initialize AI filter if enabled and API key is available
    # ---------------------------------------------------------------------------
    ai_filter = None
    use_ai = ENABLE_AI_FILTER and not args.no_ai

    if use_ai:
        try:
            from src.ai_filter import AIArticleFilter
            ai_filter = AIArticleFilter()
            print("🤖 AI filter: ENABLED (Claude claude-haiku-4-5-20251001 + SQLite dedup)")
        except Exception as e:
            print(f"⚠️  AI filter init failed ({e}), continuing without it")
            ai_filter = None
    else:
        if args.no_ai:
            print("🤖 AI filter: DISABLED (--no-ai flag)")
        else:
            print("🤖 AI filter: DISABLED (no ANTHROPIC_API_KEY)")

    # Load existing items (produced by your aggregator pipeline)
    items = load_json(ITEMS_PATH, [])

    # TEMP DEBUG: print one raw item to verify the field names (title/link/published)
    print("🔎 SAMPLE ITEM:")
    if isinstance(items, list) and items:
        print(json.dumps(items[0], indent=2, ensure_ascii=False)[:1200])
    else:
        print("(no items)")

    if not isinstance(items, list):
        print(f"❌ {ITEMS_PATH} is not a list. Check your pipeline output.")
        return 1

    # Load state
    state = load_json(STATE_PATH, {"seen": [], "seen_titles": []})
    seen = set(state.get("seen", []))
    seen_titles = state.get("seen_titles", [])

    # Filter: only dated items, only new (not seen)
    new_items = []
    for it in items:
        if not has_date(it):
            continue
        iid = stable_item_id(it)
        if iid in seen:
            continue
        new_items.append(it)

    print(f"🆕 New items (not seen, dated): {len(new_items)}")

    # Build drafts (one per story)
    drafts = []
    skipped_no_title = 0
    skipped_no_link = 0
    skipped_similar = 0
    skipped_low_score = 0
    skipped_telegram = 0
    skipped_blocklist = 0
    skipped_ai_filter = 0       # NEW: count of AI-rejected articles
    skipped_ai_duplicate = 0    # NEW: count of SQLite-deduped articles

    for it in new_items:
        title = clean_title(it.get("title") or "")
        link = (it.get("link") or it.get("url") or "").strip()
        score = it.get("score", 0)
        source_type = it.get("source_type", "")

        if not title:
            skipped_no_title += 1
            continue
        if not link:
            skipped_no_link += 1
            print(f"⚠️  No link for: {title[:60]}... (keys: {list(it.keys())})")
            continue

        # Exclude Telegram sources to prevent spam
        # Wait for news article coverage before posting
        if EXCLUDE_TELEGRAM_SOURCES and source_type == "telegram":
            skipped_telegram += 1
            print(f"📱 Skipping Telegram post (wait for news coverage): \"{title[:70]}...\"")
            continue

        # Check blocklist
        blocked, block_reason = is_blocklisted(it)
        if blocked:
            skipped_blocklist += 1
            print(f"🚫 Blocklisted ({block_reason}): \"{title[:70]}...\"")
            continue

        # Filter out low-quality items based on score
        if score < MIN_ALERT_SCORE:
            skipped_low_score += 1
            breakdown = it.get("score_breakdown", {})
            listicle_count = breakdown.get("listicle", 0)
            generic_count = breakdown.get("generic", 0)

            reason = []
            if listicle_count > 0:
                reason.append(f"listicle")
            if generic_count > 0:
                reason.append(f"generic")
            if not reason:
                reason.append(f"score={score}")

            print(f"⚖️  Filtered low score ({', '.join(reason)}): \"{title[:70]}...\"")
            continue

        # Check for semantic similarity to previously posted titles
        is_similar, similar_title = is_similar_to_seen(title, seen_titles)
        if is_similar:
            skipped_similar += 1
            print(f"🔁 Skipping similar: \"{title[:70]}...\"")
            print(f"   Similar to: \"{similar_title[:70]}...\"")
            continue

        # -------------------------------------------------------------------
        # AI FILTER: SQLite dedup + Claude classification (final quality gate)
        # This runs AFTER all cheap/local filters to minimize API calls.
        # -------------------------------------------------------------------
        ai_decision = None  # Track the AI decision for this item

        if ai_filter is not None:
            try:
                ai_decision = ai_filter.evaluate(it)

                if not ai_decision["publish"]:
                    if ai_decision.get("source") == "duplicate_check":
                        skipped_ai_duplicate += 1
                        print(f"🗄️  AI dedup: \"{title[:70]}...\"")
                        print(f"   Reason: {ai_decision['reason']}")
                    else:
                        skipped_ai_filter += 1
                        print(f"🤖 AI rejected [{ai_decision.get('category', '?')}]: \"{title[:70]}...\"")
                        print(f"   Reason: {ai_decision['reason']}")
                    continue

                # AI approved — log the decision
                print(
                    f"✅ AI approved [{ai_decision.get('category', '?')}/{ai_decision.get('priority', '?')}]: "
                    f"\"{title[:70]}...\""
                )

            except Exception as e:
                # On error, fall through and publish (fail-open)
                ai_decision = None
                print(f"⚠️  AI filter error ({e}), defaulting to publish: \"{title[:60]}...\"")

        iid = stable_item_id(it)

        # Build the draft entry
        draft_entry = {
            "id": iid,
            "title": title,
            "link": link,
            "message_html": build_message_html(title, link),
        }

        # Include AI metadata if the filter was used and approved
        if ai_decision and ai_decision.get("publish"):
            draft_entry["ai_category"] = ai_decision.get("category", "")
            draft_entry["ai_priority"] = ai_decision.get("priority", "")

        drafts.append(draft_entry)

        # Record in SQLite that this article will be posted (for future dedup)
        if ai_filter is not None:
            try:
                ai_filter.record_posted(it, ai_decision or {})
            except Exception as e:
                print(f"⚠️  Failed to record posted article in SQLite: {e}")

        # Mark as seen so we don't re-create approval issues every 5 mins
        seen.add(iid)

        # Store title for future similarity checks
        seen_titles.append({
            "title": title,
            "link": link,
            "id": iid
        })

    # Clean up AI filter resources
    if ai_filter is not None:
        ai_filter.close()

    # Write drafts
    save_json(DRAFTS_PATH, drafts)
    print(f"\n📝 Wrote drafts: {DRAFTS_PATH} ({len(drafts)} drafts)")

    # Print skip summary
    skip_parts = []
    if skipped_no_title:
        skip_parts.append(f"{skipped_no_title} no title")
    if skipped_no_link:
        skip_parts.append(f"{skipped_no_link} no link")
    if skipped_low_score:
        skip_parts.append(f"{skipped_low_score} low score")
    if skipped_similar:
        skip_parts.append(f"{skipped_similar} similar")
    if skipped_telegram:
        skip_parts.append(f"{skipped_telegram} telegram")
    if skipped_blocklist:
        skip_parts.append(f"{skipped_blocklist} blocklisted")
    if skipped_ai_duplicate:
        skip_parts.append(f"{skipped_ai_duplicate} AI dedup")
    if skipped_ai_filter:
        skip_parts.append(f"{skipped_ai_filter} AI rejected")

    if skip_parts:
        print(f"⚠️  Skipped: {', '.join(skip_parts)}")

    # Keep only last 100 seen titles to prevent unbounded growth
    if len(seen_titles) > 100:
        seen_titles = seen_titles[-100:]

    # Save state
    state["seen"] = sorted(seen)
    state["seen_titles"] = seen_titles
    save_json(STATE_PATH, state)
    print(f"💾 Updated state: {STATE_PATH} (seen={len(state['seen'])}, seen_titles={len(seen_titles)})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())