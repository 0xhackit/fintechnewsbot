#!/usr/bin/env python3
"""
Shared helper: read and write out/feed.json.

The feed is a rolling 7-day window of all posted articles.
Entries accumulate across pipeline runs. Old entries (>7 days) are pruned.
Imported by both post_alerts_now.py (Telegram) and scripts/publish_x.py (X).
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

FEED_PATH = Path("out/feed.json")
FEED_RETENTION_DAYS = 7


def load_feed() -> dict:
    """Load existing feed.json, return empty structure if not present."""
    if not FEED_PATH.exists():
        return {"updated_at": "", "entries": []}
    try:
        return json.loads(FEED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"updated_at": "", "entries": []}


def save_feed(feed: dict) -> None:
    """Write feed.json."""
    FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    FEED_PATH.write_text(
        json.dumps(feed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def prune_old_entries(entries: list) -> list:
    """Remove entries older than FEED_RETENTION_DAYS days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=FEED_RETENTION_DAYS)
    kept = []
    for entry in entries:
        posted_at_str = entry.get("posted_at", "")
        if not posted_at_str:
            kept.append(entry)
            continue
        try:
            posted_dt = datetime.fromisoformat(
                posted_at_str.replace("Z", "+00:00")
            )
            if posted_dt >= cutoff:
                kept.append(entry)
        except (ValueError, TypeError):
            kept.append(entry)
    return kept


def upsert_entries(existing: list, new_entries: list) -> list:
    """
    Merge new_entries into existing, deduplicating by 'id'.
    New data wins on conflicts — e.g. X script upserts tweet_id onto a
    TG-only entry written earlier in the same pipeline run.
    Returns list sorted descending by posted_at.
    """
    index = {e["id"]: e for e in existing}
    for entry in new_entries:
        eid = entry["id"]
        if eid in index:
            index[eid].update(entry)
        else:
            index[eid] = entry

    merged = list(index.values())
    merged.sort(key=lambda e: e.get("posted_at", ""), reverse=True)
    return merged


def write_entries_to_feed(new_entries: list) -> None:
    """
    Main entry point: load existing feed, merge new entries, prune, save.
    Called once per posting script after all posts are complete.
    """
    if not new_entries:
        return
    feed = load_feed()
    existing = feed.get("entries", [])
    merged = upsert_entries(existing, new_entries)
    pruned = prune_old_entries(merged)
    feed["entries"] = pruned
    feed["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_feed(feed)
    print(f"  📄 Feed written: {len(pruned)} entries in out/feed.json")
