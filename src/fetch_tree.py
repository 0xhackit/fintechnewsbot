#!/usr/bin/env python3
"""
fetch_tree.py — TreeOfAlpha ingestion + cross-source consensus merge.

TreeOfAlpha aggregates X/Twitter + blogs + wires into one structured, real-time,
server-friendly stream (no cookies, no ban risk). It's noisy, so it rides the SAME
v2 gate as RSS. The payoff is CONSENSUS: when Tree and RSS both report a story, that
corroboration bumps it to auto-publish; a Tree-only item stands as a single source.

Shared by scripts/fetch_tree_local.py (isolated preview) and scripts/prepare_alerts_v2.py
(production). The public history endpoint needs no key; the API key only removes the
real-time delay on the WebSocket, a later upgrade (never put the key on the CLI — env
var TREE_API_KEY when we add the WS path).
"""
import re
from datetime import datetime, timezone, timedelta

import requests

from src.app import (
    load_blocklist, is_blocklisted, is_noise, is_pr_noise, has_crypto_anchor,
    _count, TIER1_LAUNCH_PATTERNS, TIER2_ACTIVITY_PATTERNS, COMMENTARY_PATTERNS,
    LISTICLE_PATTERNS, GENERIC_PATTERNS, PROMO_PATTERNS,
)
from src.match import match_item
from src.improved_scoring import score_item_improved
from src.utils import tokenize_title, jaccard_similarity, extract_entities

TREE_URL = "https://news.treeofalpha.com/api/news"

# Tree items are single-source + unverified → Tier C by default. A few aggregator
# sources Tree relays are reliable enough to treat as Tier B (still editorial-gated).
TREE_DEFAULT_TIER = "C"
TREE_TRUSTED_TIER_B = {
    "tree:the block", "tree:theblock", "tree:coindesk", "tree:bloomberg",
    "tree:reuters", "tree:wsj", "tree:the information", "tree:ft",
}

_TWEET_RE = re.compile(r"^(?P<name>.+?)\s+\((?P<handle>@[A-Za-z0-9_]+)\):\s*(?P<text>.*)$", re.DOTALL)
_BLOG_RE = re.compile(r"^(?P<src>[A-Z][^:]{1,30}):\s*(?P<text>.*)$", re.DOTALL)


def tree_tier(feed_name: str) -> str:
    return "B" if feed_name.lower() in TREE_TRUSTED_TIER_B else TREE_DEFAULT_TIER


def fetch_raw(limit: int = 200, fixture=None) -> list[dict]:
    if fixture is not None:
        import json
        from pathlib import Path
        return json.loads(Path(fixture).read_text(encoding="utf-8"))
    r = requests.get(TREE_URL, params={"limit": limit},
                     headers={"User-Agent": "fintech-news-bot/1.0"}, timeout=25)
    r.raise_for_status()
    return r.json()


def normalize(raw: dict) -> dict | None:
    """TreeOfAlpha item → our item schema (title/link/snippet/published_at/feed_name/…)."""
    title_full = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()
    if not title_full or not url:
        return None
    source = raw.get("source") or ""
    coins = [s.get("coin") for s in (raw.get("suggestions") or []) if s.get("coin")]

    handle, text = None, title_full
    if source == "Twitter":
        m = _TWEET_RE.match(title_full)
        if m:
            handle = m.group("handle")
            text = m.group("text").strip()
        feed_name = f"tree:x:{(handle or '').lstrip('@').lower()}"
    else:
        m = _BLOG_RE.match(title_full)
        src_label = m.group("src").strip().lower() if m else source.lower()
        if m:
            text = m.group("text").strip()
        feed_name = f"tree:{src_label}"

    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    try:
        published_at = datetime.fromtimestamp(int(raw.get("time")) / 1000, tz=timezone.utc).isoformat()
    except Exception:
        published_at = ""

    return {
        "title": text[:220], "snippet": text[:300],
        "url": url, "link": url, "published_at": published_at,
        "source": f"TreeOfAlpha/{source}", "source_type": "treeofalpha",
        "feed_name": feed_name, "handle": handle, "coins": coins,
        "cluster_size": 1, "cluster_sources": [f"tree:{source}"],
    }


def fetch_tree_items(cfg: dict, limit: int = 200, window_hours: int = 24,
                     fixture=None, now=None) -> tuple[list[dict], dict]:
    """Fetch → normalize → relevance-filter → score. Returns (scored_items, stats)."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)
    blocklist = load_blocklist()
    raw_items = fetch_raw(limit, fixture)

    scored, n_off, n_old = [], 0, 0
    for raw in raw_items:
        it = normalize(raw)
        if not it:
            continue
        pa = it.get("published_at")
        if pa:
            try:
                if datetime.fromisoformat(pa) < cutoff:
                    n_old += 1
                    continue
            except Exception:
                pass
        m = match_item(it, cfg.get("keywords", []), cfg.get("topics", []))
        matched = bool(m.get("matched_keywords") or m.get("matched_topics"))
        if not (matched or it.get("coins")):
            n_off += 1
            continue
        if is_noise(m) or is_pr_noise(m) or is_blocklisted(m, blocklist):
            n_off += 1
            continue
        if not (has_crypto_anchor(m) or it.get("coins")):
            n_off += 1
            continue
        text = f"{m.get('title','')} {m.get('snippet','')}".lower()
        title_l = m.get("title", "").lower()
        generic = _count(GENERIC_PATTERNS, title_l) + _count(PROMO_PATTERNS, title_l)
        s = score_item_improved(
            m, now,
            _count(TIER1_LAUNCH_PATTERNS, text), _count(TIER2_ACTIVITY_PATTERNS, text),
            _count(COMMENTARY_PATTERNS, text), _count(LISTICLE_PATTERNS, title_l), generic,
        )
        s["origin"] = "tree"
        scored.append(s)
    return scored, {"pulled": len(raw_items), "off_topic": n_off, "out_of_window": n_old}


def _similar(a_title: str, b_title: str) -> bool:
    """Same story? Mirrors run_alerts.is_similar_to_seen's cross-title logic."""
    at, bt = tokenize_title(a_title), tokenize_title(b_title)
    jac = jaccard_similarity(at, bt)
    shared = extract_entities(a_title) & extract_entities(b_title)
    if len(shared) >= 2 and jac >= 0.10:
        return True
    if shared and jac >= 0.25:
        return True
    return jac >= 0.50


def merge_consensus(rss_items: list[dict], tree_items: list[dict]) -> tuple[list[dict], dict]:
    """Corroborate RSS stories with Tree WITHOUT losing RSS's own consensus.

    A Tree item matching an RSS story bumps that story's consensus (+1 source) and is
    absorbed. Unmatched Tree items pass through as standalone single-source candidates.
    Every returned item carries an ``origin`` tag: rss | tree | rss+tree.
    """
    for it in rss_items:
        it.setdefault("origin", "rss")

    corroborated = 0
    standalone = []
    for t in tree_items:
        hit = None
        for r in rss_items:
            if _similar(t.get("title", ""), r.get("title", "")):
                hit = r
                break
        if hit is not None:
            hit["cluster_size"] = int(hit.get("cluster_size") or 1) + 1
            hit.setdefault("cluster_sources", []).append(t.get("cluster_sources", ["tree"])[0])
            hit["origin"] = "rss+tree"
            # Keep the earlier publish time (Tree is usually first).
            if t.get("published_at") and (not hit.get("published_at") or t["published_at"] < hit["published_at"]):
                hit["tree_published_at"] = t["published_at"]
            corroborated += 1
        else:
            standalone.append(t)

    return rss_items + standalone, {
        "tree_scored": len(tree_items),
        "corroborated_rss": corroborated,
        "tree_standalone": len(standalone),
    }
