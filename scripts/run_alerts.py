#!/usr/bin/env python3
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone

STATE_PATH = Path("state/seen_alerts.json")
OUT_ALERTS = Path("out/alerts.json")
ITEMS_PATH = Path("out/items_last24h.json")  # replace if your pipeline writes elsewhere

def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def item_id(item: dict) -> str:
    title = (item.get("title") or "").strip().lower()
    link = (item.get("link") or "").strip().lower()
    base = f"{title}|{link}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def main():
    # Load items produced by your pipeline
    items = load_json(ITEMS_PATH, [])
    if not items:
        print(f"⚠️ No items found at {ITEMS_PATH}. Run `python run.py` first or point ITEMS_PATH to your live feed output.")
        return 0

    state = load_json(STATE_PATH, {"seen": []})
    seen = set(state.get("seen", []))

    new_items = []
    for it in items:
        # Only post dated items
        if not it.get("published_at") and not it.get("published"):
            continue
        iid = item_id(it)
        if iid in seen:
            continue
        new_items.append(it)

    print(f"🆕 New items to post: {len(new_items)}")
    save_json(OUT_ALERTS, new_items)

    # Update state (even if you don't publish yet)
    for it in new_items:
        seen.add(item_id(it))
    state["seen"] = list(seen)
    save_json(STATE_PATH, state)

    # Publishing: if you already have scripts/publish_telegram.py supporting alerts.json, call it here.
    # Otherwise, keep this as "prepare only" and let a separate step publish.
    if new_items:
        print("✅ Prepared out/alerts.json and updated state/seen_alerts.json")
    else:
        print("✅ Nothing new.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())