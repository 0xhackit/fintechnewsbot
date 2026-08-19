"""
enrich_fulltext.py — full-text enrichment via Jina Reader (vendored adapter).

The one adapter we take from `agent-reach` (github.com/Panniantong/agent-reach) —
vendored, not a framework dependency. RSS gives only title + snippet; the full
article body makes slop-detection, region/content-type tagging, and consensus far
more accurate.

  fetch_fulltext(url) -> str | None    GET https://r.jina.ai/<url>  (free, no API key)

- On-disk cache by URL hash so re-runs don't refetch.
- Fail-soft: any error / non-200 / empty body returns None (caller keeps the item
  on title + snippet — never drops it).
- Only call this on survivors of the cheap title+snippet gate (the network fetch is
  the cost; spend it on the ~120/day survivors, not the ~800 raw items).
"""

import hashlib
from pathlib import Path

from .utils import make_session

CACHE_DIR = Path("state/standalone/fulltext_cache")
_JINA = "https://r.jina.ai/"
_MAX_CHARS = 6000

_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        _SESSION = make_session({"retries_total": 2, "backoff_factor": 0.5})
    return _SESSION


def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{h}.txt"


def fetch_fulltext(url: str, timeout: int = 20) -> str | None:
    """Return cleaned article body (capped) or None. Never raises."""
    if not url:
        return None

    cp = _cache_path(url)
    if cp.exists():
        try:
            cached = cp.read_text(encoding="utf-8")
            return cached or None
        except Exception:
            pass

    try:
        resp = _session().get(
            f"{_JINA}{url}",
            timeout=timeout,
            headers={"Accept": "text/plain", "User-Agent": "fintech-news-bot/1.0"},
        )
        if resp.status_code != 200:
            return None
        text = (resp.text or "").strip()
        if not text:
            return None
        text = text[:_MAX_CHARS]
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cp.write_text(text, encoding="utf-8")
        except Exception:
            pass
        return text
    except Exception:
        return None


if __name__ == "__main__":
    # Smoke test: fetch a stable public URL, then confirm cache + fail-soft.
    demo = "https://example.com/"
    body = fetch_fulltext(demo)
    print("fetched:", "ok" if body else "none", f"({len(body) if body else 0} chars)")
    print("cached :", _cache_path(demo).exists())
    print("failsoft:", fetch_fulltext("") is None and fetch_fulltext("not-a-real-scheme://x") is None)
