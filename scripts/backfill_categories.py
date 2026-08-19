#!/usr/bin/env python3
"""
backfill_categories.py — stamp `category` onto existing out/feed.json entries.

New posts get their category at write time (post_alerts_now.py /
scripts/publish_x.py). This script fills in history so the site's section
tabs have data on day one, and lets you re-classify everything after tuning
the pattern banks in src/categorize.py.

Usage:
    python scripts/backfill_categories.py            # only fill missing
    python scripts/backfill_categories.py --force    # re-classify everything
    python scripts/backfill_categories.py --dry-run  # preview, write nothing
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.categorize import CATEGORY_LABELS, HIGH_SIGNAL, categorize  # noqa: E402

FEED_PATH = Path("out/feed.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="re-classify entries that already have a category")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the result without writing feed.json")
    ap.add_argument("--path", default=str(FEED_PATH), help="path to feed.json")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"error: {path} not found (run from the repo root)")
        return 1

    feed = json.loads(path.read_text(encoding="utf-8"))
    entries = feed.get("entries", [])

    counts = collections.Counter()
    changed = 0
    for entry in entries:
        existing = entry.get("category")
        if existing and not args.force:
            counts[existing] += 1
            continue
        result = categorize(entry.get("title", ""), entry.get("snippet", ""))
        if existing != result["category"]:
            changed += 1
        entry["category"] = result["category"]
        counts[result["category"]] += 1

    total = len(entries)
    high = sum(counts[c] for c in HIGH_SIGNAL)
    print(f"{total} entries — {changed} updated\n")
    for cat, label in CATEGORY_LABELS.items():
        n = counts[cat]
        pct = (100 * n / total) if total else 0
        print(f"  {label:<16} {n:>4}  ({pct:.0f}%)")
    print(f"\n  Latest News (product + fundraising): {high}/{total}")

    if args.dry_run:
        print("\ndry run — feed.json not written")
        return 0

    path.write_text(json.dumps(feed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
