#!/usr/bin/env python3
"""
prepare_alerts_v2.py — PRODUCTION draft preparation, deterministic ($0 LLM).

The graduation of the v2 pipeline: this replaces scripts/run_alerts.py's Claude
Haiku ranking agent with the deterministic editorial + region + section + source
tier gate (src/pipeline_v2). It reads the same input run_alerts.py does
(out/items_last24h.json, produced by run.py) and writes the same output the
posters consume (out/alerts_drafts.json) — so post_alerts_now.py (Telegram) and
scripts/publish_x.py (X) are UNCHANGED.

Routing (no human in the loop for KEEP):
  • KEEP    → out/alerts_drafts.json → Telegram + website feed (auto).
              A high-quality subset (pipeline_v2.qualifies_for_x) is flagged
              post_to_x=true → also posted to X.
  • REVIEW  → out/market/standalone/review.json → admin decides (publish/kill).
  • KILLED  → dropped (recorded only in killed.json for auditability).

Telegram is ignored as a data source (RSS-only), matching run_alerts.py's
EXCLUDE_TELEGRAM_SOURCES. Dedup uses the real production state so nothing reposts.

Usage:
    python scripts/prepare_alerts_v2.py            # write drafts + update dedup state
    python scripts/prepare_alerts_v2.py --dry-run  # compute + write preview, touch NO state
    python scripts/prepare_alerts_v2.py --no-fulltext   # skip Jina enrichment
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

ITEMS_PATH = _PROJECT_ROOT / "out" / "items_last24h.json"
DRAFTS_PATH = _PROJECT_ROOT / "out" / "alerts_drafts.json"
DRAFTS_PREVIEW_PATH = _PROJECT_ROOT / "out" / "alerts_drafts.preview.json"
ADMIN_DIR = _PROJECT_ROOT / "out" / "market" / "standalone"  # served to the admin Review queue
SEEN_PATH = _PROJECT_ROOT / "state" / "seen_alerts.json"
FEED_PATH = _PROJECT_ROOT / "out" / "feed.json"
BLOCKLIST_PATH = _PROJECT_ROOT / "blocklist.json"
SOURCES_PATH = _PROJECT_ROOT / "sources.json"

SEEN_TITLES_CAP = 500
SEEN_IDS_CAP = 1000


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_sources() -> tuple[dict, str]:
    d = _load_json(SOURCES_PATH, {})
    return d.get("tiers", {}), d.get("default_tier", "C")


def is_blocklisted(item: dict, blocklist: dict) -> bool:
    """Same rules as scripts/run_alerts.py::is_blocklisted (defence in depth)."""
    url = (item.get("link") or item.get("url") or "").strip()
    if url in blocklist.get("blocked_urls", []):
        return True
    title_lower = (item.get("title") or "").lower()
    for kw in blocklist.get("blocked_keywords", []):
        if kw.lower() in title_lower:
            return True
    if (item.get("source") or "").strip() in blocklist.get("blocked_sources", []):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="compute + write a preview; do NOT write drafts or touch dedup state")
    ap.add_argument("--no-fulltext", action="store_true",
                    help="skip Jina full-text enrichment (classify on title+snippet)")
    ap.add_argument("--tree", action="store_true",
                    help="force-enable the TreeOfAlpha merge for this run (overrides config.tree.enabled)")
    args = ap.parse_args()
    use_fulltext = not args.no_fulltext

    items = _load_json(ITEMS_PATH, [])
    if not isinstance(items, list):
        print(f"❌ {ITEMS_PATH} is not a list — run `python run.py` first.")
        return 1
    print(f"📥 Loaded {len(items)} scored items from {ITEMS_PATH.name}")

    tiers, default_tier = load_sources()
    blocklist = _load_json(BLOCKLIST_PATH,
                           {"blocked_urls": [], "blocked_keywords": [], "blocked_sources": []})

    # ── TreeOfAlpha consensus merge (config: tree.enabled) ──────────────────
    # Fetch the Tree firehose, run it through the same relevance+scoring, then
    # corroborate RSS stories with it (a Tree match bumps consensus → auto-keep).
    # Fail-soft: any Tree error leaves the RSS pipeline untouched.
    cfg = load_config()
    tree_cfg = cfg.get("tree", {})
    if tree_cfg.get("enabled") or args.tree:
        try:
            tree_items, tstats = fetch_tree.fetch_tree_items(
                cfg, limit=int(tree_cfg.get("limit", 300)),
                window_hours=int(cfg.get("lookback_hours", 24)))
            items, mstats = fetch_tree.merge_consensus(items, tree_items)
            for it in items:
                fn = it.get("feed_name", "")
                if fn.startswith("tree:") and fn not in tiers:
                    tiers[fn] = {"tier": fetch_tree.tree_tier(fn)}
            print(f"🌳 Tree: pulled {tstats['pulled']}, on-topic {mstats['tree_scored']} "
                  f"→ corroborated {mstats['corroborated_rss']} RSS, "
                  f"{mstats['tree_standalone']} standalone")
        except Exception as e:
            print(f"⚠️  Tree merge skipped (fail-soft): {e}")

    # Production dedup state (real): seen_alerts.json + feed.json + posted_articles.db.
    state = _load_json(SEEN_PATH, {"seen": [], "seen_titles": []})
    seen = set(state.get("seen", []))
    seen_titles = state.get("seen_titles", [])
    feed = _load_json(FEED_PATH, {"entries": []})
    feed_entries = feed.get("entries", []) if isinstance(feed, dict) else []

    dedup = DedupAgent(  # default db_path = state/posted_articles.db (production)
        seen_titles=seen_titles, feed_entries=feed_entries, enable_ai_tiebreaker=False,
    )

    kept, killed, review = [], [], []
    drafts = []
    skipped_low = skipped_dup = skipped_seen = skipped_tg = skipped_block = n_fulltext = 0

    for it in sorted(items, key=lambda x: x.get("score", 0), reverse=True):
        # Ignore Telegram as a data source (wait for news coverage) + blocklist.
        if it.get("source_type") == "telegram":
            skipped_tg += 1
            continue
        if is_blocklisted(it, blocklist):
            skipped_block += 1
            continue

        title = (it.get("title") or "").strip()
        link = (it.get("link") or it.get("url") or "").strip()
        if title and link and pipeline_v2.stable_item_id(title, link) in seen:
            skipped_seen += 1  # already processed in a previous run — don't re-enrich/repost
            continue

        rec = pipeline_v2.evaluate_item(it, tiers, default_tier, use_fulltext=use_fulltext)
        if rec is None:
            continue
        rec["origin"] = it.get("origin", "rss")  # rss | tree | rss+tree (consensus)
        bucket = rec.pop("bucket", None)
        if bucket == "below_score":
            skipped_low += 1
            continue
        if rec.get("fulltext"):
            n_fulltext += 1
        if bucket == "killed":
            killed.append(rec)
            continue
        if bucket == "review":
            review.append(rec)
            continue

        # KEEP → production dedup (real state), then a posting draft.
        is_dup, _ = dedup.is_duplicate(rec["title"], rec["link"], rec["snippet"])
        if is_dup:
            skipped_dup += 1
            continue

        kept.append(rec)
        drafts.append(pipeline_v2.build_draft(rec))

        if not args.dry_run:
            dedup.record(title=rec["title"], url=rec["link"],
                         category=rec["category"], priority=rec["source_tier"])
            seen.add(rec["id"])
            seen_titles.append({"title": rec["title"], "link": rec["link"], "id": rec["id"]})

    dedup.close()

    x_count = sum(1 for d in drafts if d.get("post_to_x"))

    # Admin Review queue JSONs (kept/killed/review + meta) — always written.
    ADMIN_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in [("kept", kept), ("killed", killed), ("review", review)]:
        (ADMIN_DIR / f"{name}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (ADMIN_DIR / "meta.json").write_text(json.dumps({
        "source": "standalone", "label": "Live (v2)", "engine": "prepare_alerts_v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(kept) + len(killed) + len(review),
        "keep": len(kept), "kill": len(killed), "review": len(review),
        "to_x": x_count, "deduped": skipped_dup, "below_score": skipped_low,
        "fulltext_fetched": n_fulltext, "dry_run": args.dry_run,
    }, indent=2), encoding="utf-8")

    # Posting drafts.
    drafts_out = DRAFTS_PREVIEW_PATH if args.dry_run else DRAFTS_PATH
    drafts_out.parent.mkdir(parents=True, exist_ok=True)
    drafts_out.write_text(json.dumps(drafts, indent=2, ensure_ascii=False), encoding="utf-8")

    # Dedup state (skipped entirely in dry-run).
    if not args.dry_run:
        if len(seen_titles) > SEEN_TITLES_CAP:
            seen_titles = seen_titles[-SEEN_TITLES_CAP:]
        seen_list = sorted(seen)
        if len(seen_list) > SEEN_IDS_CAP:
            seen_list = seen_list[-SEEN_IDS_CAP:]
        state["seen"] = seen_list
        state["seen_titles"] = seen_titles
        SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        SEEN_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    mode = "DRY-RUN (no state touched)" if args.dry_run else "LIVE"
    print(f"\n✅ KEEP {len(kept)} (→ {x_count} to X)   🔎 REVIEW {len(review)}   🗑️ KILL {len(killed)}")
    print(f"   skipped: {skipped_seen} already-seen, {skipped_dup} dup, {skipped_low} low-score, "
          f"{skipped_tg} telegram, {skipped_block} blocklisted   full-text {n_fulltext}")
    print(f"📄 drafts → {drafts_out.relative_to(_PROJECT_ROOT)}  ({len(drafts)})   [{mode}]")
    if kept:
        print("\nTop kept (→X marked):")
        for d in drafts[:12]:
            reg = ",".join(d.get("regions") or []) or "—"
            x = "→X" if d.get("post_to_x") else "  "
            print(f"  {x} [{d['score']:>3}] {d.get('tier','?')} {d['category']:<12} {reg:<9} {d['title'][:56]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
