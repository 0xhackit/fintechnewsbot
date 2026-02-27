#!/usr/bin/env python3
"""
One-time script: bootstrap out/feed.json from existing alerts_drafts.json.

Run this once after deploying feed_writer.py but before the next pipeline run.
This creates the initial feed so the frontend has data immediately.

Usage:
    python3 scripts/bootstrap_feed.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from feed_writer import write_entries_to_feed

DRAFTS_PATH = _PROJECT_ROOT / "out" / "alerts_drafts.json"


def main():
    if not DRAFTS_PATH.exists():
        print("❌ No alerts_drafts.json found — nothing to bootstrap from")
        return

    drafts = json.loads(DRAFTS_PATH.read_text(encoding="utf-8"))
    if not drafts:
        print("📭 alerts_drafts.json is empty — nothing to bootstrap")
        return

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entries = []
    for draft in drafts:
        entries.append({
            "id": draft.get("id", ""),
            "title": draft.get("title", ""),
            "link": draft.get("link", ""),
            "snippet": draft.get("snippet", ""),
            "score": draft.get("score", 0),
            "matched_topics": draft.get("matched_topics", []),
            "ai_category": draft.get("ai_category", ""),
            "ai_priority": draft.get("ai_priority", ""),
            "posted_at": now_iso,
            "source": draft.get("source", ""),
            "feed_name": draft.get("feed_name", ""),
            "published_at": draft.get("published_at", ""),
            "posted_to_telegram": True,
            "telegram_message_id": None,
            "posted_to_x": False,
            "tweet_id": None,
            "tweet_text": None,
            "tweet_url": None,
        })

    write_entries_to_feed(entries)
    print(f"✅ Bootstrapped feed.json with {len(entries)} entries from alerts_drafts.json")


if __name__ == "__main__":
    main()
