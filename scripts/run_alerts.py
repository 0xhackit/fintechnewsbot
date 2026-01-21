#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path
from difflib import SequenceMatcher

STATE_PATH = Path("state/seen_alerts.json")
DRAFTS_PATH = Path("out/alerts_drafts.json")

# Change this if your pipeline writes items elsewhere
ITEMS_PATH = Path("out/items_last24h.json")

# Minimum similarity threshold for considering titles as duplicates
# 0.0 = completely different, 1.0 = identical
SIMILARITY_THRESHOLD = 0.75

# Minimum score for an item to become an alert
# Items with score below this threshold will be filtered out
MIN_ALERT_SCORE = 20


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def is_similar_to_seen(title: str, seen_titles: list[dict], threshold: float = SIMILARITY_THRESHOLD) -> tuple[bool, str | None]:
    """
    Check if title is similar to any previously seen title.

    Args:
        title: Title to check
        seen_titles: List of dicts with 'title' and optionally 'link'
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        Tuple of (is_similar, similar_title)
    """
    for seen in seen_titles:
        seen_title = seen.get("title", "")
        if not seen_title:
            continue

        similarity = title_similarity(title, seen_title)
        if similarity >= threshold:
            return True, seen_title

    return False, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["prepare"], default="prepare")
    args = ap.parse_args()

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

    for it in new_items:
        title = clean_title(it.get("title") or "")
        link = (it.get("link") or it.get("url") or "").strip()
        score = it.get("score", 0)

        if not title:
            skipped_no_title += 1
            continue
        if not link:
            skipped_no_link += 1
            print(f"⚠️  No link for: {title[:60]}... (keys: {list(it.keys())})")
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

        iid = stable_item_id(it)

        drafts.append(
            {
                "id": iid,
                "title": title,
                "link": link,
                "message_html": build_message_html(title, link),
            }
        )

        # Mark as seen so we don't re-create approval issues every 5 mins
        seen.add(iid)

        # Store title for future similarity checks
        seen_titles.append({
            "title": title,
            "link": link,
            "id": iid
        })

    # Write drafts
    save_json(DRAFTS_PATH, drafts)
    print(f"📝 Wrote drafts: {DRAFTS_PATH} ({len(drafts)} drafts)")
    if skipped_no_title or skipped_no_link or skipped_similar or skipped_low_score:
        print(f"⚠️  Skipped: {skipped_no_title} no title, {skipped_no_link} no link, {skipped_low_score} low score, {skipped_similar} similar")

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