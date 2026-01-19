from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dateutil import parser as dateparser


from .utils import strip_html, canonicalize_url, stable_id


def parse_published(raw: Dict[str, Any]) -> tuple[Optional[str], str]:
    """
    Return (published_at_iso, confidence)
    """
    # Best: structured parsed date (time.struct_time)
    sp = raw.get("published_parsed")
    if sp:
        try:
            dt = datetime(*sp[:6], tzinfo=timezone.utc)
            return dt.isoformat(), "high"
        except Exception:
            pass

    # Next: parse string
    s = (raw.get("published") or "").strip()
    if s:
        try:
            dt = dateparser.parse(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat(), "medium"
        except Exception:
            return None, "low"

    return None, "low"


def normalize_item(raw: Dict[str, Any], fetched_at: datetime) -> Optional[Dict[str, Any]]:
    title = (raw.get("title") or "").strip()
    url = (raw.get("link") or "").strip()
    if not title or not url:
        return None

    snippet = strip_html(raw.get("description") or "")
    canonical = canonicalize_url(url)

    published_at, conf = parse_published(raw)

    item = {
        "id": stable_id(canonical, title),
        "source": raw.get("source") or "Unknown",
        "source_type": raw.get("source_type") or "unknown",
        "feed_name": raw.get("feed_name"),
        "title": title,
        "url": url,
        "canonical_url": canonical,
        "snippet": snippet[:300] if snippet else "",
        "published_at": published_at,  # ISO8601 or None
        "published_at_confidence": conf,
        "fetched_at": fetched_at.isoformat(),
        "matched_keywords": [],
        "matched_topics": [],
        "raw": raw.get("raw") or {},
    }
    return item