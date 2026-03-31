"""
Unified dedup agent: consolidates SQLite DB, seen_alerts titles, feed.json,
and session cache into one authoritative duplicate checker.

Uses Claude Haiku as a tiebreaker for borderline cases (shared entity but
low Jaccard overlap).
"""

import json
import logging
import os
import sqlite3
import hashlib
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .utils import (
    normalize_title,
    canonicalize_url,
    tokenize_title,
    jaccard_similarity,
    extract_entities,
    get_event_type,
)

logger = logging.getLogger(__name__)

DB_PATH = Path("state/posted_articles.db")

# Thresholds
SEQ_THRESHOLD = 0.75
LAUNCH_SEQ_THRESHOLD = 0.60

# Generic news words that shouldn't trigger shared-token dedup
# These appear across unrelated articles and would cause false positives
_GENERIC_NEWS_WORDS = {
    # Finance/business terms
    "million", "billion", "raises", "raise", "funding", "fund", "funds",
    "launches", "launch", "launched", "platform", "service", "services",
    "company", "companies", "firm", "firms", "market", "markets",
    "digital", "asset", "assets", "token", "tokens", "tokenized",
    "crypto", "cryptocurrency", "blockchain", "payment", "payments",
    "bank", "banking", "financial", "finance", "fintech",
    "trading", "trade", "exchange", "investors", "investor",
    "stablecoin", "stablecoins", "custody", "lending", "defi",
    "global", "network", "protocol", "infrastructure",
    "partners", "partner", "partnership", "deal",
    "series", "round", "venture", "capital",
    "regulatory", "regulation", "compliance", "license",
    "report", "reports", "according", "announced", "announce",
    "expansion", "expands", "expand", "growth", "revenue",
    "users", "customers", "clients",
    # Actions
    "enables", "enabling", "support", "supports", "adds",
    "targets", "plans", "eyes", "seeks", "backs",
    "acquires", "acquisition", "merger",
}

# Claude model for tiebreaker
TIEBREAKER_MODEL = "claude-haiku-4-5-20251001"

TIEBREAKER_PROMPT = """Are these two headlines about the SAME specific event/announcement?

HEADLINE A: {title_a}
HEADLINE B: {title_b}

Respond with ONLY valid JSON (no markdown):
{{"is_duplicate": true or false, "reason": "one sentence"}}"""


class DedupAgent:
    """Unified dedup: SQLite DB + seen_alerts titles + feed.json + session cache.
    Uses Claude Haiku as tiebreaker for borderline cases."""

    def __init__(
        self,
        db_path: Path = DB_PATH,
        seen_titles: list[dict] | None = None,
        feed_entries: list[dict] | None = None,
        enable_ai_tiebreaker: bool = True,
    ):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._ensure_table()

        # Build unified title list from all sources
        self._all_titles: list[dict] = []  # [{title, link}]
        self._session_cache: list[dict] = []  # Titles added in this batch

        # Load seen_alerts titles
        for t in (seen_titles or []):
            if t.get("title"):
                self._all_titles.append({"title": t["title"], "link": t.get("link", "")})

        # Load feed.json entries
        for fe in (feed_entries or []):
            if fe.get("title"):
                self._all_titles.append({"title": fe["title"], "link": fe.get("link", "")})

        # Load SQLite titles (last 500)
        rows = self.conn.execute(
            "SELECT title, url FROM posted_articles ORDER BY id DESC LIMIT 500"
        ).fetchall()
        for title, url in rows:
            self._all_titles.append({"title": title, "link": url})

        self.enable_ai_tiebreaker = enable_ai_tiebreaker and bool(
            os.environ.get("ANTHROPIC_API_KEY")
        )

        logger.info(
            f"DedupAgent initialized: {len(self._all_titles)} titles loaded, "
            f"AI tiebreaker={'ON' if self.enable_ai_tiebreaker else 'OFF'}"
        )

    def _ensure_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                title_normalized TEXT NOT NULL,
                posted_at TEXT NOT NULL,
                category TEXT DEFAULT '',
                priority TEXT DEFAULT ''
            )
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_url_hash ON posted_articles(url_hash)"
        )
        self.conn.commit()

    def _url_hash(self, url: str) -> str:
        canonical = canonicalize_url((url or "").strip())
        return hashlib.sha256(canonical.lower().encode("utf-8")).hexdigest()

    def is_duplicate(self, title: str, url: str, snippet: str = "") -> tuple[bool, str]:
        """Check all dedup sources. Returns (is_dup, reason)."""

        # Step 1: Exact URL match (SQLite)
        url_hash = self._url_hash(url)
        row = self.conn.execute(
            "SELECT title FROM posted_articles WHERE url_hash = ?", (url_hash,)
        ).fetchone()
        if row:
            return True, f"exact URL match (previously: \"{row[0][:80]}\")"

        # Step 2: Title-based matching against all sources
        current_tokens = tokenize_title(title)
        current_entities = extract_entities(title)
        current_event = get_event_type(title)
        is_launch = current_event is not None
        seq_threshold = LAUNCH_SEQ_THRESHOLD if is_launch else SEQ_THRESHOLD

        # Check against all titles (seen_alerts + feed.json + SQLite + session cache)
        all_to_check = self._all_titles + self._session_cache
        borderline_match: Optional[str] = None

        for entry in all_to_check:
            seen_title = entry.get("title", "")
            if not seen_title:
                continue

            norm_current = normalize_title(title)
            norm_seen = normalize_title(seen_title)
            seq_sim = SequenceMatcher(None, norm_current, norm_seen).ratio()

            seen_tokens = tokenize_title(seen_title)
            jac_sim = jaccard_similarity(current_tokens, seen_tokens)

            seen_entities = extract_entities(seen_title)
            shared_entities = current_entities & seen_entities
            seen_event = get_event_type(seen_title)

            # High-confidence matches — no AI needed

            # (A) Same entity + same event type: aggressive dedup
            if is_launch and seen_event is not None:
                if shared_entities and current_event == seen_event:
                    if seq_sim >= 0.50 or jac_sim >= 0.30:
                        return True, f"entity+event match ({list(shared_entities)[0]}, {current_event}): \"{seen_title[:80]}\""
                elif shared_entities:
                    if seq_sim >= 0.80:
                        return True, f"entity match (seq={seq_sim:.2f}): \"{seen_title[:80]}\""
                else:
                    if seq_sim >= 0.85:
                        return True, f"high seq similarity ({seq_sim:.2f}): \"{seen_title[:80]}\""
            else:
                if seq_sim >= seq_threshold:
                    return True, f"seq similarity ({seq_sim:.2f}): \"{seen_title[:80]}\""

            # (B) 2+ shared entities with any token overlap
            if len(shared_entities) >= 2 and jac_sim >= 0.10:
                return True, f"multi-entity match ({shared_entities}): \"{seen_title[:80]}\""

            # (C) Shared entity + meaningful Jaccard
            if shared_entities and jac_sim >= 0.25:
                return True, f"entity+token match ({list(shared_entities)[0]}, jac={jac_sim:.2f}): \"{seen_title[:80]}\""

            # (D) Shared rare token + moderate Jaccard (catches unknown entities like "Midas")
            # Rare = not a stopword, not generic news vocabulary, length >= 4
            shared_tokens = current_tokens & seen_tokens
            rare_shared = shared_tokens - _GENERIC_NEWS_WORDS
            if rare_shared and jac_sim >= 0.20:
                sample = sorted(rare_shared)[0]
                return True, f"shared-token match ({sample}, jac={jac_sim:.2f}): \"{seen_title[:80]}\""

            # (E) High Jaccard alone
            if jac_sim >= 0.50:
                return True, f"high token overlap (jac={jac_sim:.2f}): \"{seen_title[:80]}\""

            # (F) Borderline: shared entity + low Jaccard (0.15-0.25) → AI tiebreaker candidate
            if shared_entities and 0.15 <= jac_sim < 0.25 and borderline_match is None:
                borderline_match = seen_title

        # Step 3: AI tiebreaker for borderline cases
        if borderline_match and self.enable_ai_tiebreaker:
            is_dup, reason = self._ai_tiebreaker(title, borderline_match)
            if is_dup:
                return True, f"AI tiebreaker: {reason} (vs \"{borderline_match[:80]}\")"

        return False, ""

    def _ai_tiebreaker(self, title_a: str, title_b: str) -> tuple[bool, str]:
        """Use Claude Haiku to decide if two borderline titles are duplicates."""
        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            prompt = TIEBREAKER_PROMPT.format(title_a=title_a, title_b=title_b)

            message = client.messages.create(
                model=TIEBREAKER_MODEL,
                max_tokens=128,
                messages=[{"role": "user", "content": prompt}],
            )

            text = message.content[0].text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

            result = json.loads(text)
            return bool(result.get("is_duplicate", False)), result.get("reason", "")

        except Exception as e:
            logger.warning(f"AI tiebreaker failed ({e}), defaulting to not-duplicate")
            return False, ""

    def record(self, title: str, url: str, category: str = "", priority: str = ""):
        """Record a posted article in SQLite + session cache."""
        self.conn.execute(
            """INSERT INTO posted_articles
               (url_hash, url, title, title_normalized, posted_at, category, priority)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                self._url_hash(url),
                (url or "").strip(),
                (title or "").strip(),
                normalize_title(title),
                datetime.now(timezone.utc).isoformat(),
                category,
                priority,
            ),
        )
        self.conn.commit()
        self._session_cache.append({"title": title, "link": url})

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
