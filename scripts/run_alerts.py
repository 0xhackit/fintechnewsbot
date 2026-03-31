#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher

# Ensure the project root is importable so `from src.* import ...` works
# when run from the project directory (e.g., `python scripts/run_alerts.py`)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.utils import (
    normalize_title,
    tokenize_title,
    jaccard_similarity,
    extract_entities,
    get_event_type,
    canonicalize_url,
)
from src.dedup_agent import DedupAgent
from src.ranking_agent import rank_article

STATE_PATH = Path("state/seen_alerts.json")
FEEDBACK_PATH = Path("state/feedback.json")
DRAFTS_PATH = Path("out/alerts_drafts.json")
BLOCKLIST_PATH = Path("blocklist.json")
FEED_PATH = Path("out/feed.json")

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
    link = (item.get("link") or item.get("url") or "").strip()
    link = canonicalize_url(link).lower()  # Normalize URL (strip UTM, www, fragment)
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


def title_similarity(title1: str, title2: str) -> float:
    """
    Calculate similarity between two titles (0.0 to 1.0).
    Uses SequenceMatcher on normalized titles.
    """
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    return SequenceMatcher(None, norm1, norm2).ratio()


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
    current_tokens = tokenize_title(title)
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
        seen_tokens = tokenize_title(seen_title)
        jac_sim = jaccard_similarity(current_tokens, seen_tokens)

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

        # (B) Shared entities + meaningful token overlap = same story.
        #     - 2+ shared entities: very strong signal, low Jaccard bar (0.10)
        #       E.g., "Citigroup Hires From Binance for Digital Assets" vs
        #             "Citi poaches Binance, Ripple execs in digital asset hiring blitz"
        #     - 1 shared entity: needs moderate Jaccard (0.25)
        #       E.g., "Payoneer Adds Stablecoin Capabilities" vs
        #             "Payoneer, Wirex add stablecoin payment capabilities"
        if len(shared_entities) >= 2 and jac_sim >= 0.10:
            return True, seen_title
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
    # Initialize AI filter + Dedup Agent
    # ---------------------------------------------------------------------------
    use_ai = ENABLE_AI_FILTER and not args.no_ai

    if args.no_ai:
        print("🤖 AI filter: DISABLED (--no-ai flag)")
    elif not ENABLE_AI_FILTER:
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

    # Load user feedback for ranking agent
    feedback_data = load_json(FEEDBACK_PATH, {"signals": [], "learned_rules": []})
    feedback_count = len(feedback_data.get("signals", []))
    if feedback_count:
        print(f"📊 Loaded {feedback_count} feedback signal(s) for ranking agent")

    # Load feed.json entries for dedup
    feed_data = load_json(FEED_PATH, {"entries": []})
    feed_entries = feed_data.get("entries", []) if isinstance(feed_data, dict) else []

    # Also register feed.json IDs in the seen set (safety-net for manual posts)
    feed_dedup_count = 0
    for fe in feed_entries:
        fe_title = fe.get("title", "")
        fe_link = fe.get("link", "")
        if fe_title and fe_link:
            fe_id = stable_item_id({"title": fe_title, "link": fe_link})
            if fe_id not in seen:
                seen.add(fe_id)
                feed_dedup_count += 1
    if feed_dedup_count:
        print(f"📋 Registered {feed_dedup_count} feed.json entries in dedup set")

    # Initialize unified dedup agent (consolidates SQLite + seen_titles + feed.json)
    dedup_agent = DedupAgent(
        seen_titles=seen_titles,
        feed_entries=feed_entries,
        enable_ai_tiebreaker=use_ai,
    )
    print(f"🔍 Dedup agent: initialized")

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
    skipped_ai_filter = 0       # Count of AI-rejected articles

    for it in new_items:
        title = clean_title(it.get("title") or "")
        link = (it.get("link") or it.get("url") or "").strip()
        snippet = (it.get("snippet") or "")[:300]
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

        # Unified dedup check (SQLite + seen_titles + feed.json + session cache)
        is_dup, dup_reason = dedup_agent.is_duplicate(title, link, snippet)
        if is_dup:
            skipped_similar += 1
            print(f"🔁 Dedup: \"{title[:70]}...\"")
            print(f"   Reason: {dup_reason}")
            continue

        # Ranking agent: determines tier + platform eligibility
        score_breakdown = it.get("score_breakdown", {})
        ranking = rank_article(
            title=title,
            snippet=snippet,
            score=score,
            score_breakdown=score_breakdown,
            feedback=feedback_data if feedback_count else None,
        )

        if ranking["tier"] == "reject":
            skipped_ai_filter += 1
            print(f"🤖 Rejected [{ranking.get('category', '?')}]: \"{title[:70]}...\"")
            print(f"   Reason: {ranking['reason']}")
            continue

        if not ranking["post_to_telegram"]:
            skipped_ai_filter += 1
            print(f"🤖 Below threshold [{ranking['tier']}]: \"{title[:70]}...\"")
            continue

        print(
            f"✅ Ranked [{ranking['tier']}/{ranking.get('category', '?')}]: "
            f"\"{title[:70]}...\" (X={'yes' if ranking['post_to_x'] else 'no'})"
        )

        # Quality review (typo fix only)
        if use_ai:
            try:
                from src.ai_filter import quality_review
                recent = [d["title"] for d in drafts[-20:]]
                qr = quality_review(title, snippet, recent)

                if qr.get("has_issues"):
                    for issue in qr.get("issues", []):
                        print(f"   🔧 Quality: {issue}")

                if qr.get("clean_title") and qr["clean_title"] != title:
                    print(f"   📝 Title cleaned: \"{title[:60]}\" → \"{qr['clean_title'][:60]}\"")
                    title = qr["clean_title"]
            except Exception as e:
                print(f"⚠️  Quality review error ({e}), continuing with original title")

        iid = stable_item_id(it)

        # Build the draft entry
        draft_entry = {
            "id": iid,
            "title": title,
            "link": link,
            "message_html": build_message_html(title, link),
            "score": score,
            "snippet": snippet,
            "matched_topics": it.get("matched_topics", []),
            "tier": ranking["tier"],
            "post_to_x": ranking["post_to_x"],
            "category": ranking.get("category", ""),
        }

        drafts.append(draft_entry)

        # Record in dedup agent (SQLite + session cache)
        dedup_agent.record(
            title=title,
            url=link,
            category=ranking.get("category", ""),
            priority=ranking.get("tier", ""),
        )

        # Mark as seen so we don't re-create approval issues every 5 mins
        seen.add(iid)

        # Store title for future similarity checks
        seen_titles.append({
            "title": title,
            "link": link,
            "id": iid
        })

    # Clean up dedup agent resources
    dedup_agent.close()

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
    if skipped_ai_filter:
        skip_parts.append(f"{skipped_ai_filter} AI rejected")

    if skip_parts:
        print(f"⚠️  Skipped: {', '.join(skip_parts)}")

    # Keep only last 500 seen titles to prevent unbounded growth
    # (was 100 — too small, caused duplicates when same story re-appeared)
    if len(seen_titles) > 500:
        seen_titles = seen_titles[-500:]

    # Save state
    state["seen"] = sorted(seen)
    state["seen_titles"] = seen_titles
    save_json(STATE_PATH, state)
    print(f"💾 Updated state: {STATE_PATH} (seen={len(state['seen'])}, seen_titles={len(seen_titles)})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())