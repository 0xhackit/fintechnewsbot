#!/usr/bin/env python3
"""
fetch_tree_local.py — ISOLATED PREVIEW of the TreeOfAlpha ingester.

Fetches Tree, runs it through the SAME v2 gate as production (via src.fetch_tree +
src.pipeline_v2), and writes out/market/tree/ — but posts nowhere and uses an isolated
dedup DB. For eyeballing/tuning Tree quality before it feeds prepare_alerts_v2.py.

    python scripts/fetch_tree_local.py --limit 300 --window-hours 24
    python scripts/fetch_tree_local.py --fixture tree_sample.json   # offline
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.app import load_config  # noqa: E402
from src.dedup_agent import DedupAgent  # noqa: E402
from src import pipeline_v2, fetch_tree  # noqa: E402

OUT_DIR = _PROJECT_ROOT / "out" / "market" / "tree"
STATE_DIR = _PROJECT_ROOT / "state" / "tree"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--window-hours", type=int, default=24)
    ap.add_argument("--fixture", type=str, default=None)
    args = ap.parse_args()

    cfg = load_config()
    now = datetime.now(timezone.utc)
    fixture = args.fixture
    if fixture and not Path(fixture).is_absolute():
        fixture = str(_PROJECT_ROOT / fixture)
    try:
        items, stats = fetch_tree.fetch_tree_items(cfg, args.limit, args.window_hours, fixture, now)
    except Exception as e:
        print(f"❌ Tree fetch failed: {e}")
        return 1
    print(f"📥 pulled {stats['pulled']}   🎯 on-topic & scored {len(items)}   "
          f"(off-topic {stats['off_topic']}, out-of-window {stats['out_of_window']})")

    tiers = {it["feed_name"]: {"tier": fetch_tree.tree_tier(it["feed_name"])} for it in items}
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    dedup = DedupAgent(db_path=STATE_DIR / "posted_articles.db",
                       seen_titles=[], feed_entries=[], enable_ai_tiebreaker=False)
    kept, review, killed = [], [], []
    for it in sorted(items, key=lambda x: x.get("score", 0), reverse=True):
        rec = pipeline_v2.evaluate_item(it, tiers, fetch_tree.TREE_DEFAULT_TIER, use_fulltext=False)
        if rec is None:
            continue
        rec["coins"] = it.get("coins", [])
        rec["origin"] = "tree"
        bucket = rec.pop("bucket", None)
        if bucket in (None, "below_score"):
            continue
        if bucket == "killed":
            killed.append(rec); continue
        if bucket == "review":
            review.append(rec); continue
        is_dup, _ = dedup.is_duplicate(rec["title"], rec["link"], rec["snippet"])
        if is_dup:
            continue
        dedup.record(title=rec["title"], url=rec["link"], category=rec["category"], priority=rec["source_tier"])
        kept.append(rec)
    dedup.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in [("kept", kept), ("review", review), ("killed", killed)]:
        (OUT_DIR / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "meta.json").write_text(json.dumps({
        "source": "tree", "label": "TreeOfAlpha (preview)", "generated_at": now.isoformat(),
        "keep": len(kept), "review": len(review), "kill": len(killed), **stats,
    }, indent=2), encoding="utf-8")

    print(f"\n✅ KEEP {len(kept)}   🔎 REVIEW {len(review)}   🗑️ KILL {len(killed)}   (preview — posts nowhere)")
    for label, rows in [("KEPT", kept), ("REVIEW", review)]:
        if rows:
            print(f"\n{label}:")
            for r in rows[:8]:
                coins = ",".join(r.get("coins") or []) or "—"
                print(f"  [{r['score']:>3}] {r['source_tier']} {r['category']:<12} {coins:<10} {r['title'][:58]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
