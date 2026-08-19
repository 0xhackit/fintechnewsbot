#!/usr/bin/env python3
"""
standalone_pipeline.py — a SEPARATE, Telegram-free, LLM-free news pipeline.

Built to evaluate the new design (market-events editorial policy, no per-article
LLM calls) WITHOUT touching the live bot. It reuses the existing leaf functions
and scoring constants (single source of truth — nothing is duplicated or
modified in src/), but:

  • ignores Telegram entirely — Google News RSS only
  • replaces the Claude Haiku ranking agent with deterministic editorial.classify
  • replaces the AI dedup tiebreaker with deterministic dedup only (no API calls)
  • writes to its own out/standalone/ + state/standalone/ — never to production
  • posts nowhere

Cost: $0 in API calls (fully deterministic). Compare with the live pipeline,
which calls Haiku per article for ranking/dedup/quality.

Usage:
    python scripts/standalone_pipeline.py              # live: fetch RSS → … → editorial
    python scripts/standalone_pipeline.py --input items  # reuse out/items_last24h.json (offline tail test)
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Reuse production logic — imported, not copied.
from src.app import (  # noqa: E402
    load_config, load_blocklist, is_blocklisted, is_noise, is_pr_noise, has_crypto_anchor,
    _count, TIER1_LAUNCH_PATTERNS, TIER2_ACTIVITY_PATTERNS, COMMENTARY_PATTERNS,
    LISTICLE_PATTERNS, GENERIC_PATTERNS, PROMO_PATTERNS,
)
from src.fetchers import fetch_google_news_rss  # noqa: E402
from src.normalize import normalize_item  # noqa: E402
from src.match import match_item  # noqa: E402
from src.dedupe import hard_dedupe, cluster_and_select  # noqa: E402
from src.improved_scoring import score_item_improved  # noqa: E402
from src.dedup_agent import DedupAgent  # noqa: E402
from src import pipeline_v2  # noqa: E402  (shared editorial+region+section+tier gate)

OUT_DIR = _PROJECT_ROOT / "out" / "market" / "standalone"  # served by /market (source=standalone)
STATE_DIR = _PROJECT_ROOT / "state" / "standalone"
SOURCES_PATH = _PROJECT_ROOT / "sources.json"


def load_sources() -> tuple[dict, str]:
    """Return ({feed_name: tier}, default_tier) from sources.json (fail-soft)."""
    try:
        d = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
        return d.get("tiers", {}), d.get("default_tier", "C")
    except Exception:
        return {}, "C"


def fetch_rss_only(cfg: dict) -> list[dict]:
    """Fetch Google News RSS feeds only. No Telegram."""
    raw = []
    gnews = cfg.get("google_news_rss", {})
    if not gnews.get("enabled", True):
        return raw
    for feed_name, feed_url in gnews.get("feeds", {}).items():
        try:
            raw.extend(fetch_google_news_rss(feed_name=feed_name, feed_url=feed_url,
                                             http_cfg=cfg.get("http", {})))
        except Exception as e:
            print(f"⚠️  feed {feed_name} failed: {e}")
    return raw


def build_scored_items(cfg: dict) -> list[dict]:
    """Mirror app.main's fetch→filter→window→hard-dedupe→score→cluster, RSS-only."""
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=int(cfg.get("lookback_hours", 24)))

    raw = fetch_rss_only(cfg)
    print(f"📥 Raw RSS items: {len(raw)}")

    normalized = [n for n in (normalize_item(r, fetched_at=now_utc) for r in raw) if n]
    blocklist = load_blocklist()

    matched = []
    for item in normalized:
        m = match_item(item, cfg.get("keywords", []), cfg.get("topics", []))
        if not (m.get("matched_keywords") or m.get("matched_topics")):
            continue
        if is_noise(m) or is_pr_noise(m) or is_blocklisted(m, blocklist):
            continue
        if not has_crypto_anchor(m):  # no telegram exception needed — RSS only
            continue
        matched.append(m)
    print(f"🎯 Matched: {len(matched)}")

    windowed = []
    for item in matched:
        pa = item.get("published_at")
        if not pa:
            continue
        try:
            if datetime.fromisoformat(pa.replace("Z", "+00:00")) >= cutoff:
                windowed.append(item)
        except Exception:
            pass
    windowed = hard_dedupe(windowed)
    print(f"⏱️  In-window, deduped: {len(windowed)}")

    scored = []
    for it in windowed:
        text = f"{it.get('title','')} {it.get('snippet','')}".lower()
        title_l = it.get("title", "").lower()
        generic = _count(GENERIC_PATTERNS, title_l) + _count(PROMO_PATTERNS, title_l)
        scored.append(score_item_improved(
            it, now_utc,
            _count(TIER1_LAUNCH_PATTERNS, text), _count(TIER2_ACTIVITY_PATTERNS, text),
            _count(COMMENTARY_PATTERNS, text), _count(LISTICLE_PATTERNS, title_l), generic,
        ))
    return cluster_and_select(scored, now_utc=now_utc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", choices=["rss", "items"], default="rss",
                    help="rss = live fetch (default); items = reuse out/items_last24h.json")
    ap.add_argument("--no-fulltext", action="store_true",
                    help="skip Jina full-text enrichment (faster offline; classify on title+snippet)")
    args = ap.parse_args()
    use_fulltext = not args.no_fulltext

    cfg = load_config()
    tiers, default_tier = load_sources()

    if args.input == "items":
        items = json.loads((_PROJECT_ROOT / "out" / "items_last24h.json").read_text())
        print(f"📥 Loaded {len(items)} pre-scored items (offline tail test)")
    else:
        items = build_scored_items(cfg)
    print(f"🔧 full-text: {'on (Jina)' if use_fulltext else 'off'}   sources tiered: {len(tiers)}")

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    dedup = DedupAgent(db_path=STATE_DIR / "posted_articles.db",
                       seen_titles=[], feed_entries=[], enable_ai_tiebreaker=False)
    kept, killed, review = [], [], []
    skipped_dup = skipped_low = n_fulltext = 0

    for it in sorted(items, key=lambda x: x.get("score", 0), reverse=True):
        # Single shared brain (src/pipeline_v2). The preview differs from production
        # ONLY in dedup target (isolated DB below) and outputs — never in judgement.
        rec = pipeline_v2.evaluate_item(it, tiers, default_tier, use_fulltext=use_fulltext)
        if rec is None:
            continue
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
        # kept → isolated deterministic dedup (never touches production state), then keep.
        is_dup, _ = dedup.is_duplicate(rec["title"], rec["link"], rec["snippet"])
        if is_dup:
            skipped_dup += 1
            continue
        dedup.record(title=rec["title"], url=rec["link"],
                     category=rec["category"], priority=rec["source_tier"])
        kept.append(rec)

    dedup.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, data in [("kept", kept), ("killed", killed), ("review", review)]:
        (OUT_DIR / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    meta = {
        "source": "standalone", "label": "Standalone (v2)", "input": args.input,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(kept) + len(killed) + len(review),
        "keep": len(kept), "kill": len(killed), "review": len(review),
        "deduped": skipped_dup, "below_score": skipped_low,
        "fulltext_fetched": n_fulltext,
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, indent=2))

    print(f"\n✅ KEEP {len(kept)}   🗑️ KILL {len(killed)}   🔎 REVIEW {len(review)}"
          f"   (deduped {skipped_dup}, below score {skipped_low}, full-text {n_fulltext})")
    print(f"📄 {OUT_DIR}/  — 0 paid/LLM calls, Telegram excluded, production untouched")
    if kept:
        print("\nTop kept:")
        for r in kept[:10]:
            reg = ",".join(r["regions"]) or "—"
            print(f"  [{r['score']:>3}] {r['category']:<13} {reg:<10} {r['title'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
