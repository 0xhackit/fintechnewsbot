#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone

STATE_PATH = Path("state/seen_alerts.json")
DRAFTS_PATH = Path("out/alerts_drafts.json")

# Change this if your pipeline writes items elsewhere
ITEMS_PATH = Path("out/items_last24h.json")


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
    link = (item.get("link") or "").strip().lower()
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
    # Telegram HTML formatting: bold + LINK anchor
    safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_link = link.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<b>{safe_title}</b> <a href=\"{safe_link}\">LINK</a>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["prepare"], default="prepare")
    args = ap.parse_args()

    # Load existing items (produced by your aggregator pipeline)
    items = load_json(ITEMS_PATH, [])
    if not isinstance(items, list):
        print(f"❌ {ITEMS_PATH} is not a list. Check your pipeline output.")
        return 1

    # Load state
    state = load_json(STATE_PATH, {"seen": []})
    seen = set(state.get("seen", []))

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
    for it in new_items:
        title = clean_title(it.get("title") or "")
        link = (it.get("link") or "").strip()
        if not title or not link:
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

    # Write drafts
    save_json(DRAFTS_PATH, drafts)
    print(f"📝 Wrote drafts: {DRAFTS_PATH} ({len(drafts)} drafts)")

    # Save state
    state["seen"] = sorted(seen)
    save_json(STATE_PATH, state)
    print(f"💾 Updated state: {STATE_PATH} (seen={len(state['seen'])})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())