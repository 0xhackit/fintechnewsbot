import json
import re
from datetime import datetime, timezone, timedelta

from .fetchers import fetch_google_news_rss, fetch_telegram_public_channels
from .normalize import normalize_item
from .match import match_item
from .dedupe import hard_dedupe, cluster_and_select
from .output import write_json, write_markdown_digest
from .utils import ensure_parent_dir


# =========================
# Scoring / ranking engine
# =========================

TIER1_LAUNCH_PATTERNS = [
    r"\blaunch(?:es|ed|ing)?\b",
    r"\bunveil(?:s|ed|ing)?\b",
    r"\bintroduc(?:es|ed|ing)?\b",
    r"\brolls?\s+out\b",
    r"\bgo(?:es)?\s+live\b",
    r"\bpartners?\s+with\b",
    r"\bteams?\s+up\s+with\b",
    r"\bjoins?\s+forces\b",
    r"\bcollaborat(?:es|ed|ing)?\s+with\b",
    r"\bannounc(?:es|ed|ing)\b",
    r"\bto\s+launch\b",
    r"\bplans?\s+to\s+launch\b",
    r"\braises?\b",
    r"\bseries\s+[abc]\b",
    r"\bfunding\b",
    r"\bacquires?\b",
    r"\bacquisition\b",
    r"\bintegrat(?:es|ed|ing)?\b",
    r"\badds?\s+support\b",
    r"\bexpands?\s+to\b",
    r"\bpilot\b",
    r"\btrial\b",
    r"\bmainnet\b",
    r"\btestnet\b",
]

TIER2_ACTIVITY_PATTERNS = [
    r"\bissu(?:es|ed|ance)\b",
    r"\bdeploy(?:s|ed|ing)?\b",
    r"\benabl(?:es|ed|ing)?\b",
    r"\badopt(?:s|ed|ing)?\b",
    r"\bsettlement\b",
    r"\btokeniz(?:es|ed|ing|ation)\b",
    r"\blicen[cs]e\b",
    r"\bauthori[sz]ed\b",
]

COMMENTARY_PATTERNS = [
    r"\bdeep\s+dive\b",
    r"\bexplainer\b",
    r"\bwhat\s+is\b",
    r"\bhow\b",
    r"\bwhy\b",
    r"\beverything\s+you\s+need\b",
    r"\bguide\b",
    r"\bopinion\b",
    r"\banalysis\b",
    r"\btrends\b",
    r"\boutlook\b",
    r"\bforecast\b",
    r"\bcould\b",
    r"\bmay\b",
    r"\bmight\b",
]


def _count(patterns, text: str) -> int:
    t = (text or "").lower()
    return sum(1 for p in patterns if re.search(p, t))


def score_item(item: dict, now_utc: datetime) -> dict:
    """Attach `score` + `score_breakdown` to an item dict and return it."""
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()

    tier1 = _count(TIER1_LAUNCH_PATTERNS, text)
    tier2 = _count(TIER2_ACTIVITY_PATTERNS, text)
    comm = _count(COMMENTARY_PATTERNS, text)

    launch_score = min(tier1 * 25, 60) + min(tier2 * 10, 30)
    commentary_penalty = -min(comm * 20, 50)

    freshness = 0
    try:
        if item.get("published_at"):
            dt = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
            hours = (now_utc - dt).total_seconds() / 3600
            if hours <= 6:
                freshness = 10
            elif hours <= 24:
                freshness = 4
    except Exception:
        pass

    score = launch_score + commentary_penalty + freshness

    # Overrides: ensure launches outrank commentary
    if tier1 >= 1 and comm <= 1:
        score = max(score, 35)
    if comm >= 2 and tier1 == 0:
        score = min(score, 10)

    item["score"] = int(score)
    item["score_breakdown"] = {
        "tier1": tier1,
        "tier2": tier2,
        "commentary": comm,
        "freshness": freshness,
        "launch_score": launch_score,
        "commentary_penalty": commentary_penalty,
    }
    return item


# =========================
# Hard filters (noise kill + crypto anchor gate)
# =========================

CRYPTO_ANCHORS = [
    "stablecoin",
    "blockchain",
    "crypto",
    "on-chain",
    "onchain",
    "tokenized",
    "tokenization",
    "digital asset",
    "digital assets",
    "usdc",
    "usdt",
    "rwa",
]

NOISE_PATTERNS = [
    "watching your wallet",
    "holiday",
    "saving",
    "savings",
    "college",
    "student",
    "shopping",
    "plants",
    "budget",
    "financial literacy",
    "credit card debt",
    "scholarship",
    "retirement",
    "abc",
    "fresno",
]


def has_crypto_anchor(item: dict) -> bool:
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    return any(w in text for w in CRYPTO_ANCHORS)


def is_noise(item: dict) -> bool:
    text = f"{item.get('title','')} {item.get('snippet','')}".lower()
    return any(p in text for p in NOISE_PATTERNS)


def load_config(path: str = "config.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    cfg = load_config()

    lookback_hours = int(cfg.get("lookback_hours", 24))
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=lookback_hours)

    out_json = cfg.get("output", {}).get("json_path", "out/items_last24h.json")
    out_md = cfg.get("output", {}).get("md_path", "out/digest.md")
    ensure_parent_dir(out_json)
    ensure_parent_dir(out_md)

    raw_items = []
    if cfg.get("google_news_rss", {}).get("enabled", True):
        feeds = cfg.get("google_news_rss", {}).get("feeds", {})
        for feed_name, feed_url in feeds.items():
            items = fetch_google_news_rss(
                feed_name=feed_name,
                feed_url=feed_url,
                http_cfg=cfg.get("http", {}),
            )
            raw_items.extend(items)

    # Telegram public channels (optional)
    tg_cfg = cfg.get("telegram", {}) or {}
    if tg_cfg.get("enabled"):
        channels = tg_cfg.get("channels", []) or []
        max_msgs = int(tg_cfg.get("max_messages_per_channel", 200))
        session_path = tg_cfg.get("session_path", "tg.session")
        require_primary_link = bool(tg_cfg.get("require_primary_link", True))
        event_keywords = tg_cfg.get("event_keywords", []) or []

        print(f"\n🟦 Telegram: fetching from {len(channels)} channel(s)...")
        try:
            tg_items = fetch_telegram_public_channels(
                channels=channels,
                max_messages_per_channel=max_msgs,
                session_path=session_path,
                require_primary_link=require_primary_link,
                event_keywords=event_keywords,
            )
            print(f"🟦 Telegram: fetched {len(tg_items)} item(s)")
            raw_items.extend(tg_items)
        except Exception as e:
            print(f"⚠️  Telegram fetch failed (continuing with RSS only): {e}")

    print(f"\n📥 Raw items fetched: {len(raw_items)}")

    from collections import Counter

    raw_src_types = Counter([(r.get("source_type") or "rss") for r in raw_items])
    raw_sources = Counter([(r.get("source") or "Unknown") for r in raw_items])
    print("🧾 Raw source_type counts:", raw_src_types.most_common(10))
    print("🧾 Raw source counts:", raw_sources.most_common(10))

    write_json("out/debug_raw.json", raw_items)
    print("🧪 Wrote debug: out/debug_raw.json")

    normalized = []
    for r in raw_items:
        n = normalize_item(r, fetched_at=now_utc)
        if n is not None:
            normalized.append(n)

    print(f"🧹 Normalized items: {len(normalized)}")

    matched = []
    for item in normalized:
        m = match_item(item, cfg.get("keywords", []), cfg.get("topics", []))

        if not (m.get("matched_keywords") or m.get("matched_topics")):
            continue
        if is_noise(m):
            continue

        # Crypto-anchor gate is useful for noisy Google News queries, but Telegram items
        # are already gated at ingestion time (primary link OR event keyword). Don't
        # drop Telegram items just because they don't contain anchor words.
        if (m.get("source_type") or "").lower() != "telegram":
            if not has_crypto_anchor(m):
                continue

        matched.append(m)

    print(f"🎯 Matched items: {len(matched)}")

    src_counts = Counter([i.get("source") for i in matched])
    print("🏷 Top sources:", src_counts.most_common(10))

    kw_counts = Counter()
    for i in matched:
        for kw in i.get("matched_keywords") or []:
            kw_counts[kw] += 1
    print("🔑 Top keywords:", kw_counts.most_common(15))

    # Windowing: drop undated and out-of-window items entirely
    windowed = []
    dropped_undated = []
    dropped_old = []

    for item in matched:
        published_at = item.get("published_at")
        if not published_at:
            dropped_undated.append(item)
            continue

        try:
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except Exception:
            dropped_undated.append(item)
            continue

        if dt < cutoff:
            dropped_old.append(item)
            continue

        windowed.append(item)

    print(f"⏱️  In window (last {lookback_hours}h): {len(windowed)}")
    print(f"🗑️  Dropped undated: {len(dropped_undated)}")
    print(f"🗑️  Dropped older than window: {len(dropped_old)}")

    write_json("out/debug_dropped_undated.json", dropped_undated)
    write_json("out/debug_dropped_old.json", dropped_old)
    print("🧪 Wrote debug: out/debug_dropped_undated.json")
    print("🧪 Wrote debug: out/debug_dropped_old.json")

    # 1) Hard dedupe first
    windowed = hard_dedupe(windowed)

    # 2) Base scoring
    windowed_scored = [score_item(it, now_utc) for it in windowed]

    # 3) Cluster similar titles across sources, apply consensus boost, select representative
    windowed_clustered = cluster_and_select(windowed_scored, now_utc=now_utc)

    # 4) Final sort
    windowed_clustered.sort(
        key=lambda x: (x.get("score", 0), x.get("published_at") or ""),
        reverse=True,
    )

    final_items = windowed_clustered

    write_json(out_json, final_items)

    write_markdown_digest(
        out_md,
        now_utc=now_utc,
        lookback_hours=lookback_hours,
        windowed=final_items,
        undated=[],
        topics=cfg.get("topics", []),
    )

    print(f"\n✅ Wrote JSON: {out_json} ({len(final_items)} items)")
    print(f"✅ Wrote Markdown: {out_md}")
    return 0