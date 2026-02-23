"""
AI-powered article classification and duplicate detection.

This module sits between the scoring pipeline and the posting logic (run_alerts.py).
It provides two layers of filtering:

1. DUPLICATE DETECTION (SQLite)
   - Exact URL match
   - Fuzzy title similarity (configurable threshold)
   - Checked BEFORE calling the API to save costs

2. AI CLASSIFICATION (Claude claude-haiku-4-5-20251001)
   - Determines if an article is genuinely fintech-relevant
   - Returns structured decision: publish (yes/no), reason, category, priority
   - Only called if the article passes dedup

Usage:
    from src.ai_filter import AIArticleFilter

    ai_filter = AIArticleFilter()
    decision = ai_filter.evaluate(item)
    # decision = {"publish": True, "reason": "...", "category": "payments", "priority": "high"}
"""

import os
import json
import sqlite3
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher
from typing import Optional

from .utils import normalize_title

# ---------------------------------------------------------------------------
# Configuration (override these at the top of your script or via config.json)
# ---------------------------------------------------------------------------

# Minimum similarity ratio (0.0 - 1.0) for two titles to be considered duplicates.
# 0.85 is strict enough to catch "same story, different outlet" while allowing
# genuinely different articles about the same topic.
SIMILARITY_THRESHOLD = 0.85

# Categories the AI classifier can assign. Customize this list to match
# what you consider "fintech". Articles outside these categories get filtered.
FINTECH_CATEGORIES = [
    "payments",
    "crypto",
    "banking",
    "regulation",
    "insurtech",
    "lending",
    "tokenization",
    "stablecoins",
    "defi",
    "infrastructure",
    "other",
]

# Toggle logging of filtered (rejected) articles to filtered_log.txt
LOG_FILTERED = True

# Path to the SQLite database for tracking posted articles
DB_PATH = Path("state/posted_articles.db")

# Path to the filtered articles log
FILTERED_LOG_PATH = Path("filtered_log.txt")

# Claude model for classification (fast + cheap)
CLASSIFICATION_MODEL = "claude-haiku-4-5-20251001"

# Maximum tokens for the classification response
MAX_TOKENS = 256

logger = logging.getLogger(__name__)


# ===========================================================================
# SQLite Duplicate Detection
# ===========================================================================

class ArticleDatabase:
    """
    SQLite-backed store for tracking posted articles.
    Used to prevent posting the same story twice.

    Schema:
        - id: auto-increment primary key
        - url_hash: SHA-256 of the canonical URL (for exact match)
        - url: the original URL (for debugging)
        - title: the article title (for fuzzy matching)
        - title_normalized: lowercased, stripped title (for comparison)
        - posted_at: ISO timestamp when the article was posted
        - category: AI-assigned category
        - priority: AI-assigned priority
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._create_table()

    def _create_table(self):
        """Create the posted_articles table if it doesn't exist."""
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
        # Index for fast URL lookups
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_hash ON posted_articles(url_hash)
        """)
        self.conn.commit()

    def _url_hash(self, url: str) -> str:
        """Generate a SHA-256 hash of the URL for exact matching."""
        return hashlib.sha256((url or "").strip().lower().encode("utf-8")).hexdigest()

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison — delegates to shared utils."""
        return normalize_title(title)

    def is_duplicate(self, url: str, title: str, threshold: float = SIMILARITY_THRESHOLD) -> tuple[bool, str]:
        """
        Check if an article is a duplicate of something already posted.

        Returns:
            (is_dup, reason) - True if duplicate, with explanation string.

        Checks in order (cheapest first):
            1. Exact URL hash match
            2. Fuzzy title similarity against recent posts
        """
        # --- Check 1: Exact URL match ---
        url_hash = self._url_hash(url)
        row = self.conn.execute(
            "SELECT title FROM posted_articles WHERE url_hash = ?", (url_hash,)
        ).fetchone()
        if row:
            return True, f"exact URL match (previously posted as: \"{row[0][:80]}\")"

        # --- Check 2: Fuzzy title match ---
        norm_title = self._normalize_title(title)
        if not norm_title:
            return False, ""

        # Only check against last 500 posted articles to keep it fast
        rows = self.conn.execute(
            "SELECT title, title_normalized FROM posted_articles ORDER BY id DESC LIMIT 500"
        ).fetchall()

        for posted_title, posted_norm in rows:
            similarity = SequenceMatcher(None, norm_title, posted_norm).ratio()
            if similarity >= threshold:
                return True, (
                    f"similar title (score={similarity:.2f}): "
                    f"\"{posted_title[:80]}\""
                )

        return False, ""

    def record_posted(self, url: str, title: str, category: str = "", priority: str = ""):
        """Record that an article has been posted (call after successful publish)."""
        self.conn.execute(
            """INSERT INTO posted_articles (url_hash, url, title, title_normalized, posted_at, category, priority)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                self._url_hash(url),
                (url or "").strip(),
                (title or "").strip(),
                self._normalize_title(title),
                datetime.now(timezone.utc).isoformat(),
                category,
                priority,
            ),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


# ===========================================================================
# AI Classification (Claude claude-haiku-4-5-20251001)
# ===========================================================================

# The classification prompt. Strict: only publish articles that are clearly
# and directly about fintech. Generic tech, politics, or loosely related
# business news should be rejected.
CLASSIFICATION_PROMPT = """You are a strict fintech news editor. Your job is to decide whether an article should be published to a fintech-focused Telegram channel and X (Twitter) account.

The channel covers: stablecoins, tokenization, digital assets, crypto infrastructure, institutional crypto adoption, payments technology, banking innovation, fintech regulation, lending/credit tech, and insurtech.

RULES:
- ONLY publish articles that are DIRECTLY and CLEARLY about fintech, crypto infrastructure, digital assets, or financial technology.
- REJECT generic tech news (AI, chips, social media) unless it directly impacts fintech.
- REJECT political news unless it's specifically about fintech/crypto regulation or legislation.
- REJECT loosely related business news (e.g., "Bank X reports quarterly earnings" without fintech angle).
- REJECT price speculation, market commentary, and "top 10" listicles.
- REJECT celebrity crypto endorsements or meme coin hype.
- PRIORITIZE: product launches, partnerships, regulatory actions, funding rounds, institutional adoption, and infrastructure developments.

Given this article:
TITLE: {title}
URL: {url}
SNIPPET: {snippet}

Respond with ONLY valid JSON (no markdown, no explanation outside the JSON):
{{
  "publish": true or false,
  "reason": "one sentence explaining your decision",
  "category": "one of: payments, crypto, banking, regulation, insurtech, lending, tokenization, stablecoins, defi, infrastructure, other",
  "priority": "one of: high, medium, low"
}}"""


def classify_article(title: str, url: str, snippet: str = "") -> dict:
    """
    Call Claude claude-haiku-4-5-20251001 to classify a single article.

    Returns:
        dict with keys: publish (bool), reason (str), category (str), priority (str)

    Requires ANTHROPIC_API_KEY environment variable.
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic package is required for AI classification. "
            "Install with: pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing ANTHROPIC_API_KEY environment variable. "
            "Set it in your shell or GitHub Actions secrets."
        )

    client = Anthropic(api_key=api_key)

    prompt = CLASSIFICATION_PROMPT.format(
        title=title or "(no title)",
        url=url or "(no url)",
        snippet=(snippet or "(no snippet)")[:500],  # Cap snippet length
    )

    try:
        message = client.messages.create(
            model=CLASSIFICATION_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract the text response
        response_text = message.content[0].text.strip()

        # Parse JSON from the response (handle potential markdown wrapping)
        if response_text.startswith("```"):
            # Strip markdown code fences if present
            lines = response_text.split("\n")
            response_text = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            ).strip()

        result = json.loads(response_text)

        # Validate and normalize the response
        return {
            "publish": bool(result.get("publish", False)),
            "reason": str(result.get("reason", "No reason provided")),
            "category": str(result.get("category", "other")).lower(),
            "priority": str(result.get("priority", "low")).lower(),
        }

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse AI response as JSON: {e}")
        logger.warning(f"Raw response: {response_text[:200]}")
        # Default to rejecting if we can't parse the response
        return {
            "publish": False,
            "reason": f"AI response parse error: {e}",
            "category": "other",
            "priority": "low",
        }
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        # On API error, default to PUBLISHING (fail-open) so you don't miss stories.
        # Change to False if you prefer fail-closed.
        return {
            "publish": True,
            "reason": f"AI classification unavailable ({e}), defaulting to publish",
            "category": "other",
            "priority": "medium",
        }


# ===========================================================================
# Filtered Article Logger
# ===========================================================================

def log_filtered_article(item: dict, decision: dict, log_path: Path = FILTERED_LOG_PATH):
    """
    Append a filtered (rejected) article to the log file for review.

    Each entry includes:
      - timestamp
      - title
      - url
      - publish decision (always NO here)
      - reason for filtering
      - category / priority
    """
    if not LOG_FILTERED:
        return

    log_path.parent.mkdir(parents=True, exist_ok=True)

    title = item.get("title", "(no title)")
    url = item.get("link") or item.get("url") or "(no url)"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    entry = (
        f"[{timestamp}] FILTERED\n"
        f"  Title:    {title}\n"
        f"  URL:      {url}\n"
        f"  Publish:  NO\n"
        f"  Reason:   {decision.get('reason', 'unknown')}\n"
        f"  Category: {decision.get('category', 'unknown')}\n"
        f"  Priority: {decision.get('priority', 'unknown')}\n"
        f"{'─' * 70}\n"
    )

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


# ===========================================================================
# Main Filter Class (combines dedup + AI classification)
# ===========================================================================

class AIArticleFilter:
    """
    Combined duplicate detection + AI classification filter.

    Usage:
        filter = AIArticleFilter()
        decision = filter.evaluate(item)

        if decision["publish"]:
            # proceed with posting to Telegram / X
            filter.record_posted(item, decision)
        else:
            # article was filtered, reason is in decision["reason"]
            pass

        filter.close()

    Pipeline integration point:
        This replaces the simple score threshold in run_alerts.py.
        Instead of just checking `score >= MIN_ALERT_SCORE`, articles
        now also pass through dedup + AI classification.
    """

    def __init__(
        self,
        db_path: Path = DB_PATH,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        log_filtered: bool = LOG_FILTERED,
        log_path: Path = FILTERED_LOG_PATH,
    ):
        self.db = ArticleDatabase(db_path)
        self.similarity_threshold = similarity_threshold
        self.log_filtered = log_filtered
        self.log_path = log_path

    def evaluate(self, item: dict) -> dict:
        """
        Evaluate a single article through the full filter pipeline.

        Steps:
            1. Check for duplicates (SQLite - fast, no API call)
            2. If not a duplicate, classify with AI (Claude claude-haiku-4-5-20251001)

        Args:
            item: Article dict with at least 'title' and 'link'/'url' keys.
                  Optionally 'snippet' or 'summary' for better classification.

        Returns:
            dict with keys:
                - publish: bool (True = post it, False = skip it)
                - reason: str (one sentence explanation)
                - category: str (fintech subcategory)
                - priority: str (high/medium/low)
                - source: str ("duplicate_check" or "ai_classification")
        """
        title = (item.get("title") or "").strip()
        url = (item.get("link") or item.get("url") or "").strip()
        snippet = (item.get("snippet") or item.get("summary") or "").strip()

        # --- Step 1: Duplicate check (cheap, local) ---
        is_dup, dup_reason = self.db.is_duplicate(
            url=url,
            title=title,
            threshold=self.similarity_threshold,
        )

        if is_dup:
            decision = {
                "publish": False,
                "reason": f"duplicate: {dup_reason}",
                "category": "duplicate",
                "priority": "low",
                "source": "duplicate_check",
            }
            if self.log_filtered:
                log_filtered_article(item, decision, self.log_path)
            return decision

        # --- Step 2: AI classification (API call) ---
        ai_result = classify_article(title=title, url=url, snippet=snippet)

        decision = {
            "publish": ai_result["publish"],
            "reason": ai_result["reason"],
            "category": ai_result["category"],
            "priority": ai_result["priority"],
            "source": "ai_classification",
        }

        if not decision["publish"] and self.log_filtered:
            log_filtered_article(item, decision, self.log_path)

        return decision

    def record_posted(self, item: dict, decision: dict):
        """
        Record that an article was posted. Call this AFTER successful publish
        to both Telegram and X so future runs can detect it as a duplicate.

        Args:
            item: The article dict
            decision: The AI decision dict (for category/priority)
        """
        url = (item.get("link") or item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        self.db.record_posted(
            url=url,
            title=title,
            category=decision.get("category", ""),
            priority=decision.get("priority", ""),
        )

    def close(self):
        """Close the database connection."""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ===========================================================================
# Standalone test / CLI
# ===========================================================================

if __name__ == "__main__":
    """
    Quick test: run this file directly to test classification on a sample article.

    Usage:
        export ANTHROPIC_API_KEY="your_key_here"
        python -m src.ai_filter
    """
    import sys

    logging.basicConfig(level=logging.INFO)

    sample = {
        "title": "JPMorgan Launches Blockchain-Based Dollar Deposit Token for Institutional Settlement",
        "link": "https://example.com/jpmorgan-deposit-token",
        "snippet": "JPMorgan Chase has launched a new blockchain-based deposit token "
                   "for institutional clients, enabling near-instant settlement of "
                   "dollar-denominated transactions on a permissioned ledger.",
    }

    print("Testing AI Article Filter...")
    print(f"  Title: {sample['title']}")
    print(f"  URL:   {sample['link']}")
    print()

    with AIArticleFilter(db_path=Path("state/test_posted.db")) as f:
        result = f.evaluate(sample)
        print("Decision:")
        print(json.dumps(result, indent=2))

        if result["publish"]:
            f.record_posted(sample, result)
            print("\nRecorded as posted.")

            # Test duplicate detection
            print("\nTesting duplicate detection (same article again)...")
            result2 = f.evaluate(sample)
            print(json.dumps(result2, indent=2))

    # Clean up test DB
    test_db = Path("state/test_posted.db")
    if test_db.exists():
        test_db.unlink()
        print("\nCleaned up test database.")
