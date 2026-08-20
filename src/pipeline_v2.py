#!/usr/bin/env python3
"""
pipeline_v2.py — the deterministic v2 editorial gate, shared by two callers:

  • scripts/standalone_pipeline.py  — PREVIEW / shadow: isolated dedup DB, posts
    nowhere. For tuning the pattern banks against live RSS without side effects.
  • scripts/prepare_alerts_v2.py    — PRODUCTION: real dedup state, emits
    out/alerts_drafts.json so the existing Telegram/X posters publish the KEEP set.

Both judge an item with the *same* brain (editorial + region + section + source
tier, $0 LLM). They differ only in dedup target and what they write. Keeping the
judgement in one place means the preview you tune is exactly what production posts.

Flow per item:
    score floor → editorial gate (title+snippet) → full-text enrich survivors →
    re-classify on the body → editorial REVIEW? → balanced high-signal gate →
    bucket = kept | review | killed
"""
import hashlib

from src import editorial
from src import regions as regions_mod
from src.categorize import categorize
from src import enrich_fulltext
from src.utils import canonicalize_url

# Same score floor the live pipeline uses to enter the alert stage.
MIN_SCORE = 35

# --- Balanced high-signal gate (kept vs review) ----------------------------
# A concrete event (already editorial-gated) from a curated Tier-A/B publisher is
# signal on its own; the noisy Tier-C broad web searches must corroborate
# (>=2 sources) or be materially large. Region is a filter, not a gate.
KEEP_TIERS = ("A", "B")
KEEP_MIN_CONSENSUS = 2
KEEP_MIN_FINANCIAL = 40

# --- "High quality -> X" gate (tunable) ------------------------------------
# KEEP is already the high-signal set. X is the public megaphone, so it takes
# only the STRONGEST subset of KEEP: a primary-tier publisher, a materially large
# number, a story several independent outlets are covering, or a very high score.
X_MIN_CONSENSUS = 3
X_MIN_FINANCIAL = 40
X_MIN_SCORE = 70


def stable_item_id(title: str, link: str) -> str:
    """SHA-1 of 'title.lower()|canonical_url.lower()' — identical to
    scripts/run_alerts.py::stable_item_id so dedup/feed IDs stay consistent."""
    link = canonicalize_url(link or "").lower()
    base = f"{(title or '').strip().lower()}|{link}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def qualifies_for_x(rec: dict) -> bool:
    """Deterministic 'high quality' test for X. Strict subset of KEEP."""
    return (
        rec.get("source_tier") == "A"
        or int(rec.get("financial", 0) or 0) >= X_MIN_FINANCIAL
        or int(rec.get("consensus", 0) or 0) >= X_MIN_CONSENSUS
        or int(rec.get("score", 0) or 0) >= X_MIN_SCORE
    )


def _consensus(it: dict) -> int:
    return int(it.get("cluster_size") or len(it.get("cluster_sources") or []) or 1)


def _financial(it: dict) -> int:
    return int((it.get("score_breakdown") or {}).get("financial_bonus", 0) or 0)


def evaluate_item(it: dict, tiers: dict, default_tier: str = "C",
                  use_fulltext: bool = True) -> dict | None:
    """Judge one scored item. Returns a record dict with a 'bucket' key
    (``kept`` | ``review`` | ``killed`` | ``below_score``), or ``None`` when the
    item is unusable (missing title/link). No dedup here — the caller owns dedup
    so the preview (isolated) and production (real state) can diverge on that
    alone. ``n_fulltext`` side effects are surfaced via rec['fulltext'] (bool).
    """
    title = (it.get("title") or "").strip()
    link = (it.get("link") or it.get("url") or "").strip()
    snippet = (it.get("snippet") or "")[:300]
    score = it.get("score", 0)
    feed_name = it.get("feed_name") or ""
    if not title or not link:
        return None
    if score < MIN_SCORE:
        return {"bucket": "below_score"}

    tier = tiers.get(feed_name, {}).get("tier", default_tier)
    region = regions_mod.classify_region(title, snippet)
    cat = categorize(title, snippet)
    base = {
        # SHA-1(title|canonical_url) — same id run_alerts.py / manual-post / promote-to-x
        # use, so drafts, feed entries and dedup state all agree on identity.
        "id": stable_item_id(title, link),
        "title": title, "link": link, "score": score, "snippet": snippet,
        "regions": region["regions"], "primary_region": region["primary"],
        "category": cat["category"], "source_tier": tier,
        "consensus": _consensus(it), "financial": _financial(it),
        "matched_topics": it.get("matched_topics", []),
        "feed_name": feed_name, "source": it.get("source", ""),
        "published_at": it.get("published_at", ""),
    }

    # 1. Editorial gate on title+snippet. This verdict is FINAL — the full-text
    #    enrichment below sharpens category/region only, it does NOT revisit keep/kill.
    #    Re-judging on the fetched body let a market-event verb buried deep in a long
    #    article or tweet ("onboard", "launch") manufacture a KEEP for commentary and
    #    market-recap items — the leak that put opinion/price-wrap tweets on the wire.
    v = editorial.classify(title, snippet)
    if v["verdict"] not in (editorial.KEEP, editorial.REVIEW):
        return {**base, "bucket": "killed", "verdict": v["verdict"], "axis": v["axis"],
                "reason": v["reason"], "matched": v["matched"], "fulltext": False}

    # 2. Enrich survivors — to sharpen category + region only, not the verdict.
    body = enrich_fulltext.fetch_fulltext(link) if use_fulltext else None
    text = body if body else snippet
    region = regions_mod.classify_region(title, text)
    cat = categorize(title, text)
    rec = {**base, "verdict": v["verdict"], "axis": v["axis"], "reason": v["reason"],
           "matched": v["matched"], "regions": region["regions"],
           "primary_region": region["primary"], "category": cat["category"],
           "fulltext": bool(body)}

    # 3. Survived only as editorial REVIEW (ambiguous) → review bucket.
    if v["verdict"] != editorial.KEEP:
        rec["bucket"] = "review"
        return rec

    # 4. Balanced higher-signal gate.
    high_signal = (
        rec["source_tier"] in KEEP_TIERS
        or rec["consensus"] >= KEEP_MIN_CONSENSUS
        or rec["financial"] >= KEEP_MIN_FINANCIAL
    )
    rec["bucket"] = "kept" if high_signal else "review"
    return rec


def build_message_html(title: str, link: str) -> str:
    """Telegram HTML — identical to scripts/run_alerts.py::build_message_html."""
    st = (title or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    sl = (link or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<b>{st}</b> <a href="{sl}">...</a>'


def build_draft(rec: dict) -> dict:
    """Format a KEEP record into the out/alerts_drafts.json schema that
    post_alerts_now.py (Telegram) and scripts/publish_x.py (X) already consume."""
    return {
        "id": rec["id"],
        "title": rec["title"],
        "link": rec["link"],
        "message_html": build_message_html(rec["title"], rec["link"]),
        "score": rec["score"],
        "snippet": rec["snippet"],
        "matched_topics": rec.get("matched_topics", []),
        # Nothing downstream keys off 'tier'; carry the source tier for visibility.
        "tier": rec["source_tier"],
        "post_to_x": qualifies_for_x(rec),
        "category": rec["category"],
        # v2 extras (harmless to the posters, useful in the feed/admin).
        "source_tier": rec["source_tier"],
        "regions": rec.get("regions", []),
        "primary_region": rec.get("primary_region"),
        "source": rec.get("source", ""),
        "feed_name": rec.get("feed_name", ""),
        "published_at": rec.get("published_at", ""),
    }
