from typing import List, Dict, Any, Optional
import os
import re
from datetime import timezone

import feedparser

from .utils import make_session

import asyncio

# Lazy import: Telegram support is optional and only used if enabled/configured.
try:
    from telethon import TelegramClient
except Exception:  # pragma: no cover
    TelegramClient = None


def fetch_google_news_rss(feed_name: str, feed_url: str, http_cfg: dict) -> List[Dict[str, Any]]:
    """
    Fetch Google News RSS URL and return raw items:
    {source_type, source, feed_name, title, link, description, published, raw}
    """
    session = make_session(http_cfg)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept": "application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    print(f"📰 Fetching Google News RSS [{feed_name}] ...")
    r = session.get(feed_url, headers=headers, timeout=int(http_cfg.get("timeout_seconds", 20)))

    ctype = (r.headers.get("Content-Type") or "").lower()
    print(f"   ↳ HTTP {r.status_code}, content-type={ctype}, bytes={len(r.content)}")

    if r.status_code >= 400:
        snippet = (r.text or "")[:200]
        print(f"⚠️  Feed failed [{feed_name}] HTTP {r.status_code}: {snippet}")
        return []

    feed = feedparser.parse(r.content)
    entries = getattr(feed, "entries", []) or []
    print(f"   ↳ entries={len(entries)}, bozo={getattr(feed, 'bozo', 0)}")

    items = []
    for e in entries:
        items.append({
            "source_type": "google_news_rss",
            "source": "Google News RSS",
            "feed_name": feed_name,
            "title": e.get("title", "") or "",
            "link": e.get("link", "") or "",
            "description": e.get("summary", "") or e.get("description", "") or "",
            "published": e.get("published", "") or e.get("updated", "") or "",
            "published_parsed": e.get("published_parsed") or e.get("updated_parsed"),
            "raw": {
                "id": e.get("id"),
                "guidislink": e.get("guidislink"),
            },
        })

    return items


# =========================
# Telegram (public channels) ingestion
# =========================

_URL_RE = re.compile(r"https?://\S+")


def _extract_first_url(text: str) -> str:
    if not text:
        return ""
    m = _URL_RE.search(text)
    return m.group(0) if m else ""


def _tg_permalink(channel_username: str, msg_id: int) -> str:
    u = (channel_username or "").lstrip("@")
    if not u or not msg_id:
        return ""
    return f"https://t.me/{u}/{msg_id}"


def fetch_telegram_public_channels(
    channels: List[str],
    max_messages_per_channel: int = 200,
    session_path: str = "tg.session",
    require_primary_link: bool = True,
    event_keywords: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Fetch recent messages from public Telegram channels.

    Uses Telethon (MTProto). Requires environment variables:
      - TG_API_ID
      - TG_API_HASH

    Returns raw items shaped similarly to other fetchers so they can flow through
    normalize/match/scoring:
      {source_type, source, source_name, title, link, description, published, raw}

    A lightweight gate is applied:
      - if require_primary_link=True, keep messages with an external URL OR any event keyword
      - if require_primary_link=False, keep messages with an external URL OR any event keyword
    """
    if not channels:
        return []

    if TelegramClient is None:
        raise RuntimeError(
            "Telethon is not installed. Install it with: pip install telethon"
        )

    api_id_raw = (os.environ.get("TG_API_ID") or "").strip()
    api_hash = (os.environ.get("TG_API_HASH") or "").strip()
    if not api_id_raw or not api_hash:
        raise RuntimeError("Missing TG_API_ID or TG_API_HASH environment variables")

    try:
        api_id = int(api_id_raw)
    except Exception:
        raise RuntimeError("TG_API_ID must be an integer")

    event_keywords = event_keywords or []

    def passes_gate(text: str) -> bool:
        t = (text or "").lower()
        has_url = bool(_extract_first_url(text))

        # If primary link is required, URL passes immediately.
        if require_primary_link and has_url:
            return True

        # Accept if event keyword matches.
        for kw in event_keywords:
            if (kw or "").lower() in t:
                return True

        # If primary link is not required, URL-only also passes.
        if not require_primary_link and has_url:
            return True

        return False

    async def _run() -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        print(f"🟦 Fetching Telegram channels: {len(channels)}")

        # Creates/uses a local session file. First run may prompt a login code.
        async with TelegramClient(session_path, api_id, api_hash) as client:
            for ch in channels:
                ch = (ch or "").strip()
                if not ch:
                    continue

                # Accept @handle or plain handle.
                if not ch.startswith("@"):  # public username
                    ch = "@" + ch

                try:
                    async for msg in client.iter_messages(ch, limit=max_messages_per_channel):
                        if not msg or not getattr(msg, "message", None):
                            continue

                        text = (msg.message or "").strip()
                        if not text:
                            continue

                        if not passes_gate(text):
                            continue

                        dt = getattr(msg, "date", None)
                        published_iso = ""
                        if dt:
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            dt_utc = dt.astimezone(timezone.utc)
                            published_iso = dt_utc.isoformat().replace("+00:00", "Z")

                        external_url = _extract_first_url(text)
                        permalink = _tg_permalink(ch, getattr(msg, "id", 0))

                        title = text.split("\n", 1)[0].strip()
                        if len(title) > 160:
                            title = title[:157] + "..."

                        description = text
                        if len(description) > 800:
                            description = description[:797] + "..."

                        items.append(
                            {
                                "source_type": "telegram",
                                "source": "Telegram",
                                "source_name": ch,
                                "title": title,
                                "link": external_url or permalink,
                                "description": description,
                                "published": published_iso,
                                "raw": {
                                    "tg_permalink": permalink,
                                    "external_url": external_url or None,
                                    "message_id": getattr(msg, "id", None),
                                },
                            }
                        )
                except Exception as e:
                    # Don't fail the entire run because one channel is missing/private/etc.
                    print(f"⚠️  Telegram channel failed {ch}: {e}")
                    continue

        print(f"🟦 Telegram items fetched (post-gate): {len(items)}")
        return items

    # Python 3.14+: Telethon requires an explicit running loop.
    return asyncio.run(_run())